import os
import re
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .config import load_project_env

load_project_env()

from .context_builder import build_context
from .llm import DeepSeekError, call_deepseek
from .prompt import build_deepseek_answer_prompt
from .retrieval import build_sources, filter_by_metadata, keyword_retrieve, load_chunks, source_evidence
from .schemas import GenerateRequest, Plan, QueryResult, Source
from .vector_store import DEFAULT_VECTOR_DB_PATH, LocalVectorStore, VectorStoreError, vector_db_status


app = FastAPI(title="邮智办 · C AI/RAG 服务", version="0.1.0")


@lru_cache(maxsize=1)
def get_chunks() -> tuple[dict[str, Any], ...]:
    return tuple(load_chunks())


@lru_cache(maxsize=1)
def get_vector_store() -> LocalVectorStore:
    return LocalVectorStore(os.getenv("RAG_VECTOR_DB_PATH", str(DEFAULT_VECTOR_DB_PATH)))


def verify_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("RAG_API_KEY")
    if not expected:
        return
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="缺少 RAG 服务密钥")
    if authorization[len(prefix):] != expected:
        raise HTTPException(status_code=403, detail="RAG 服务密钥不正确")


@app.get("/health")
def health() -> dict[str, Any]:
    chunks = get_chunks()
    status = vector_db_status(os.getenv("RAG_VECTOR_DB_PATH", str(DEFAULT_VECTOR_DB_PATH)))
    return {
        "status": "ok",
        "mode": "rag",
        "chunks": len(chunks),
        "vector_db_ready": status["ready"],
        "vector_db_chunks": status["chunks"],
        "embedding_model": status["model"],
        "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
    }


@app.get("/sources/evidence")
def evidence(
    title: str = Query(..., min_length=1, max_length=300),
    reference: str = Query(..., min_length=1, max_length=1000),
    _: None = Depends(verify_api_key),
) -> dict[str, Any]:
    result = source_evidence(title, reference)
    if not result.get("chunks"):
        raise HTTPException(status_code=404, detail="暂未找到该来源的详细内容")
    return result


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value).strip()] if str(value).strip() else []


def _sources_from_affair(affair: dict[str, Any]) -> list[dict[str, str]]:
    sources = affair.get("sources") or []
    if not isinstance(sources, list):
        return []
    result = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        title = str(source.get("title") or "").strip()
        reference = str(source.get("reference") or "").strip()
        if title and reference:
            result.append({"title": title, "reference": reference})
    return result


def _build_plan(affair: dict[str, Any], fallback_sources: list[dict[str, str]]) -> Plan:
    affair_sources = _sources_from_affair(affair)
    return Plan(
        affair_id=affair.get("id"),
        title=str(affair.get("title") or "未命名事务"),
        materials=_list(affair.get("materials")),
        steps=_list(affair.get("steps")),
        location=str(affair.get("location") or ""),
        room=str(affair.get("room") or ""),
        contact=str(affair.get("contact") or ""),
        office_hours=str(affair.get("office_hours") or ""),
        sources=[Source(**source) for source in (affair_sources or fallback_sources)],
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _append_unique(items: list[str], value: str) -> None:
    normalized = value.strip()
    if normalized and normalized not in items:
        items.append(normalized)


def _numbered_items(text: str) -> list[str]:
    normalized = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    matches = re.finditer(
        r"(?:^|\n)\s*(?:\d+[.、]|（[一二三四五六七八九十]+）)\s*(.+?)(?=(?:\n\s*(?:\d+[.、]|（[一二三四五六七八九十]+）))|\Z)",
        normalized,
        re.S,
    )
    items = []
    for match in matches:
        item = re.sub(r"\s*\n\s*", " ", match.group(1)).strip(" ：:;；")
        item = re.split(r"[二三四五六七八九十]、(?:相关手续|办理流程|办理办法|办理步骤)", item, maxsplit=1)[0].strip(" ：:;；")
        if 3 <= len(item) <= 180:
            items.append(item)
    return items


def _text_before(text: str, heading_terms: tuple[str, ...]) -> str:
    positions = [text.find(term) for term in heading_terms if term in text]
    positions = [pos for pos in positions if pos > 0]
    if not positions:
        return text
    return text[: min(positions)]


def _text_after(text: str, heading_terms: tuple[str, ...]) -> str:
    positions = [text.find(term) for term in heading_terms if term in text]
    if not positions:
        return text
    start = min(pos for pos in positions if pos >= 0)
    return text[start:]


def _derived_materials(chunks: list[dict[str, Any]]) -> list[str]:
    materials: list[str] = []
    combined = "\n".join(str(chunk.get("content") or "") for chunk in chunks)
    if "医院证明" in combined:
        _append_unique(materials, "因病住院、急诊留院观察或患其他不适合参加考试疾病的，提供校医院或二级甲等（含）及以上医院证明")
    if "直系亲属突发不可抗拒事由" in combined:
        _append_unique(materials, "因直系亲属突发不可抗拒事由须请假离校的，提供相关证明")
    if "组织单位证明" in combined:
        _append_unique(materials, "代表学校参加各类学术、交流活动的，提供组织单位证明")
    if "缓考原因、联系方式和相关附件证明" in combined:
        _append_unique(materials, "在系统中填写缓考原因、联系方式，并上传相关附件证明")
    for chunk in chunks:
        title = str(chunk.get("title") or "")
        content = str(chunk.get("content") or "")
        if _contains_any(title + content[:80], ("准备材料", "申请材料", "证明材料", "提交材料")):
            material_text = _text_before(content, ("二、相关手续", "相关手续", "办理流程", "办理办法", "办理步骤"))
            for item in _numbered_items(material_text):
                if _contains_any(item, ("办理办法", "领取地点", "联系电话", "地址：", "地址:", "空白表", "审核表", "面试意见")):
                    continue
                _append_unique(materials, item)
    return materials


def _derived_steps(chunks: list[dict[str, Any]]) -> list[str]:
    steps: list[str] = []
    for chunk in chunks:
        title = str(chunk.get("title") or "")
        content = str(chunk.get("content") or "")
        text = f"{title}\n{content}"
        if "本科教务管理系统" in text and "考试前" in text:
            _append_unique(steps, "考试前在本科教务管理系统中提交缓考申请")
        if "课程与考试 → 考试管理 → 缓考申请" in text:
            _append_unique(steps, "进入系统后选择“课程与考试 → 考试管理 → 缓考申请”")
        if "点击“申请”" in text:
            _append_unique(steps, "查询到需要缓考的课程后，点击该课程右侧“申请”")
        if "填写缓考原因" in text and "联系方式" in text:
            _append_unique(steps, "填写缓考原因、联系方式并上传相关附件证明")
        if "点击“确认”" in text:
            _append_unique(steps, "确认信息无误后点击“确认”提交申请")
        if "送审" in text and "审核人" in text:
            _append_unique(steps, "申请信息变为待审核后，选择审核人并点击“送审”")
        if "辅导员审核" in text and "学院教务" in text:
            _append_unique(steps, "等待辅导员审核、学院教务审核，审核通过后缓考申请完成")
        if "查询审核结果" in text:
            _append_unique(steps, "审核完成后，在系统中查询缓考申请审核结果")
        if _contains_any(text, ("相关手续", "办理流程", "办理办法", "办理步骤")):
            step_text = _text_after(content, ("二、相关手续", "相关手续", "办理流程", "办理办法", "办理步骤"))
            for item in _numbered_items(step_text):
                if not _contains_any(item, ("联系电话", "领取地点", "地址：", "地址:")):
                    _append_unique(steps, item)
    return steps


def _service_chunks(chunks: list[dict[str, Any]], service: str) -> list[dict[str, Any]]:
    return [chunk for chunk in chunks if str(chunk.get("service") or "").strip() == service]


def _plan_evidence_chunks(chunks: list[dict[str, Any]], all_chunks: list[dict[str, Any]], service: str) -> list[dict[str, Any]]:
    evidence = list(chunks)
    if service == "缓考申请":
        for chunk in all_chunks:
            if chunk.get("document_id") in {"deferred_exam_001", "deferred_exam_002"}:
                evidence.append(chunk)
    seen: set[str] = set()
    unique = []
    for chunk in evidence:
        chunk_id = str(chunk.get("chunk_id") or "")
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            unique.append(chunk)
    return unique


def _build_rag_plan(
    chunks: list[dict[str, Any]],
    sources: list[dict[str, str]],
    all_chunks: list[dict[str, Any]],
) -> Plan | None:
    service_counts: dict[str, int] = {}
    for chunk in chunks:
        service = str(chunk.get("service") or "").strip()
        if service:
            service_counts[service] = service_counts.get(service, 0) + 1
    if not service_counts:
        return None

    service = max(service_counts, key=service_counts.get)
    relevant_chunks = _plan_evidence_chunks(_service_chunks(chunks, service), all_chunks, service)
    knowledge_text = "\n".join(
        f"{chunk.get('title') or ''}\n{chunk.get('content') or ''}" for chunk in relevant_chunks
    )
    materials = _derived_materials(relevant_chunks)
    steps = _derived_steps(relevant_chunks)
    if not materials and not steps and not _contains_any(knowledge_text, ("申请", "办理", "审批", "流程", "材料", "证明")):
        return None
    return Plan(
        affair_id=None,
        title=service,
        materials=materials,
        steps=steps,
        location="",
        room="",
        contact="",
        office_hours="",
        sources=[Source(**source) for source in (build_sources(relevant_chunks) or sources)],
    )


def _merge_plan_with_rag(plan: Plan, rag_plan: Plan | None) -> Plan:
    if rag_plan is None:
        return plan
    return Plan(
        affair_id=plan.affair_id,
        title=plan.title,
        materials=plan.materials or rag_plan.materials,
        steps=plan.steps or rag_plan.steps,
        location=plan.location,
        room=plan.room,
        contact=plan.contact,
        office_hours=plan.office_hours,
        sources=plan.sources or rag_plan.sources,
    )


def _answer(question: str, chunks: list[dict[str, Any]], retrieval_method: str) -> str:
    if not chunks:
        return "当前知识库未找到可靠信息，请补充问题或联系教务部门确认。"
    label = "向量检索" if retrieval_method == "vector" else "关键词检索 fallback"
    lines = [f"当前知识库通过{label}找到与问题相关的缓考申请资料，以下回答仅依据已整理 Chunk："]
    for index, chunk in enumerate(chunks, start=1):
        lines.append(f"{index}. {chunk['title']}：{chunk['content']}")
    return "\n".join(lines)


def _deepseek_warning(error: DeepSeekError) -> str:
    if "DEEPSEEK_API_KEY" in str(error):
        return "DeepSeek 未配置，当前使用检索结果直接回答。"
    return "DeepSeek 当前不可用，已回退到检索结果直接回答。"


@app.post("/generate", response_model=QueryResult)
def generate(body: GenerateRequest, _: None = Depends(verify_api_key)) -> QueryResult:
    profile = body.profile.model_dump()
    active_chunks = list(get_chunks())
    matched_chunks = filter_by_metadata(active_chunks, profile)
    warnings: list[str] = []
    retrieval_method = "vector"
    try:
        search_results = get_vector_store().search(body.question, profile, top_k=5)
        retrieved_chunks = [result.chunk for result in search_results]
    except VectorStoreError as exc:
        retrieval_method = "keyword"
        retrieved_chunks = keyword_retrieve(body.question, matched_chunks)
        warnings.append(f"Vector DB 不可用，已回退到关键词检索：{exc}")

    context = build_context(body.question, profile, retrieved_chunks, body.affairs)
    rag_sources = build_sources(retrieved_chunks)
    rag_plan = _build_rag_plan(retrieved_chunks, rag_sources, active_chunks)
    plans = [_merge_plan_with_rag(_build_plan(affair, rag_sources), rag_plan) for affair in body.affairs]
    if not plans and rag_plan is not None:
        plans = [rag_plan]

    if not retrieved_chunks:
        warnings.append("当前知识库未找到可靠信息，未生成政策性结论。")
    if not body.affairs:
        warnings.append("后端未提供结构化事务数据，办理地点、房间、联系人和办公时间保持为空。")
    else:
        missing_precise_fields = []
        for field in ("location", "room", "contact", "office_hours"):
            if all(not str(affair.get(field) or "").strip() for affair in body.affairs):
                missing_precise_fields.append(field)
        if missing_precise_fields:
            warnings.append("后端提供的事务结构化事实不完整，缺失：" + "、".join(missing_precise_fields))

    try:
        answer = call_deepseek(build_deepseek_answer_prompt(context))
    except DeepSeekError as exc:
        answer = _answer(context["user_question"], retrieved_chunks, retrieval_method)
        warnings.append(_deepseek_warning(exc))

    return QueryResult(
        answer=answer,
        plans=plans,
        sources=[Source(**source) for source in rag_sources],
        warnings=warnings,
        mode="rag",
    )

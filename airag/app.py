import os
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException

from .context_builder import build_context
from .llm import DeepSeekError, call_deepseek
from .prompt import build_deepseek_answer_prompt
from .retrieval import build_sources, filter_by_metadata, keyword_retrieve, load_chunks
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
    }


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
    plans = [_build_plan(affair, rag_sources) for affair in body.affairs]

    if not retrieved_chunks:
        warnings.append("当前知识库未找到可靠信息，未生成政策性结论。")
    if not body.affairs:
        warnings.append("后端未提供结构化事务数据，C 服务不会编造办理地点、房间、联系人或办公时间。")
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

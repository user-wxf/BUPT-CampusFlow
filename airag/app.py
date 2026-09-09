import os
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException

from .retrieval import build_sources, filter_by_metadata, load_chunks, retrieve
from .schemas import GenerateRequest, Plan, QueryResult, Source


app = FastAPI(title="邮智办 · C AI/RAG 服务", version="0.1.0")


@lru_cache(maxsize=1)
def get_chunks() -> tuple[dict[str, Any], ...]:
    return tuple(load_chunks())


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
    return {"status": "ok", "mode": "rag", "chunks": len(chunks)}


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


def _answer(question: str, chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "当前知识库未找到可靠信息，请补充问题或联系教务部门确认。"
    lines = ["当前知识库检索到与问题相关的缓考申请资料，以下回答仅依据已整理 Chunk："]
    for index, chunk in enumerate(chunks, start=1):
        lines.append(f"{index}. {chunk['title']}：{chunk['content']}")
    return "\n".join(lines)


@app.post("/generate", response_model=QueryResult)
def generate(body: GenerateRequest, _: None = Depends(verify_api_key)) -> QueryResult:
    profile = body.profile.model_dump()
    active_chunks = list(get_chunks())
    matched_chunks = filter_by_metadata(active_chunks, profile)
    retrieved_chunks = retrieve(body.question, matched_chunks)
    rag_sources = build_sources(retrieved_chunks)
    plans = [_build_plan(affair, rag_sources) for affair in body.affairs]
    warnings: list[str] = []

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

    return QueryResult(
        answer=_answer(body.question, retrieved_chunks),
        plans=plans,
        sources=[Source(**source) for source in rag_sources],
        warnings=warnings,
        mode="rag",
    )

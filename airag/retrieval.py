import json
import re
from pathlib import Path
from typing import Any


PROFILE_FIELDS = ("college", "grade", "education_level", "campus")
REQUIRED_CHUNK_FIELDS = (
    "chunk_id",
    "service",
    "college",
    "grade",
    "education_level",
    "campus",
    "title",
    "content",
    "source",
    "status",
    "source_pages",
)
DEFAULT_CHUNKS_PATH = Path(__file__).resolve().parent / "data" / "chunks" / "chunks.jsonl"

KEY_TERMS = (
    "缓考",
    "期末考试",
    "期中考试",
    "考试",
    "生病",
    "住院",
    "急诊",
    "疾病",
    "医院证明",
    "证明",
    "申请",
    "审批",
    "审核",
    "辅导员",
    "班主任",
    "教务",
    "补考",
    "重修",
    "缺考",
    "本科教务管理系统",
    "教务管理系统",
    "课程与考试",
    "考试管理",
    "送审",
    "附件",
    "联系方式",
)
STOP_CHARS = set("的一是在不了和及或与为我你他她它们这个那个什么怎么如何办理参加可以需要")


class ChunkLoadError(ValueError):
    pass


def load_chunks(path: str | Path = DEFAULT_CHUNKS_PATH) -> list[dict[str, Any]]:
    chunk_path = Path(path)
    chunks: list[dict[str, Any]] = []
    with chunk_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ChunkLoadError(f"Invalid JSONL at line {line_number}: {exc.msg}") from exc
            missing = [field for field in REQUIRED_CHUNK_FIELDS if field not in chunk]
            if missing:
                raise ChunkLoadError(f"Chunk line {line_number} missing fields: {', '.join(missing)}")
            if chunk.get("status") != "active":
                continue
            chunks.append(chunk)
    return chunks


def metadata_matches(chunk: dict[str, Any], profile: dict[str, str]) -> bool:
    for field in PROFILE_FIELDS:
        chunk_value = str(chunk.get(field) or "").strip()
        user_value = str(profile.get(field) or "").strip()
        if chunk_value.lower() == "all":
            continue
        if not user_value:
            return False
        if chunk_value != user_value:
            return False
    return True


def filter_by_metadata(chunks: list[dict[str, Any]], profile: dict[str, str]) -> list[dict[str, Any]]:
    return [chunk for chunk in chunks if metadata_matches(chunk, profile)]


def _terms(text: str) -> set[str]:
    normalized = text.lower()
    terms = {term.lower() for term in KEY_TERMS if term.lower() in normalized}
    terms.update(re.findall(r"[a-zA-Z0-9_]{2,}", normalized))
    chinese_chars = [char for char in normalized if "\u4e00" <= char <= "\u9fff" and char not in STOP_CHARS]
    for index in range(len(chinese_chars) - 1):
        terms.add("".join(chinese_chars[index:index + 2]))
    return {term for term in terms if len(term) >= 2}


def _score(question: str, chunk: dict[str, Any]) -> int:
    query_terms = _terms(question)
    if not query_terms:
        return 0
    haystack = " ".join(str(chunk.get(field) or "") for field in ("service", "title", "content")).lower()
    score = 0
    for term in query_terms:
        if term in haystack:
            score += 3 if term in KEY_TERMS else 1
    service = str(chunk.get("service") or "").lower()
    title = str(chunk.get("title") or "").lower()
    if service and service in question.lower():
        score += 10
    if title and any(term in title for term in query_terms):
        score += 4
    return score


def keyword_retrieve(question: str, chunks: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
    scored = [(_score(question, chunk), chunk) for chunk in chunks]
    relevant = [(score, chunk) for score, chunk in scored if score >= 3]
    relevant.sort(key=lambda item: (-item[0], str(item[1].get("chunk_id") or "")))
    return [chunk for _, chunk in relevant[:top_k]]


def retrieve(question: str, chunks: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
    return keyword_retrieve(question, chunks, top_k)


def source_from_chunk(chunk: dict[str, Any]) -> dict[str, str] | None:
    title = str(chunk.get("source") or "").strip()
    if not title:
        return None
    pages = str(chunk.get("source_pages") or "").strip()
    reference = f"第{pages}页" if pages else str(chunk.get("source_file") or "来源文件").strip()
    if not reference:
        return None
    return {"title": title, "reference": reference}


def dedupe_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for source in sources:
        title = str(source.get("title") or "").strip()
        reference = str(source.get("reference") or "").strip()
        if not title or not reference:
            continue
        key = (title, reference)
        if key in seen:
            continue
        seen.add(key)
        unique.append({"title": title, "reference": reference})
    return unique


def build_sources(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    return dedupe_sources([source for chunk in chunks if (source := source_from_chunk(chunk))])
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - runtime dependency check
    PdfReader = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[2]
AIRAG_ROOT = REPO_ROOT / "airag"
RAW_ROOT = AIRAG_ROOT / "data" / "raw"
PROCESSED_ROOT = AIRAG_ROOT / "data" / "processed"
METADATA_PATH = AIRAG_ROOT / "data" / "metadata" / "documents.json"
CHUNKS_PATH = AIRAG_ROOT / "data" / "chunks" / "chunks.jsonl"
SOURCE_MANIFEST_PATH = AIRAG_ROOT / "data" / "metadata" / "source_manifest.csv"
INGEST_REPORT_PATH = AIRAG_ROOT / "data" / "metadata" / "ingest_report_c_delivery.json"

SERVICE_CATEGORY_ALIASES = {
    "discipline": "discipline",
    "graduation": "graduation",
    "major_transfer": "major_transfer",
    "scholarships": "scholarship",
    "student_development": "student_development",
    "student_management": "student_status",
    "study_status": "student_status",
}

DOCUMENT_OVERRIDES: dict[str, dict[str, str | None]] = {
    "student_discipline_measures_2025-09-01.html": {
        "title": "北京邮电大学学生违纪处分管理办法",
        "service": "违纪处分",
        "category": "discipline",
        "education_level": "all",
    },
    "student_management_regulations_2025-09-01.html": {
        "title": "北京邮电大学学生管理规定",
        "service": "学生管理",
        "category": "student_status",
        "education_level": "all",
    },
    "graduate_registration_notice_2025-09-16.html": {
        "title": "关于做好2025级研究生新生报到相关工作的通知",
        "service": "研究生报到",
        "category": "student_status",
        "education_level": "研究生",
    },
    "military_service_policy.html": {
        "title": "服兵役高等学校学生国家教育资助政策",
        "service": "服兵役教育资助",
        "category": "student_status",
        "education_level": "all",
    },
    "student_affairs_office_services.html": {
        "title": "学生处科室中心服务信息",
        "service": "学生事务服务",
        "category": "student_status",
        "education_level": "all",
    },
    "undergraduate_major_transfer_process.pdf": {
        "title": "普通本科生校内转专业工作流程",
        "service": "转专业",
        "category": "major_transfer",
        "education_level": "本科",
    },
    "teaching_affairs_brief_transfer_2026.html": {
        "title": "本科教学工作简报2026年第三期转专业工作",
        "service": "转专业",
        "category": "major_transfer",
        "education_level": "本科",
    },
    "completion_process.pdf": {
        "title": "普通本科生结业申请工作流程",
        "service": "结业申请",
        "category": "graduation",
        "education_level": "本科",
    },
    "pre_graduation_repeat_year_process.pdf": {
        "title": "普通本科生毕业年级延长学习年限工作流程",
        "service": "延长学习年限",
        "category": "graduation",
        "education_level": "本科",
    },
    "undergraduate_thesis_management_rules.pdf": {
        "title": "北京邮电大学本科毕业设计论文管理办法",
        "service": "本科毕业设计",
        "category": "graduation",
        "education_level": "本科",
    },
    "national_scholarship_rules_2025-09-01.html": {
        "title": "北京邮电大学本科生国家奖学金评审实施细则",
        "service": "本科生国家奖学金",
        "category": "scholarship",
        "education_level": "本科",
    },
    "national_encouragement_scholarship_rules_2025-09-01.html": {
        "title": "北京邮电大学本科生国家励志奖学金评审实施细则",
        "service": "本科生国家励志奖学金",
        "category": "scholarship",
        "education_level": "本科",
    },
    "student_aid_measures_2025-09-01.html": {
        "title": "北京邮电大学学生奖助学金管理办法",
        "service": "奖助学金",
        "category": "scholarship",
        "education_level": "all",
    },
    "donated_scholarship_rules_2026-04-21.html": {
        "title": "北京邮电大学学生社会捐助奖助学金管理办法",
        "service": "社会捐助奖助学金",
        "category": "scholarship",
        "education_level": "all",
    },
    "graduate_national_aid_rules.html": {
        "title": "北京邮电大学研究生国家助学金管理办法",
        "service": "研究生国家助学金",
        "category": "scholarship",
        "education_level": "研究生",
    },
    "work_study_rules.html": {
        "title": "北京邮电大学学生勤工助学管理办法",
        "service": "勤工助学",
        "category": "work_study",
        "education_level": "all",
    },
    "graduate_assistantship_rules_2026-04-21.html": {
        "title": "北京邮电大学研究生三助工作实施办法",
        "service": "研究生三助",
        "category": "student_development",
        "education_level": "研究生",
    },
    "undergraduate_quality_evaluation_2025-12-30.html": {
        "title": "北京邮电大学本科生综合素质测评办法",
        "service": "综合素质测评",
        "category": "student_development",
        "education_level": "本科",
    },
}


@dataclass
class IngestedDocument:
    id: str
    service: str
    category: str
    college: str
    grade: str
    education_level: str
    campus: str
    source: str
    updated_at: str | None
    source_url: str
    status: str
    raw_file: str
    processed_file: str
    sha256: str
    text_sha256: str
    title: str
    format: str
    page_count: int | None
    text_length: int
    ocr_required: bool


class ArticleTextParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ol",
        "p",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.capture_depth = 0
        self.ignore_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self.ignore_depth += 1
            return
        if tag == "title":
            self.in_title = True
        identity = " ".join([attr_map.get("id", ""), attr_map.get("class", "")])
        if not self.capture and (
            "vsb_content" in identity or "v_news_content" in identity or "art-body" in identity
        ):
            self.capture = True
            self.capture_depth = 1
            self.parts.append("\n")
            return
        if self.capture:
            self.capture_depth += 1
            if tag in self.BLOCK_TAGS:
                self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.ignore_depth:
            self.ignore_depth -= 1
            return
        if tag == "title":
            self.in_title = False
        if self.capture:
            if tag in self.BLOCK_TAGS:
                self.parts.append("\n")
            self.capture_depth -= 1
            if self.capture_depth <= 0:
                self.capture = False

    def handle_data(self, data: str) -> None:
        if self.ignore_depth:
            return
        text = html.unescape(data)
        if self.in_title:
            self.title_parts.append(text)
        if self.capture:
            self.parts.append(text)

    @property
    def article_text(self) -> str:
        return normalize_text("\n".join(self.parts))

    @property
    def page_title(self) -> str:
        return normalize_space("".join(self.title_parts))


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = heal_wrapped_lines(text)
    return text.strip()


def heal_wrapped_lines(text: str) -> str:
    healed: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if healed and healed[-1] != "":
                healed.append("")
            continue
        if healed and should_merge_line(healed[-1], line):
            separator = " " if re.match(r"^第[一二三四五六七八九十百]+章$", healed[-1]) else ""
            healed[-1] = f"{healed[-1]}{separator}{line}"
        else:
            healed.append(line)
    return "\n".join(healed)


def should_merge_line(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if current.startswith(("#", "-", "|")):
        return False
    if re.match(r"^第[一二三四五六七八九十百0-9]+[章节条]", current) and not re.match(
        r"^第[一二三四五六七八九十百0-9]+章$", previous
    ):
        return False
    if re.match(r"^([（(][一二三四五六七八九十0-9]+[）)]|[0-9]+[.、])", current):
        return False
    if re.search(r"[。！？；;：:]$", previous):
        return False
    if current[0] in "，,。；：、）)]":
        return True
    if re.search(r"[，、（(“《〔]$", previous):
        return True
    if re.match(r"^第[一二三四五六七八九十百0-9]+章$", previous) and len(current) <= 12:
        return True
    return True


def compact_for_hash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(compact_for_hash(text).encode("utf-8")).hexdigest().upper()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def extract_html(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    parser = ArticleTextParser()
    parser.feed(raw)
    title = parser.page_title
    text = parser.article_text
    if not text:
        text = fallback_html_to_text(raw)
    return title, text


def fallback_html_to_text(raw: str) -> str:
    raw = re.sub(r"<(script|style|noscript)\b.*?</\1>", "\n", raw, flags=re.I | re.S)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</(p|div|li|tr|h[1-6]|section|article)>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return normalize_text(raw)


def extract_pdf(path: Path) -> tuple[str, list[tuple[int, str]], bool]:
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed; cannot extract PDF text")
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        pages.append((index, text))
    merged = "\n\n".join(text for _, text in pages if text)
    ocr_required = len(compact_for_hash(merged)) < 50
    return merged, pages, ocr_required


def infer_title(file_name: str, page_title: str, manifest_title: str) -> str:
    override = DOCUMENT_OVERRIDES.get(file_name, {})
    if override.get("title"):
        return str(override["title"])
    if page_title:
        return re.sub(r"[-_].*$", "", page_title).strip()
    return manifest_title or Path(file_name).stem


def infer_metadata(row: dict[str, str], title: str, text: str) -> dict[str, str | None]:
    file_name = row["file"]
    override = DOCUMENT_OVERRIDES.get(file_name, {})
    category = str(override.get("category") or SERVICE_CATEGORY_ALIASES.get(row.get("category", ""), row.get("category", "")))
    service = str(override.get("service") or title)
    lower = f"{title}\n{text}"
    education_level = override.get("education_level")
    if education_level is None:
        if "本科" in lower and "研究生" not in lower:
            education_level = "本科"
        elif "研究生" in lower and "本科" not in lower:
            education_level = "研究生"
        else:
            education_level = "all"
    return {
        "category": category,
        "service": service,
        "college": "all",
        "grade": "all",
        "education_level": str(education_level),
        "campus": "all",
    }


def doc_id_from_title(title: str, file_name: str) -> str:
    if file_name in DOCUMENT_OVERRIDES:
        slug = Path(file_name).stem
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", Path(file_name).stem.lower()).strip("_")
    if not slug:
        slug = hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
    return slug


def build_markdown(title: str, source_url: str, published_at: str | None, text: str) -> str:
    lines = [f"# {title}", "", f"- 来源 URL：{source_url or '未提供'}"]
    lines.append(f"- 发布日期：{published_at or '未确认'}")
    lines.append("")
    lines.extend(markdownize_lines(text))
    return "\n".join(lines).rstrip() + "\n"


def markdownize_lines(text: str) -> list[str]:
    output: list[str] = []
    for raw_line in collapse_heading_fragments(normalize_text(text).splitlines()):
        line = normalize_space(raw_line)
        if not line:
            if output and output[-1] != "":
                output.append("")
            continue
        if is_noise_line(line):
            continue
        heading_level = heading_level_for(line)
        if heading_level:
            if output and output[-1] != "":
                output.append("")
            output.append(f"{'#' * heading_level} {line}")
            output.append("")
        else:
            output.append(line)
    while output and output[-1] == "":
        output.pop()
    return output


def collapse_heading_fragments(lines: list[str]) -> list[str]:
    collapsed: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if re.match(r"^第[一二三四五六七八九十百0-9]+[章节]$", line):
            fragments = [line]
            lookahead = index + 1
            while lookahead < len(lines) and lines[lookahead].strip() == "":
                lookahead += 1
            while lookahead < len(lines):
                candidate = lines[lookahead].strip()
                if not candidate:
                    lookahead += 1
                    continue
                if len(candidate) > 18 or re.match(r"^第[一二三四五六七八九十百0-9]+[章节条]", candidate):
                    break
                fragments.append(candidate)
                lookahead += 1
                while lookahead < len(lines) and lines[lookahead].strip() == "":
                    lookahead += 1
                if len("".join(fragments[1:])) >= 8:
                    break
            if len(fragments) > 1:
                collapsed.append(f"{fragments[0]} {''.join(fragments[1:])}")
                index = lookahead
                continue
        collapsed.append(lines[index])
        index += 1
    return collapsed


def is_noise_line(line: str) -> bool:
    noise = {
        "学校主页",
        "信息门户",
        "邮ai",
        "学工系统",
        "请输入关键字",
        "下一条",
        "上一条",
        "打印",
        "关闭",
    }
    return line in noise or line.startswith("当前位置") or line.startswith("附件【")


def heading_level_for(line: str) -> int | None:
    if re.match(r"^第[一二三四五六七八九十百]+章\s+", line):
        return 2
    if re.match(r"^第[一二三四五六七八九十百]+节\s+", line):
        return 3
    if re.match(r"^[一二三四五六七八九十]+、", line):
        return 3
    if re.match(r"^附件[：:]", line):
        return 2
    return None


def split_sections(markdown: str) -> list[tuple[str, str]]:
    lines = markdown.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in lines:
        if line.startswith("# "):
            current_title = line[2:].strip()
            continue
        if line.startswith("## ") or line.startswith("### "):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.lstrip("#").strip()
            current_lines = []
            continue
        if line.strip():
            current_lines.append(line.strip())
    if current_lines:
        sections.append((current_title, current_lines))
    return [(title, "\n".join(items)) for title, items in sections if normalize_space("\n".join(items))]


def split_into_chunks(markdown: str, document: IngestedDocument, pages: list[tuple[int, str]] | None) -> list[dict[str, Any]]:
    sections = split_sections(markdown)
    raw_units: list[tuple[str, str]] = []
    for title, body in sections:
        parts = split_policy_articles(body)
        if len(parts) <= 1:
            raw_units.append((title, body))
        else:
            raw_units.extend((infer_chunk_title(title, part), part) for part in parts)

    merged_units: list[tuple[str, str]] = []
    pending_title = ""
    pending_body = ""
    for title, body in raw_units:
        body = normalize_text(body)
        if not body or body.startswith("- 来源 URL") or body.startswith("- 发布日期"):
            continue
        if len(compact_for_hash(pending_body)) < 180:
            pending_title = pending_title or title
            pending_body = f"{pending_body}\n{body}".strip()
            continue
        merged_units.append((pending_title or title, pending_body))
        pending_title = title
        pending_body = body
    if pending_body:
        merged_units.append((pending_title or document.title, pending_body))

    chunks: list[dict[str, Any]] = []
    seen_content: set[str] = set()
    for index, (title, body) in enumerate(merged_units, start=1):
        if len(compact_for_hash(body)) < 80:
            continue
        key = compact_for_hash(body)
        if key in seen_content:
            continue
        seen_content.add(key)
        source_pages = find_source_pages(body, pages) if pages else ""
        chunks.append(
            {
                "chunk_id": f"{document.id}_{index:03d}",
                "document_id": document.id,
                "service": document.service,
                "college": document.college,
                "grade": document.grade,
                "education_level": document.education_level,
                "campus": document.campus,
                "title": title or document.title,
                "content": body,
                "source": document.source,
                "updated_at": document.updated_at,
                "status": "active",
                "source_file": document.raw_file,
                "source_pages": source_pages,
            }
        )
    return chunks


def split_policy_articles(text: str) -> list[str]:
    marker = re.compile(r"(?=第[一二三四五六七八九十百]+条\s*)")
    parts = [part.strip() for part in marker.split(text) if part.strip()]
    if len(parts) > 1:
        return merge_short_parts(parts)
    paragraphs = [p.strip() for p in re.split(r"\n{1,}", text) if p.strip()]
    return merge_short_parts(paragraphs)


def merge_short_parts(parts: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""
    for part in parts:
        if not buffer:
            buffer = part
        elif len(compact_for_hash(buffer)) < 260:
            buffer = f"{buffer}\n{part}"
        else:
            merged.append(buffer)
            buffer = part
    if buffer:
        merged.append(buffer)
    return merged


def infer_chunk_title(section_title: str, content: str) -> str:
    first_line = normalize_space(content.splitlines()[0] if content.splitlines() else content)
    article = re.match(r"^(第[一二三四五六七八九十百]+条)\s*(.*)", first_line)
    if article:
        rest = article.group(2)
        if rest:
            return normalize_space(f"{section_title} {article.group(1)} {rest[:30]}")
        return normalize_space(f"{section_title} {article.group(1)}")
    return section_title or first_line[:40]


def find_source_pages(content: str, pages: list[tuple[int, str]] | None) -> str:
    if not pages:
        return ""
    compact_content = compact_for_hash(content)
    if not compact_content:
        return ""
    sample = compact_content[: min(80, len(compact_content))]
    matched = [number for number, text in pages if sample and sample in compact_for_hash(text)]
    if not matched:
        shorter = compact_content[: min(30, len(compact_content))]
        matched = [number for number, text in pages if shorter and shorter in compact_for_hash(text)]
    if not matched:
        return ""
    if len(matched) == 1:
        return str(matched[0])
    return f"{min(matched)}-{max(matched)}"


def load_existing_documents() -> list[dict[str, Any]]:
    if not METADATA_PATH.exists():
        return []
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def load_existing_chunks() -> list[dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        return []
    chunks: list[dict[str, Any]] = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_chunks(path: Path, chunks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def append_source_manifest(rows: list[dict[str, str]]) -> None:
    SOURCE_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "document_id",
        "category",
        "service",
        "title",
        "file",
        "processed_file",
        "published_at",
        "source_url",
        "source_status",
        "sha256",
        "text_sha256",
    ]
    with SOURCE_MANIFEST_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def expected_document_ids(manifest_rows: list[dict[str, str]]) -> set[str]:
    ids: set[str] = set()
    for row in manifest_rows:
        if row.get("status") == "failed" or not row.get("file"):
            continue
        override = DOCUMENT_OVERRIDES.get(row["file"], {})
        title = str(override.get("title") or row.get("title") or row["file"])
        ids.add(doc_id_from_title(title, row["file"]))
    return ids


def existing_raw_file_hashes(documents: list[dict[str, Any]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for doc in documents:
        file_value = str(doc.get("file", ""))
        if not file_value:
            continue
        path = REPO_ROOT / file_value
        if path.exists() and path.is_file():
            hashes[sha256_file(path)] = file_value
    return hashes


def validate_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    required = {
        "chunk_id",
        "document_id",
        "service",
        "college",
        "grade",
        "education_level",
        "campus",
        "title",
        "content",
        "source",
        "updated_at",
        "status",
        "source_file",
        "source_pages",
    }
    errors: list[str] = []
    seen: set[str] = set()
    for index, chunk in enumerate(chunks, start=1):
        missing = required - set(chunk)
        if missing:
            errors.append(f"line {index} missing fields: {sorted(missing)}")
        chunk_id = str(chunk.get("chunk_id") or "")
        if chunk_id in seen:
            errors.append(f"duplicate chunk_id: {chunk_id}")
        seen.add(chunk_id)
        if not str(chunk.get("content") or "").strip():
            errors.append(f"empty content: {chunk_id}")
    return errors


def ingest(incoming_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest_rows = read_manifest(manifest_path)
    all_existing_documents = load_existing_documents()
    all_existing_chunks = load_existing_chunks()
    managed_document_ids = expected_document_ids(manifest_rows)
    existing_documents = [
        doc for doc in all_existing_documents if str(doc.get("id", "")) not in managed_document_ids
    ]
    existing_chunks = [
        chunk for chunk in all_existing_chunks if str(chunk.get("document_id", "")) not in managed_document_ids
    ]
    existing_doc_ids = {doc["id"] for doc in existing_documents}
    existing_chunk_ids = {chunk["chunk_id"] for chunk in existing_chunks}
    existing_file_hashes = existing_raw_file_hashes(existing_documents)
    existing_text_hashes = {
        sha256_text(str(chunk.get("content", "")))
        for chunk in existing_chunks
        if str(chunk.get("content", "")).strip()
    }

    ingested_documents: list[IngestedDocument] = []
    new_chunks: list[dict[str, Any]] = []
    source_manifest_rows: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    duplicate_report: list[dict[str, str]] = []

    for row in manifest_rows:
        if row.get("status") == "failed":
            failures.append({"file": row.get("file", ""), "error": row.get("error", "manifest status failed")})
            continue
        source_path = incoming_dir / row["category"] / row["file"]
        if not source_path.exists():
            failures.append({"file": row.get("file", ""), "error": "file not found"})
            continue

        suffix = source_path.suffix.lower()
        pages: list[tuple[int, str]] | None = None
        page_count: int | None = None
        ocr_required = False
        try:
            if suffix == ".html":
                page_title, text = extract_html(source_path)
            elif suffix == ".pdf":
                text, pages, ocr_required = extract_pdf(source_path)
                page_count = len(pages or [])
                page_title = ""
            else:
                failures.append({"file": row.get("file", ""), "error": f"unsupported format: {suffix}"})
                continue
        except Exception as exc:
            failures.append({"file": row.get("file", ""), "error": str(exc)})
            continue

        title = infer_title(row["file"], page_title, row.get("title", ""))
        metadata = infer_metadata(row, title, text)
        doc_id = doc_id_from_title(title, row["file"])
        if doc_id in existing_doc_ids:
            digest = hashlib.sha1(row["file"].encode("utf-8")).hexdigest()[:6]
            doc_id = f"{doc_id}_{digest}"
        existing_doc_ids.add(doc_id)
        category = str(metadata["category"])
        raw_relative = Path("airag/data/raw") / category / row["file"]
        raw_path = REPO_ROOT / raw_relative
        processed_relative = Path("airag/data/processed") / category / f"{doc_id}.md"
        processed_path = REPO_ROOT / processed_relative
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, raw_path)

        published_at = row.get("published_at") or None
        markdown = build_markdown(title, row.get("source_url", ""), published_at, text)
        processed_path.write_text(markdown, encoding="utf-8", newline="\n")

        file_hash = sha256_file(source_path)
        text_hash = sha256_text(text)
        if file_hash.upper() != (row.get("sha256") or "").upper():
            duplicate_report.append({"file": row["file"], "type": "checksum_mismatch", "detail": "manifest sha256 differs"})
        if file_hash in existing_file_hashes:
            duplicate_report.append(
                {
                    "file": row["file"],
                    "type": "existing_file_duplicate",
                    "detail": f"same raw file hash as {existing_file_hashes[file_hash]}",
                }
            )
        if text_hash in existing_text_hashes:
            duplicate_report.append({"file": row["file"], "type": "existing_content_duplicate", "detail": "same normalized text already exists"})
        existing_text_hashes.add(text_hash)

        doc = IngestedDocument(
            id=doc_id,
            service=str(metadata["service"]),
            category=category,
            college=str(metadata["college"]),
            grade=str(metadata["grade"]),
            education_level=str(metadata["education_level"]),
            campus=str(metadata["campus"]),
            source=title,
            updated_at=published_at,
            source_url=row.get("source_url", ""),
            status="active",
            raw_file=str(raw_relative).replace("\\", "/"),
            processed_file=str(processed_relative).replace("\\", "/"),
            sha256=file_hash,
            text_sha256=text_hash,
            title=title,
            format=suffix.lstrip("."),
            page_count=page_count,
            text_length=len(compact_for_hash(text)),
            ocr_required=ocr_required,
        )
        ingested_documents.append(doc)

        chunks = split_into_chunks(markdown, doc, pages)
        for chunk in chunks:
            original_id = chunk["chunk_id"]
            if original_id in existing_chunk_ids:
                chunk["chunk_id"] = f"{original_id}_{hashlib.sha1(doc.id.encode('utf-8')).hexdigest()[:6]}"
            existing_chunk_ids.add(chunk["chunk_id"])
        new_chunks.extend(chunks)
        source_manifest_rows.append(
            {
                "document_id": doc.id,
                "category": doc.category,
                "service": doc.service,
                "title": doc.title,
                "file": doc.raw_file,
                "processed_file": doc.processed_file,
                "published_at": doc.updated_at or "",
                "source_url": doc.source_url,
                "source_status": row.get("status", ""),
                "sha256": doc.sha256,
                "text_sha256": doc.text_sha256,
            }
        )

    document_records = [
        {
            "id": doc.id,
            "service": doc.service,
            "college": doc.college,
            "grade": doc.grade,
            "education_level": doc.education_level,
            "campus": doc.campus,
            "source": doc.source,
            "updated_at": doc.updated_at,
            "status": doc.status,
            "file": doc.raw_file,
        }
        for doc in ingested_documents
    ]
    all_documents = existing_documents + document_records
    all_chunks = existing_chunks + new_chunks
    validation_errors = validate_chunks(all_chunks)
    if validation_errors:
        raise RuntimeError("chunk validation failed: " + "; ".join(validation_errors[:5]))

    write_json(METADATA_PATH, all_documents)
    write_chunks(CHUNKS_PATH, all_chunks)
    append_source_manifest(source_manifest_rows)

    report = {
        "incoming_dir": str(incoming_dir),
        "manifest": str(manifest_path),
        "manifest_records": len(manifest_rows),
        "successful_documents": len(ingested_documents),
        "failed_documents": len(failures),
        "existing_documents_before": len(all_existing_documents),
        "replaced_documents": len(all_existing_documents) - len(existing_documents),
        "documents_after": len(all_documents),
        "existing_chunks_before": len(all_existing_chunks),
        "replaced_chunks": len(all_existing_chunks) - len(existing_chunks),
        "chunks_after": len(all_chunks),
        "new_chunks": len(new_chunks),
        "documents": [doc.__dict__ for doc in ingested_documents],
        "failures": failures,
        "duplicates_or_conflicts": duplicate_report,
        "manual_review": [
            {
                "file": doc.raw_file,
                "reason": "发布日期未在 manifest 中确认" if doc.updated_at is None else "",
            }
            for doc in ingested_documents
            if doc.updated_at is None
        ],
    }
    write_json(INGEST_REPORT_PATH, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest BUPT policy documents into airag knowledge data files")
    parser.add_argument("incoming_dir", type=Path, help="Directory containing category folders and document files")
    parser.add_argument("--manifest", type=Path, default=None, help="CSV manifest path; defaults to incoming_dir/document_manifest.csv")
    args = parser.parse_args()
    incoming_dir = args.incoming_dir.resolve()
    manifest_path = (args.manifest or incoming_dir / "document_manifest.csv").resolve()
    report = ingest(incoming_dir, manifest_path)
    print(f"Documents: {report['existing_documents_before']} -> {report['documents_after']}")
    print(f"Chunks: {report['existing_chunks_before']} -> {report['chunks_after']}")
    print(f"Failures: {report['failed_documents']}")
    print(f"Report: {INGEST_REPORT_PATH}")


if __name__ == "__main__":
    main()

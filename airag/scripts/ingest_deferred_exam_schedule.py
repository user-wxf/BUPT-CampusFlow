from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "airag" / "data"
RAW_DIR = DATA_ROOT / "raw" / "deferred_exam_schedule"
PROCESSED_DIR = DATA_ROOT / "processed" / "deferred_exam_schedule"
METADATA_PATH = DATA_ROOT / "metadata" / "documents.json"
CHUNKS_PATH = DATA_ROOT / "chunks" / "chunks.jsonl"
REPORT_PATH = DATA_ROOT / "metadata" / "deferred_exam_schedule_ingest_report.json"

DOCUMENT_ID = "deferred_exam_schedule_2025_2026_2"
SOURCE_TITLE = "附件1：2025-2026学年第二学期本科生期末考试补考、缓考安排表"
EXPECTED_COLUMNS = [
    "课程编号",
    "课程名称",
    "上课院系",
    "学生班级",
    "考试日期",
    "考试时间",
    "考场所在校区",
    "考场所在教学楼",
    "考试地点",
]


@dataclass
class ScheduleRecord:
    id: str
    academic_year: str | None
    semester: str | None
    course_code: str | None
    course_name: str | None
    offering_departments: str | None
    class_scope: str | None
    exam_date: str | None
    exam_time: str | None
    raw_exam_date: str | None
    raw_exam_time: str | None
    exam_campus: str | None
    teaching_building: str | None
    exam_location: str | None
    source: str
    source_file: str
    sheet_name: str
    source_row: int


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def parse_period_from_name(name: str) -> tuple[str | None, str | None]:
    match = re.search(r"(\d{4}-\d{4})学年第([一二三四五六七八九十]+)学期", name)
    if not match:
        return None, None
    return match.group(1), f"第{match.group(2)}学期"


def normalized_date(value: str) -> str | None:
    text = clean_cell(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None


def normalized_time(value: str) -> str | None:
    text = clean_cell(value)
    if re.fullmatch(r"\d{1,2}:\d{2}\s*[~\-－]\s*\d{1,2}:\d{2}", text):
        return re.sub(r"\s+", "", text).replace("-", "~").replace("－", "~")
    return None


def read_xls_with_win32com(path: Path) -> list[dict[str, Any]]:
    try:
        import win32com.client as win32  # type: ignore
    except ImportError as exc:
        raise RuntimeError("读取 .xls 需要 xlrd 或 Windows Excel COM；当前 Python 环境未安装 win32com。") from exc

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    workbook = excel.Workbooks.Open(str(path), ReadOnly=True)
    try:
        sheets: list[dict[str, Any]] = []
        for worksheet in workbook.Worksheets:
            used = worksheet.UsedRange
            rows = int(used.Rows.Count)
            cols = int(used.Columns.Count)
            values = []
            for row_number in range(1, rows + 1):
                row = []
                for col_number in range(1, cols + 1):
                    row.append(clean_cell(worksheet.Cells(row_number, col_number).Text))
                values.append(row)
            sheets.append({"name": worksheet.Name, "rows": rows, "cols": cols, "values": values})
        return sheets
    finally:
        workbook.Close(False)
        excel.Quit()


def read_xls(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore

        workbook = pd.ExcelFile(path)
        sheets = []
        for sheet_name in workbook.sheet_names:
            frame = workbook.parse(sheet_name=sheet_name, header=None, dtype=str).fillna("")
            sheets.append(
                {
                    "name": sheet_name,
                    "rows": int(frame.shape[0]),
                    "cols": int(frame.shape[1]),
                    "values": [[clean_cell(cell) for cell in row] for row in frame.values.tolist()],
                }
            )
        return sheets
    except Exception:
        return read_xls_with_win32com(path)


def load_documents() -> list[dict[str, Any]]:
    if not METADATA_PATH.exists():
        return []
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def load_chunks() -> list[dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        return []
    chunks = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def make_records(source_path: Path, raw_relative: str) -> tuple[list[ScheduleRecord], dict[str, Any]]:
    academic_year, semester = parse_period_from_name(source_path.name)
    sheets = read_xls(source_path)
    records: list[ScheduleRecord] = []
    sheet_summaries = []
    skipped_rows: list[dict[str, Any]] = []

    for sheet in sheets:
        values = sheet["values"]
        header = [clean_cell(cell) for cell in values[0]] if values else []
        sheet_summaries.append({"name": sheet["name"], "rows": sheet["rows"], "cols": sheet["cols"], "columns": header})
        if header[: len(EXPECTED_COLUMNS)] != EXPECTED_COLUMNS:
            raise RuntimeError(f"工作表 {sheet['name']} 列名不符合预期：{header}")

        for row_offset, row in enumerate(values[1:], start=2):
            mapped = {column: clean_cell(row[index]) if index < len(row) else "" for index, column in enumerate(EXPECTED_COLUMNS)}
            if not mapped["课程编号"] and not mapped["课程名称"]:
                skipped_rows.append({"sheet": sheet["name"], "row": row_offset, "reason": "empty course code and name"})
                continue
            record_index = len(records) + 1
            raw_date = mapped["考试日期"] or None
            raw_time = mapped["考试时间"] or None
            records.append(
                ScheduleRecord(
                    id=f"{DOCUMENT_ID}_{record_index:03d}",
                    academic_year=academic_year,
                    semester=semester,
                    course_code=mapped["课程编号"] or None,
                    course_name=mapped["课程名称"] or None,
                    offering_departments=mapped["上课院系"] or None,
                    class_scope=mapped["学生班级"] or None,
                    exam_date=normalized_date(mapped["考试日期"]),
                    exam_time=normalized_time(mapped["考试时间"]),
                    raw_exam_date=raw_date,
                    raw_exam_time=raw_time,
                    exam_campus=mapped["考场所在校区"] or None,
                    teaching_building=mapped["考场所在教学楼"] or None,
                    exam_location=mapped["考试地点"] or None,
                    source=SOURCE_TITLE,
                    source_file=raw_relative,
                    sheet_name=str(sheet["name"]),
                    source_row=row_offset,
                )
            )
    return records, {"sheets": sheet_summaries, "skipped_rows": skipped_rows}


def display(value: str | None) -> str:
    return value if value else "未提供"


def record_content(record: ScheduleRecord) -> str:
    date_text = record.exam_date or record.raw_exam_date
    time_text = record.exam_time or record.raw_exam_time
    return "\n".join(
        [
            f"资料类型：2025-2026学年第二学期本科生期末考试补考、缓考安排。",
            f"课程名称：{display(record.course_name)}",
            f"课程代码：{display(record.course_code)}",
            f"考试日期：{display(date_text)}",
            f"考试时间：{display(time_text)}",
            f"适用班级：{display(record.class_scope)}",
            f"上课院系：{display(record.offering_departments)}",
            f"考场所在校区：{display(record.exam_campus)}",
            f"考场所在教学楼：{display(record.teaching_building)}",
            f"考试地点：{display(record.exam_location)}",
            f"来源定位：{record.sheet_name} 第{record.source_row}行。",
        ]
    )


def build_chunks(records: list[ScheduleRecord]) -> list[dict[str, Any]]:
    chunks = []
    for record in records:
        period = ""
        if record.academic_year and record.semester:
            period = f"{record.academic_year}学年{record.semester}"
        chunks.append(
            {
                "chunk_id": record.id,
                "document_id": DOCUMENT_ID,
                "service": "缓考申请",
                "college": "all",
                "grade": "all",
                "education_level": "本科",
                "campus": "all",
                "title": f"{period}《{record.course_name or '未命名课程'}》补考/缓考安排",
                "content": record_content(record),
                "source": SOURCE_TITLE,
                "updated_at": None,
                "status": "active",
                "source_file": record.source_file,
                "source_pages": f"{record.sheet_name} 第{record.source_row}行",
            }
        )
    return chunks


def ingest(source_path: Path) -> dict[str, Any]:
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    raw_path = RAW_DIR / source_path.name
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, raw_path)
    raw_relative = str(raw_path.relative_to(REPO_ROOT)).replace("\\", "/")

    records, workbook_info = make_records(source_path, raw_relative)
    records_payload = [asdict(record) for record in records]
    processed_jsonl = PROCESSED_DIR / f"{DOCUMENT_ID}.jsonl"
    write_jsonl(processed_jsonl, records_payload)

    documents_before = load_documents()
    chunks_before = load_chunks()
    existing_documents = [doc for doc in documents_before if doc.get("id") != DOCUMENT_ID]
    existing_chunks = [chunk for chunk in chunks_before if chunk.get("document_id") != DOCUMENT_ID]

    document_record = {
        "id": DOCUMENT_ID,
        "service": "缓考申请",
        "college": "all",
        "grade": "all",
        "education_level": "本科",
        "campus": "all",
        "source": SOURCE_TITLE,
        "updated_at": None,
        "status": "active",
        "file": raw_relative,
    }
    new_chunks = build_chunks(records)
    documents_after = existing_documents + [document_record]
    chunks_after = existing_chunks + new_chunks

    write_json(METADATA_PATH, documents_after)
    write_jsonl(CHUNKS_PATH, chunks_after)

    report = {
        "source": str(source_path),
        "raw_file": raw_relative,
        "processed_file": str(processed_jsonl.relative_to(REPO_ROOT)).replace("\\", "/"),
        "document_id": DOCUMENT_ID,
        "source_title": SOURCE_TITLE,
        "workbook": workbook_info,
        "records_total": len(records),
        "records_parsed": len(records_payload),
        "documents_before": len(documents_before),
        "documents_after": len(documents_after),
        "chunks_before": len(chunks_before),
        "chunks_after": len(chunks_after),
        "new_chunks": len(new_chunks),
        "sample_records": records_payload[:5],
    }
    write_json(REPORT_PATH, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest BUPT deferred exam schedule .xls into airag data")
    parser.add_argument("source", type=Path, help="Path to the original .xls schedule")
    args = parser.parse_args()
    report = ingest(args.source.resolve())
    print(f"Sheets: {len(report['workbook']['sheets'])}")
    print(f"Records: {report['records_parsed']}")
    print(f"Documents: {report['documents_before']} -> {report['documents_after']}")
    print(f"Chunks: {report['chunks_before']} -> {report['chunks_after']}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

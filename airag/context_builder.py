from typing import Any


PROFILE_FIELDS = ("college", "grade", "education_level", "campus")
AFFAIR_FIELDS = (
    "id",
    "title",
    "description",
    "materials",
    "steps",
    "location",
    "room",
    "contact",
    "office_hours",
    "sources",
    "eligibility",
)


def build_context(
    question: str,
    profile: dict[str, str],
    retrieved_chunks: list[dict[str, Any]],
    affairs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "user_question": question,
        "user_profile": {field: str(profile.get(field) or "") for field in PROFILE_FIELDS},
        "retrieved_knowledge": [
            {
                "chunk_id": chunk.get("chunk_id"),
                "title": chunk.get("title"),
                "content": chunk.get("content"),
                "source": chunk.get("source"),
                "source_pages": chunk.get("source_pages"),
                "metadata": {
                    "document_id": chunk.get("document_id"),
                    "service": chunk.get("service"),
                    "college": chunk.get("college"),
                    "grade": chunk.get("grade"),
                    "education_level": chunk.get("education_level"),
                    "campus": chunk.get("campus"),
                    "status": chunk.get("status"),
                },
            }
            for chunk in retrieved_chunks
        ],
        "structured_affairs": [
            {field: affair.get(field) for field in AFFAIR_FIELDS if field in affair}
            for affair in affairs
        ],
    }


def context_to_text(context: dict[str, Any]) -> str:
    lines = ["## User Question", str(context["user_question"]), "", "## User Profile"]
    for key, value in context["user_profile"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Retrieved Knowledge"])
    for index, chunk in enumerate(context["retrieved_knowledge"], start=1):
        lines.append(f"{index}. [{chunk['chunk_id']}] {chunk['title']}")
        lines.append(f"   Source: {chunk['source']} / {chunk['source_pages']}")
        lines.append(f"   Content: {chunk['content']}")
    lines.extend(["", "## Structured Affairs"])
    for index, affair in enumerate(context["structured_affairs"], start=1):
        lines.append(f"{index}. {affair.get('title') or affair.get('id')}")
        for field in AFFAIR_FIELDS:
            if field in affair and field != "title":
                lines.append(f"   {field}: {affair[field]}")
    return "\n".join(lines)

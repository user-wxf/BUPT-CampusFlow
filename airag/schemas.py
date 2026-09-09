from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Profile(StrictModel):
    college: str = Field(default="", max_length=100)
    grade: str = Field(default="", max_length=30)
    education_level: str = Field(default="", max_length=30)
    campus: str = Field(default="", max_length=100)


class Source(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    reference: str = Field(min_length=1, max_length=1000)


class GenerateRequest(StrictModel):
    question: str = Field(min_length=1, max_length=2000)
    profile: Profile = Field(default_factory=Profile)
    affairs: list[dict] = Field(default_factory=list)


class Plan(StrictModel):
    affair_id: int | None = None
    title: str
    materials: list[str]
    steps: list[str]
    location: str
    room: str
    contact: str
    office_hours: str
    sources: list[Source]


class QueryResult(StrictModel):
    answer: str
    plans: list[Plan]
    sources: list[Source]
    warnings: list[str] = Field(default_factory=list)
    mode: Literal["rag"]

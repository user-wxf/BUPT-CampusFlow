from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL_PATTERN = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Credentials(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    username: str = Field(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(min_length=8, max_length=128)


class ProfileInput(StrictModel):
    college: str = Field(default='', max_length=100)
    grade: str = Field(default='', max_length=30)
    education_level: str = Field(default='', max_length=30)
    campus: str = Field(default='', max_length=100)
    email: str = Field(default='', max_length=254)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        import re
        email = value.strip()
        if email and not re.match(EMAIL_PATTERN, email):
            raise ValueError('邮箱格式不正确')
        return email


class Source(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    reference: str = Field(min_length=1, max_length=1000)


class AffairInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=10000)
    location: str = Field(default='', max_length=200)
    room: str = Field(default='', max_length=100)
    contact: str = Field(default='', max_length=100)
    office_hours: str = Field(default='', max_length=200)
    materials: list[str] = Field(default_factory=list, max_length=100)
    steps: list[str] = Field(default_factory=list, max_length=100)
    sources: list[Source] = Field(default_factory=list, max_length=100)
    eligibility: dict[Literal['college', 'grade', 'education_level', 'campus'], list[str]] = Field(default_factory=dict)


class TodoInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default='', max_length=5000)
    completed: bool = False
    due_at: datetime | None = None


class QueryInput(StrictModel):
    question: str = Field(min_length=1, max_length=2000)
    affair_id: int | None = Field(default=None, gt=0)


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
    mode: Literal['demo', 'rag']

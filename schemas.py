from pydantic import BaseModel
from datetime import date


class UniversityCreate(BaseModel):
    name: str
    city: str
    university_type: str
    website: str | None = None


class ReviewCreate(BaseModel):
    university_id: int
    review_text: str
    source: str | None = None
    review_date: date | None = None


class AskRequest(BaseModel):
    question: str
    university_name: str | None = None


class CompareRequest(BaseModel):
    question: str
    university_names: list[str]
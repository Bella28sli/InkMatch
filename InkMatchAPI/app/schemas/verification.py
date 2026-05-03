from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class VerificationPersonalDataIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)
    second_name: str | None = Field(default=None, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    patronymic: str | None = Field(default=None, max_length=64)
    birth_date: date
    citizenship: str | None = Field(default=None, max_length=64)


class VerificationPersonalDataOut(BaseModel):
    first_name: str
    second_name: str | None = None
    last_name: str
    patronymic: str | None = None
    birth_date: date
    citizenship: str | None = None


class VerificationDocumentOut(BaseModel):
    id: UUID
    document_id: UUID
    document_type: str
    title: str | None = None
    issuer: str | None = None
    issued_date: date | None = None
    file_url: str
    file_type: str
    created_at: str


class VerificationRequestOut(BaseModel):
    request_id: UUID | None = None
    status: str
    comments: str | None = None
    rejection_reason: str | None = None
    submitted_at: str | None = None
    reviewed_at: str | None = None
    personal_data: VerificationPersonalDataOut | None = None
    documents: list[VerificationDocumentOut] = []

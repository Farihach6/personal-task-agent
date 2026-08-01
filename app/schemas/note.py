"""Pydantic request/response schemas for the Notes API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NoteCreate(BaseModel):
    """Payload for creating a new note."""

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)

    @field_validator("title", "content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class NoteUpdate(BaseModel):
    """Payload for updating an existing note; at least one field is required."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)

    @field_validator("title", "content")
    @classmethod
    def not_blank_if_provided(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self) -> "NoteUpdate":
        if self.title is None and self.content is None:
            raise ValueError("at least one of title or content must be provided")
        return self


class NoteResponse(BaseModel):
    """A single note as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    """A paginated page of notes."""

    items: list[NoteResponse]
    total: int
    limit: int
    offset: int
"""Pydantic request/response schemas for the /chat endpoint."""

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Payload for sending a message to the agent."""

    message: str = Field(..., min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value
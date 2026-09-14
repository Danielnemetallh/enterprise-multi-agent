"""Typed model boundary for LLM-generated resolution proposals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.tools.llm import extract_json


class ProposalValidationError(ValueError):
    """Raised when a provider response is not a safe resolution proposal."""


class ProviderFailure(RuntimeError):
    """Raised when the configured model provider cannot respond safely."""


class ResolutionProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action_type: Literal[
        "offer_discount",
        "send_apology",
        "provide_information",
        "process_cancellation",
    ]
    discount_percent: float = Field(ge=0, le=30, allow_inf_nan=False)
    subject: str = Field(min_length=1, max_length=120)
    customer_message: str = Field(min_length=1, max_length=1000)
    business_reason: str | None = Field(default=None, max_length=500)
    alternatives: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("subject", "customer_message")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


def parse_resolution_proposal(text: str) -> dict:
    try:
        payload = extract_json(text)
        return ResolutionProposal.model_validate(payload).model_dump()
    except (ValidationError, ValueError) as exc:
        raise ProposalValidationError(f"Invalid resolution proposal: {exc}") from exc

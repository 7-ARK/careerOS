"""Structured contracts for optional LLM resume-quality output."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SupportLevel = Literal["supported", "weakly_supported", "unsupported"]


class LLMSkillGroup(BaseModel):
    """Skill group proposed by the LLM."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    skills: list[str] = Field(default_factory=list)


class LLMProjectDecision(BaseModel):
    """Project selection or exclusion explanation."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(min_length=1, max_length=250)
    reason: str = Field(min_length=1, max_length=350)
    support_level: SupportLevel = "supported"
    relevance_score: int | None = Field(default=None, ge=0, le=100)


class LLMResumeStrategyNote(BaseModel):
    """A classified resume-strategy recommendation."""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=350)
    support_level: SupportLevel


class LLMResumeQualityOutput(BaseModel):
    """Validated optional OpenAI response for resume quality improvement."""

    model_config = ConfigDict(extra="forbid")

    professional_summary: str = Field(min_length=1, max_length=900)
    skill_groups: list[LLMSkillGroup] = Field(default_factory=list)
    selected_projects: list[LLMProjectDecision] = Field(default_factory=list)
    excluded_projects: list[LLMProjectDecision] = Field(default_factory=list)
    resume_strategy_notes: list[LLMResumeStrategyNote] = Field(default_factory=list)
    truthfulness_warnings: list[str] = Field(default_factory=list)
    cloud_certification_notes: list[str] = Field(default_factory=list)

    @field_validator("truthfulness_warnings", "cloud_certification_notes")
    @classmethod
    def clean_notes(cls, values: list[str]) -> list[str]:
        """Drop empty notes and keep the result compact."""
        return [value.strip() for value in values if value.strip()][:10]

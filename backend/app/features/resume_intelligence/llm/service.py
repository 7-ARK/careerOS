"""Optional OpenAI-backed resume-quality layer with deterministic fallback."""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.clients.openai_client import OpenAIResumeClient
from app.core.config import Settings
from app.features.resume_intelligence.llm.prompts import LLM_RESUME_QUALITY_SYSTEM_PROMPT
from app.features.resume_intelligence.llm.schemas import (
    LLMProjectDecision,
    LLMResumeQualityOutput,
)
from app.features.resume_intelligence.quality import (
    DeterministicResumeQualityEngine,
    ProjectSelection,
    ResumeQualityResult,
)
from app.models import CandidateProfile, JobAnalysis, ResumeAnalysis


class JSONResumeClient(Protocol):
    """Client protocol for tests and future provider adapters."""

    def create_json_response(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a JSON-compatible response."""


class LLMResumeQualityService:
    """Improve deterministic resume quality when LLM mode is explicitly enabled."""

    fallback_warning = "LLM resume intelligence failed; deterministic fallback was used."
    missing_key_warning = (
        "LLM resume intelligence is enabled but OPENAI_API_KEY is missing; "
        "deterministic fallback was used."
    )

    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str | None,
        model: str,
        deterministic_engine: DeterministicResumeQualityEngine | None = None,
        client: JSONResumeClient | None = None,
    ) -> None:
        """Build an injectable optional LLM layer."""
        self.enabled = enabled
        self.api_key = api_key
        self.model = model
        self.deterministic_engine = deterministic_engine or DeterministicResumeQualityEngine()
        self.client = client

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        deterministic_engine: DeterministicResumeQualityEngine | None = None,
    ) -> LLMResumeQualityService:
        """Create a service from environment-backed runtime settings."""
        runtime_settings = settings or Settings.from_env()
        return cls(
            enabled=runtime_settings.use_llm_resume_intelligence,
            api_key=runtime_settings.openai_api_key,
            model=runtime_settings.openai_model,
            deterministic_engine=deterministic_engine,
        )

    def select_projects(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        *,
        limit: int = 3,
    ) -> ProjectSelection:
        """Expose deterministic project selection for stable orchestration."""
        return self.deterministic_engine.select_projects(candidate, job_analysis, limit=limit)

    def build(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        *,
        project_limit: int = 3,
    ) -> ResumeQualityResult:
        """Return LLM-enhanced quality output or deterministic fallback."""
        deterministic = self.deterministic_engine.build(
            candidate,
            job_analysis,
            analysis,
            project_limit=project_limit,
        )
        if not self.enabled:
            return deterministic
        if not self.api_key:
            return deterministic.with_warnings([self.missing_key_warning])
        try:
            output = self._call_llm(candidate, job_analysis, analysis, deterministic)
        except Exception as exc:
            return deterministic.with_warnings([f"{self.fallback_warning} Reason: {exc}"])
        return self._merge_output(candidate, deterministic, output)

    def _call_llm(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        deterministic: ResumeQualityResult,
    ) -> LLMResumeQualityOutput:
        """Call the configured LLM client and validate the result."""
        client = self.client or OpenAIResumeClient(api_key=self.api_key or "", model=self.model)
        return LLMResumeQualityOutput.model_validate(
            client.create_json_response(
                system_prompt=LLM_RESUME_QUALITY_SYSTEM_PROMPT,
                payload=self._payload(candidate, job_analysis, analysis, deterministic),
            )
        )

    def _merge_output(
        self,
        candidate: CandidateProfile,
        deterministic: ResumeQualityResult,
        output: LLMResumeQualityOutput,
    ) -> ResumeQualityResult:
        """Use only validated candidate-supported LLM content."""
        candidate_skills = {skill.name.casefold(): skill.name for skill in candidate.skills}
        known_project_names = {
            project.title.casefold(): project.title for project in candidate.projects
        }
        skill_groups = []
        for group in output.skill_groups:
            supported_skills = [
                candidate_skills[skill.casefold()]
                for skill in group.skills
                if skill.casefold() in candidate_skills
            ]
            if supported_skills:
                skill_groups.append(
                    {"category": group.name, "skills": _deduplicate(supported_skills)}
                )
        selected_reason_by_title = self._project_reasons(
            output.selected_projects,
            known_project_names,
        )
        excluded_reason_by_title = self._project_reasons(
            output.excluded_projects,
            known_project_names,
        )
        projects_section = [
            {
                **project,
                "selection_reason": selected_reason_by_title.get(
                    str(project.get("title", "")).casefold(),
                    project.get("selection_reason"),
                ),
            }
            for project in deterministic.projects_section
        ]
        selected_projects = [
            {
                **project,
                "reason": selected_reason_by_title.get(
                    str(project.get("title", "")).casefold(),
                    project.get("reason", ""),
                ),
            }
            for project in deterministic.selected_projects
        ]
        excluded_projects = [
            {
                **project,
                "reason": excluded_reason_by_title.get(
                    str(project.get("title", "")).casefold(),
                    project.get("reason", ""),
                ),
            }
            for project in deterministic.excluded_projects
        ]
        unsupported_notes = [
            note.note
            for note in output.resume_strategy_notes
            if note.support_level == "unsupported"
        ]
        summary, summary_warning = self._safe_summary(
            output.professional_summary,
            deterministic.summary,
        )
        warnings = [
            *output.truthfulness_warnings,
            *output.cloud_certification_notes,
            *unsupported_notes,
        ]
        if summary_warning:
            warnings.append(summary_warning)
        return ResumeQualityResult(
            summary=summary,
            skills_section=skill_groups or deterministic.skills_section,
            projects_section=projects_section,
            selected_projects=selected_projects,
            excluded_projects=excluded_projects,
            warnings=[*deterministic.warnings, *_deduplicate(warnings)],
            include_additional_experience=deterministic.include_additional_experience,
        )

    @staticmethod
    def _safe_summary(candidate_summary: str, fallback_summary: str) -> tuple[str, str | None]:
        """Reject common unsupported production overclaims from LLM summaries."""
        lowered = candidate_summary.casefold()
        unsafe_patterns = (
            "production gcp deployment",
            "production vertex ai",
            "production ai agents",
            "built production agents",
            "managed production gcp",
        )
        if any(pattern in lowered for pattern in unsafe_patterns):
            return (
                fallback_summary,
                "LLM summary included an unsupported production claim and was not used.",
            )
        return candidate_summary, None

    @staticmethod
    def _payload(
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        deterministic: ResumeQualityResult,
    ) -> dict[str, Any]:
        """Build a privacy-scoped structured prompt payload."""
        job_description = getattr(job_analysis, "job_description", None)
        return {
            "candidate_profile": {
                "full_name": candidate.full_name,
                "headline": candidate.headline,
                "summary": candidate.summary,
                "location": candidate.location,
            },
            "candidate_skills": [
                {"name": skill.name, "category": skill.category} for skill in candidate.skills
            ],
            "candidate_projects": [
                {
                    "title": project.title,
                    "description": project.description,
                    "technologies": project.technologies,
                    "outcomes": project.outcomes,
                }
                for project in candidate.projects
            ],
            "candidate_experience": [
                {
                    "company": experience.company,
                    "job_title": experience.job_title,
                    "description": experience.description,
                    "achievements": experience.achievements,
                }
                for experience in candidate.work_experiences
            ],
            "candidate_education": [
                {
                    "institution": education.institution,
                    "degree": education.degree,
                    "field_of_study": education.field_of_study,
                    "description": education.description,
                }
                for education in candidate.education
            ],
            "candidate_certifications": [
                {
                    "name": certification.name,
                    "issuing_organization": certification.issuing_organization,
                    "credential_id": certification.credential_id,
                }
                for certification in candidate.certifications
            ],
            "job": {
                "title": job_analysis.normalized_title,
                "company": getattr(job_description, "company_name", None),
                "description": getattr(job_description, "description_text", None),
                "required_skills": job_analysis.required_skills,
                "preferred_skills": job_analysis.preferred_skills,
                "required_technologies": job_analysis.required_technologies,
                "preferred_technologies": job_analysis.preferred_technologies,
                "ats_keywords": job_analysis.ats_keywords,
                "domain_keywords": job_analysis.domain_keywords,
            },
            "rule_based_review": {
                "matched_skills": analysis.matched_skills,
                "missing_skills": analysis.missing_skills,
                "matched_technologies": analysis.matched_technologies,
                "missing_technologies": analysis.missing_technologies,
                "warnings": analysis.truthfulness_warnings,
                "selected_projects": deterministic.selected_projects,
                "excluded_projects": deterministic.excluded_projects,
            },
        }

    @staticmethod
    def _project_reasons(
        decisions: list[LLMProjectDecision],
        known_project_names: dict[str, str],
    ) -> dict[str, str]:
        """Return reasons for supported/weakly-supported known candidate projects."""
        reasons = {}
        for decision in decisions:
            key = decision.project_name.casefold()
            if key in known_project_names and decision.support_level != "unsupported":
                reasons[key] = decision.reason
        return reasons


def _deduplicate(values: list[str]) -> list[str]:
    """Deduplicate strings case-insensitively while preserving order."""
    seen: set[str] = set()
    result = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result

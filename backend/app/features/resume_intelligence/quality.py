"""Deterministic resume-quality shaping for recruiter-readable drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import CandidateProfile, JobAnalysis, Project, ResumeAnalysis

DEFAULT_PROJECT_LIMIT = 3
MAX_PROJECT_LIMIT = 4
MAX_PROJECT_BULLETS = 4
MAX_SKILLS = 18

SKILL_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Languages", ("python", "sql")),
    ("Backend", ("fastapi", "postgresql", "api", "apis", "microservices")),
    (
        "AI / Machine Learning",
        (
            "machine learning",
            "deep learning",
            "neural networks",
            "computer vision",
            "reinforcement learning",
            "vertex ai",
            "bigquery ml",
            "google cloud",
            "openai api",
            "langchain",
            "langgraph",
            "rag",
            "mlops",
        ),
    ),
    ("Automation", ("automation", "playwright", "selenium", "webhooks", "make", "zapier", "n8n")),
    ("Developer Tools", ("git", "github", "docker", "devops basics", "dataops")),
)


@dataclass(frozen=True, slots=True)
class ProjectScore:
    """Project relevance score and explanation."""

    project: Project
    score: int
    matched_terms: list[str]

    @property
    def reason(self) -> str:
        """Return a concise deterministic explanation."""
        if self.matched_terms:
            return f"Matched {', '.join(self.matched_terms[:4])}."
        return "Excluded because lower relevance score."


@dataclass(frozen=True, slots=True)
class ProjectSelection:
    """Selected and excluded project scores."""

    selected: list[ProjectScore]
    excluded: list[ProjectScore]


@dataclass(frozen=True, slots=True)
class ResumeQualityResult:
    """Structured quality output used to create a cleaner resume draft."""

    summary: str
    skills_section: list[dict[str, object]]
    projects_section: list[dict[str, object]]
    selected_projects: list[dict[str, object]]
    excluded_projects: list[dict[str, object]]
    warnings: list[str]
    include_additional_experience: bool

    def with_warnings(self, warnings: list[str]) -> ResumeQualityResult:
        """Return a copy with additional frontend-only warnings."""
        return ResumeQualityResult(
            summary=self.summary,
            skills_section=self.skills_section,
            projects_section=self.projects_section,
            selected_projects=self.selected_projects,
            excluded_projects=self.excluded_projects,
            warnings=[*self.warnings, *warnings],
            include_additional_experience=self.include_additional_experience,
        )


class DeterministicResumeQualityEngine:
    """Improve resume draft quality using only local candidate and job evidence."""

    def build(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        *,
        project_limit: int = DEFAULT_PROJECT_LIMIT,
    ) -> ResumeQualityResult:
        """Build quality-shaped sections for one candidate-job pair."""
        selection = self.select_projects(candidate, job_analysis, limit=project_limit)
        skills = self.group_skills(candidate, analysis, selection)
        return ResumeQualityResult(
            summary=self.summary(candidate, job_analysis, analysis, selection),
            skills_section=skills,
            projects_section=[
                self._project_entry(score, candidate) for score in selection.selected
            ],
            selected_projects=[
                self._project_review(score, selected=True) for score in selection.selected
            ],
            excluded_projects=[
                self._project_review(score, selected=False) for score in selection.excluded
            ],
            warnings=[],
            include_additional_experience=self._should_include_additional_experience(
                candidate,
                selection,
            ),
        )

    def select_projects(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        *,
        limit: int = DEFAULT_PROJECT_LIMIT,
    ) -> ProjectSelection:
        """Rank candidate projects and select only the strongest projects."""
        bounded_limit = max(1, min(limit, MAX_PROJECT_LIMIT))
        scores = [self.score_project(project, job_analysis) for project in candidate.projects]
        scores.sort(key=lambda item: (-item.score, item.project.title.casefold()))
        selected = scores[:bounded_limit]
        excluded = scores[bounded_limit:]
        return ProjectSelection(selected=selected, excluded=excluded)

    def score_project(self, project: Project, job_analysis: JobAnalysis) -> ProjectScore:
        """Score one project by deterministic overlap with the target job."""
        project_text = _normalize(
            " ".join(
                [
                    project.title,
                    project.description,
                    *project.technologies,
                    *project.outcomes,
                ]
            )
        )
        job_title_text = _normalize(job_analysis.normalized_title)
        weighted_terms = [
            *((term, 10) for term in job_analysis.required_skills),
            *((term, 10) for term in job_analysis.required_technologies),
            *((term, 6) for term in job_analysis.preferred_skills),
            *((term, 6) for term in job_analysis.preferred_technologies),
            *((term, 4) for term in job_analysis.ats_keywords),
            *((term, 3) for term in job_analysis.domain_keywords),
        ]
        matched_terms: list[str] = []
        score = 0
        seen: set[str] = set()
        for term, weight in weighted_terms:
            key = _normalize(term)
            if key and key not in seen and key in project_text:
                seen.add(key)
                matched_terms.append(term)
                score += weight
        title_tokens = {token for token in job_title_text.split() if len(token) >= 3}
        score += 5 * len(title_tokens.intersection(project_text.split()))
        score += self._theme_boost(job_title_text, project_text)
        return ProjectScore(project=project, score=score, matched_terms=matched_terms)

    def group_skills(
        self,
        candidate: CandidateProfile,
        analysis: ResumeAnalysis,
        selection: ProjectSelection,
    ) -> list[dict[str, object]]:
        """Create grouped, ATS-readable skills ordered by relevance."""
        selected_project_terms = {
            _normalize(term) for score in selection.selected for term in score.project.technologies
        }
        matched_terms = {
            _normalize(term)
            for term in [
                *analysis.matched_skills,
                *analysis.matched_technologies,
                *analysis.matched_keywords,
            ]
        }
        ranked_skills = sorted(
            candidate.skills,
            key=lambda skill: (
                _normalize(skill.name) not in matched_terms,
                _normalize(skill.name) not in selected_project_terms,
                skill.category.casefold(),
                skill.name.casefold(),
            ),
        )
        grouped: list[dict[str, object]] = []
        used: set[str] = set()
        for group_name, aliases in SKILL_GROUPS:
            values = []
            for skill in ranked_skills:
                key = _normalize(skill.name)
                if key in used:
                    continue
                if _skill_matches_group(key, aliases):
                    values.append(skill.name)
                    used.add(key)
                if len(used) >= MAX_SKILLS:
                    break
            if values:
                grouped.append({"category": group_name, "skills": _deduplicate(values)})
            if len(used) >= MAX_SKILLS:
                break
        return grouped

    def summary(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        selection: ProjectSelection,
    ) -> str:
        """Create a deterministic job-tailored summary without unsupported claims."""
        role = job_analysis.normalized_title or candidate.headline or "AI Engineer"
        project_themes = self._project_themes(selection.selected)
        terms = _deduplicate(
            [*analysis.matched_technologies, *analysis.matched_skills, *analysis.matched_keywords]
        )[:5]
        role_prefix = _early_career_role(role)
        certification_sentence = self._certification_sentence(candidate)
        if terms:
            term_text = ", ".join(terms)
            return (
                f"{role_prefix} with hands-on project experience building {project_themes}. "
                f"Experienced with {term_text}.{certification_sentence}"
            )
        return (
            f"{role_prefix} with hands-on project experience building {project_themes}."
            f"{certification_sentence}"
        )

    @staticmethod
    def _theme_boost(job_title_text: str, project_text: str) -> int:
        """Boost project-job thematic overlap without ML or embeddings."""
        boost = 0
        themes = {
            "ai": ("ai", "machine learning", "llm", "agent", "automation", "workflow"),
            "automation": ("automation", "workflow", "webhook", "playwright"),
            "backend": ("api", "fastapi", "postgresql", "backend"),
            "mlops": ("mlops", "docker", "cloud", "vertex", "sagemaker"),
        }
        for title_token, project_terms in themes.items():
            if title_token in job_title_text and any(
                term in project_text for term in project_terms
            ):
                boost += 12
        if "engineer" in job_title_text and any(
            term in project_text for term in ("system", "backend", "workflow", "platform")
        ):
            boost += 6
        return boost

    @staticmethod
    def _project_themes(selected: list[ProjectScore]) -> str:
        """Summarize selected project evidence in compact recruiter language."""
        text = " ".join(score.project.title.lower() for score in selected)
        if "career" in text and "workflow" in text:
            return (
                "Python automation systems, FastAPI backends, job extraction workflows, "
                "and career automation products"
            )
        if "workflow" in text:
            return "workflow automation tools, API-based systems, and backend services"
        if "ocr" in text or "document" in text:
            return "document-processing platforms and backend services"
        return "Python-based backend systems and automation tools"

    @staticmethod
    def _certification_sentence(candidate: CandidateProfile) -> str:
        """Mention cloud ML certification evidence without implying production work."""
        evidence_text = " ".join(
            value
            for certification in candidate.certifications
            for value in (
                certification.name,
                certification.issuing_organization,
                certification.credential_id or "",
            )
        ).casefold()
        if not any(term in evidence_text for term in ("google cloud", "vertex ai", "bigquery ml")):
            return ""
        return (
            " Certified in Google Cloud machine learning coursework with exposure to "
            "Vertex AI, BigQuery ML, MLOps, and production ML concepts."
        )

    @staticmethod
    def _should_include_additional_experience(
        candidate: CandidateProfile,
        selection: ProjectSelection,
    ) -> bool:
        """Include short non-engineering experience only when the draft remains compact."""
        if len(selection.selected) > DEFAULT_PROJECT_LIMIT:
            return False
        return any(
            _is_additional_experience(experience.job_title, experience.company)
            for experience in candidate.work_experiences
        )

    @staticmethod
    def _project_entry(score: ProjectScore, candidate: CandidateProfile) -> dict[str, object]:
        """Convert one selected project into a compact draft entry."""
        project = score.project
        return {
            "source_id": str(project.id),
            "title": project.title,
            "description": project.description,
            "technologies": _deduplicate(project.technologies)[:8],
            "outcomes": _prioritize_bullets(project.outcomes),
            "github_url": _specific_link(project.github_url, candidate),
            "portfolio_url": _specific_link(project.portfolio_url, candidate),
            "relevance_score": score.score,
            "selection_reason": score.reason,
        }

    @staticmethod
    def _project_review(score: ProjectScore, *, selected: bool) -> dict[str, object]:
        """Return frontend/API project selection review metadata."""
        return {
            "title": score.project.title,
            "score": score.score,
            "reason": score.reason if selected else "Excluded because lower relevance score.",
        }


def _specific_link(value: str | None, candidate: CandidateProfile) -> str | None:
    """Remove repeated generic profile links from project entries."""
    if not value:
        return None
    normalized = value.rstrip("/").casefold()
    generic_links = {
        (candidate.portfolio_url or "").rstrip("/").casefold(),
        "https://github.com/7-ark",
    }
    return None if normalized in generic_links else value


def _early_career_role(role: str) -> str:
    """Create a human summary opening without senior overclaiming."""
    clean_role = role.replace("Senior ", "").replace("Lead ", "")
    if "early" in clean_role.casefold():
        return clean_role
    return f"Early-career {clean_role}"


def _is_additional_experience(job_title: str, company: str) -> bool:
    """Detect real non-engineering business/tutoring experience."""
    text = f"{job_title} {company}".casefold()
    return any(term in text for term in ("tutor", "tutoring", "ignite learning", "learning"))


def _prioritize_bullets(values: list[str]) -> list[str]:
    """Keep concise, non-duplicate outcome bullets."""
    unique = _deduplicate([value for value in values if value])
    unique.sort(
        key=lambda value: (
            not any(
                term in value.casefold()
                for term in ("built", "generated", "tracked", "automated", "extracted")
            ),
            len(value),
        )
    )
    return unique[:MAX_PROJECT_BULLETS]


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


def _skill_matches_group(key: str, aliases: tuple[str, ...]) -> bool:
    """Match skills to groups without broad tokens stealing specific skills."""
    for alias in aliases:
        if alias in {"api", "apis"}:
            if key in {"api", "apis"}:
                return True
            continue
        if alias in {"git"}:
            if key == alias:
                return True
            continue
        if alias in key or key in alias:
            return True
    return False


def _normalize(value: str) -> str:
    """Normalize text for deterministic overlap checks."""
    normalized = value.lower()
    replacements = {
        "apis": "api",
        "workflows": "workflow",
        "technologies": "technology",
        "google cloud ai": "google cloud",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"[^a-z0-9+#.]+", " ", normalized).strip()

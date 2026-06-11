"""Deterministic resume-quality shaping for recruiter-readable drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.models import CandidateProfile, JobAnalysis, Project, ResumeAnalysis

RoleKind = Literal["legal_ai", "ai_automation", "backend_python", "machine_learning", "general"]

DEFAULT_PROJECT_LIMIT = 3
MAX_PROJECT_LIMIT = 4
NORMAL_PROJECT_LIMIT = 3
MAX_PROJECT_BULLETS = 3
MAX_SKILLS = 16
MAX_SKILL_GROUPS = 5

SKILL_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Languages", ("python", "sql")),
    ("Backend", ("fastapi", "api", "apis", "microservices", "backend architecture")),
    ("Databases", ("postgresql", "database", "databases")),
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
            "langchain",
            "langgraph",
            "rag",
            "mlops",
        ),
    ),
    (
        "Cloud / MLOps",
        ("google cloud", "vertex ai", "bigquery ml", "mlops", "sagemaker", "azure ml"),
    ),
    (
        "Document AI / Extraction",
        (
            "ocr",
            "document extraction",
            "structured extraction",
            "structured data extraction",
            "validation",
            "legal technology",
            "document review",
        ),
    ),
    (
        "Automation",
        (
            "automation",
            "playwright",
            "selenium",
            "webhooks",
            "webhook",
            "make",
            "zapier",
            "n8n",
            "workflow automation",
            "resume automation",
            "job extraction",
            "document generation",
        ),
    ),
    ("Developer Tools", ("git", "github", "docker", "devops basics", "dataops")),
)

ROLE_SKILL_ORDER: dict[RoleKind, tuple[str, ...]] = {
    "legal_ai": (
        "Languages",
        "Backend",
        "Document AI / Extraction",
        "Databases",
        "Automation",
    ),
    "ai_automation": (
        "Languages",
        "Backend",
        "Automation",
        "AI / Machine Learning",
        "Developer Tools",
    ),
    "backend_python": (
        "Languages",
        "Backend",
        "Databases",
        "Developer Tools",
        "Automation",
    ),
    "machine_learning": (
        "Languages",
        "AI / Machine Learning",
        "Cloud / MLOps",
        "Backend",
        "Developer Tools",
    ),
    "general": (
        "Languages",
        "Backend",
        "AI / Machine Learning",
        "Automation",
        "Developer Tools",
    ),
}


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
        selection = self.select_projects(
            candidate,
            job_analysis,
            analysis=analysis,
            limit=project_limit,
        )
        return self.build_from_selection(candidate, job_analysis, analysis, selection)

    def build_from_selection(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        selection: ProjectSelection,
    ) -> ResumeQualityResult:
        """Build quality-shaped sections from a precomputed project selection."""
        role = self.role_for_job(job_analysis)
        skills = self.group_skills(candidate, job_analysis, analysis, selection)
        return ResumeQualityResult(
            summary=self.summary(candidate, job_analysis, analysis, selection, role),
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
                job_analysis,
                selection,
            ),
        )

    def role_for_job(self, job_analysis: JobAnalysis) -> RoleKind:
        """Classify the target job into a small ATS-tailoring profile."""
        text = self._job_context(job_analysis)
        legal_hits = _count_terms(
            text,
            (
                "legal",
                "law",
                "court",
                "document processing",
                "ocr",
                "document extraction",
                "structured extraction",
                "legal filings",
                "validation",
                "document review",
            ),
        )
        automation_hits = _count_terms(
            text,
            (
                "ai automation",
                "workflow automation",
                "webhook",
                "openai",
                "make",
                "n8n",
                "zapier",
                "internal tools",
                "operations automation",
            ),
        )
        backend_hits = _count_terms(
            text,
            (
                "backend",
                "python",
                "fastapi",
                "api",
                "postgresql",
                "sql",
                "docker",
                "backend services",
                "backend architecture",
            ),
        )
        ml_hits = _count_terms(
            text,
            (
                "machine learning",
                "deep learning",
                "neural networks",
                "computer vision",
                "reinforcement learning",
                "vertex ai",
                "bigquery ml",
                "mlops",
                "model training",
                "model deployment",
                "ml pipelines",
            ),
        )
        if legal_hits >= 2:
            return "legal_ai"
        if ml_hits >= 3:
            return "machine_learning"
        if automation_hits >= 2:
            return "ai_automation"
        if backend_hits >= 3:
            return "backend_python"
        return "general"

    def select_projects(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        *,
        analysis: ResumeAnalysis | None = None,
        limit: int = DEFAULT_PROJECT_LIMIT,
    ) -> ProjectSelection:
        """Rank candidate projects and select only the strongest projects."""
        bounded_limit = max(1, min(limit, self._project_limit(job_analysis)))
        scores = [
            self.score_project(project, job_analysis, analysis=analysis)
            for project in candidate.projects
        ]
        scores.sort(key=lambda item: (-item.score, item.project.title.casefold()))
        selected = scores[:bounded_limit]
        excluded = scores[bounded_limit:]
        return ProjectSelection(selected=selected, excluded=excluded)

    def score_project(
        self,
        project: Project,
        job_analysis: JobAnalysis,
        *,
        analysis: ResumeAnalysis | None = None,
    ) -> ProjectScore:
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
        role = self.role_for_job(job_analysis)
        job_title_text = _normalize(job_analysis.normalized_title)
        job_context_text = self._job_context(job_analysis)
        weighted_terms = [
            *((term, 14) for term in job_analysis.required_technologies),
            *((term, 12) for term in job_analysis.required_skills),
            *((term, 8) for term in job_analysis.preferred_technologies),
            *((term, 7) for term in job_analysis.preferred_skills),
            *((term, 5) for term in job_analysis.ats_keywords),
            *((term, 4) for term in job_analysis.domain_keywords),
        ]
        if analysis is not None:
            weighted_terms.extend((term, 10) for term in analysis.matched_technologies)
            weighted_terms.extend((term, 9) for term in analysis.matched_skills)
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
        score += self._context_overlap_score(job_context_text, project_text)
        score += self._theme_boost(job_title_text, job_context_text, project, role)
        return ProjectScore(project=project, score=score, matched_terms=matched_terms)

    def group_skills(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        selection: ProjectSelection,
    ) -> list[dict[str, object]]:
        """Create grouped, ATS-readable skills ordered by relevance."""
        role = self.role_for_job(job_analysis)
        allowed_groups = ROLE_SKILL_ORDER[role]
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
        supported_values: dict[str, tuple[str, str]] = {
            _normalize(skill.name): (skill.name, skill.category) for skill in candidate.skills
        }
        for score in selection.selected:
            for term in [*score.project.technologies, *score.matched_terms]:
                key = _normalize(term)
                if key and key not in supported_values:
                    supported_values[key] = (term, "Project Evidence")
        ranked_skills = sorted(
            supported_values.values(),
            key=lambda item: (
                _normalize(item[0]) not in matched_terms,
                _normalize(item[0]) not in selected_project_terms,
                item[1].casefold(),
                item[0].casefold(),
            ),
        )
        grouped: list[dict[str, object]] = []
        used: set[str] = set()
        group_definitions = {group_name: aliases for group_name, aliases in SKILL_GROUPS}
        for group_name in allowed_groups:
            aliases = group_definitions[group_name]
            values = []
            for skill_name, _category in ranked_skills:
                key = _normalize(skill_name)
                if key in used:
                    continue
                if _skill_matches_group(key, aliases):
                    values.append(skill_name)
                    used.add(key)
                if len(used) >= MAX_SKILLS:
                    break
            if values:
                grouped.append({"category": group_name, "skills": _deduplicate(values)})
            if len(used) >= MAX_SKILLS:
                break
        return grouped[:MAX_SKILL_GROUPS]

    def summary(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        analysis: ResumeAnalysis,
        selection: ProjectSelection,
        role_kind: RoleKind,
    ) -> str:
        """Create a deterministic job-tailored summary without unsupported claims."""
        role_title = job_analysis.normalized_title or candidate.headline or "AI Engineer"
        project_themes = self._project_themes(selection.selected, role_kind)
        terms = _deduplicate(self._summary_terms(analysis, role_kind))[:4]
        role_prefix = _early_career_role(role_title)
        certification_sentence = self._certification_sentence(candidate, role_kind)
        term_text = f" using {', '.join(terms)}" if terms else ""
        first_sentence = (
            f"{role_prefix} with hands-on project experience building {project_themes}{term_text}."
        )
        if certification_sentence:
            return f"{first_sentence} {certification_sentence}"
        if terms:
            return first_sentence
        return first_sentence

    @staticmethod
    def _summary_terms(analysis: ResumeAnalysis, role: RoleKind) -> list[str]:
        """Select role-appropriate terms for the summary."""
        values = [
            *analysis.matched_technologies,
            *analysis.matched_skills,
            *analysis.matched_keywords,
        ]
        if role == "backend_python":
            preferred = ("python", "fastapi", "api", "postgresql", "sql", "docker", "backend")
            return [
                value for value in values if any(term in _normalize(value) for term in preferred)
            ]
        if role == "machine_learning":
            preferred = (
                "machine learning",
                "deep learning",
                "neural",
                "computer vision",
                "vertex ai",
                "bigquery ml",
                "mlops",
                "google cloud",
                "python",
            )
            return [
                value for value in values if any(term in _normalize(value) for term in preferred)
            ]
        if role == "legal_ai":
            preferred = ("ocr", "document", "structured", "validation", "legal", "fastapi")
            return [
                value for value in values if any(term in _normalize(value) for term in preferred)
            ]
        return values

    @staticmethod
    def _theme_boost(
        job_title_text: str,
        job_context_text: str,
        project: Project,
        role: RoleKind,
    ) -> int:
        """Boost project-job thematic overlap without ML or embeddings."""
        boost = 0
        project_text = _normalize(
            " ".join([project.title, project.description, *project.technologies, *project.outcomes])
        )
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
        project_title = project.title.casefold()
        if project_title == "careeros" and _careeros_is_relevant(job_context_text):
            boost += 18
        if role == "legal_ai":
            if _is_legal_ocr_project(project):
                boost += 95
            elif project_title == "careeros" and not _careeros_domain_requested(job_context_text):
                boost -= 30
            elif "workflow automation" in project_text or "webhook" in project_text:
                boost += 10
        if role == "ai_automation":
            if project_title == "careeros":
                boost += 25
            if "workflow automation" in project_text or "webhook" in project_text:
                boost += 35
            if "agent" in project_text or "incident" in project_text:
                boost += 28
            if _is_legal_ocr_project(project) and not _document_domain_requested(job_context_text):
                boost -= 45
        if role == "backend_python":
            if project_title == "careeros":
                boost += 18
            if _is_legal_ocr_project(project):
                boost += 12
        if role == "machine_learning":
            if project_title == "careeros":
                boost += 10
            if "workflow automation" in project_text or "agent" in project_text:
                boost += 8
            if _is_legal_ocr_project(project) and not _document_domain_requested(job_context_text):
                boost -= 25
        if "agent" in project_text and any(
            term in job_context_text for term in ("ai", "llm", "workflow", "automation")
        ):
            boost += 24
        if any(term in project_text for term in ("ocr", "legal", "document")) and not any(
            term in job_context_text for term in ("ocr", "legal", "document", "extraction")
        ):
            boost -= 20
        return boost

    @staticmethod
    def _context_overlap_score(job_context_text: str, project_text: str) -> int:
        """Score broader description overlap while avoiding tiny generic tokens."""
        project_tokens = {token for token in project_text.split() if len(token) >= 5}
        job_tokens = {token for token in job_context_text.split() if len(token) >= 5}
        generic = {"experience", "strong", "required", "preferred", "working", "systems"}
        overlap = (project_tokens - generic).intersection(job_tokens - generic)
        return min(24, len(overlap) * 2)

    @staticmethod
    def _job_context(job_analysis: JobAnalysis) -> str:
        """Return normalized job title, description, and extracted analysis terms."""
        return _normalize(
            " ".join(
                [
                    job_analysis.normalized_title,
                    getattr(getattr(job_analysis, "job_description", None), "description_text", ""),
                    *job_analysis.responsibilities,
                    *job_analysis.qualifications,
                    *job_analysis.required_skills,
                    *job_analysis.required_technologies,
                    *job_analysis.preferred_skills,
                    *job_analysis.preferred_technologies,
                    *job_analysis.ats_keywords,
                    *job_analysis.domain_keywords,
                    *job_analysis.soft_skills,
                ]
            )
        )

    @staticmethod
    def _project_limit(job_analysis: JobAnalysis) -> int:
        """Keep normal resumes at three projects; allow four only for project-heavy jobs."""
        text = _normalize(
            " ".join(
                [
                    job_analysis.normalized_title,
                    *job_analysis.responsibilities,
                    *job_analysis.qualifications,
                    *job_analysis.ats_keywords,
                    *job_analysis.domain_keywords,
                ]
            )
        )
        project_heavy = any(term in text for term in ("portfolio", "project based", "case study"))
        return MAX_PROJECT_LIMIT if project_heavy else NORMAL_PROJECT_LIMIT

    @staticmethod
    def _project_themes(selected: list[ProjectScore], role: RoleKind) -> str:
        """Summarize selected project evidence in compact recruiter language."""
        text = " ".join(score.project.title.lower() for score in selected)
        if role == "legal_ai":
            return "OCR, document extraction, validation systems, and legal workflow tools"
        if role == "backend_python":
            return "FastAPI services, APIs, PostgreSQL-backed systems, and backend workflows"
        if role == "machine_learning":
            return "ML-focused tools, Python systems, and cloud machine learning concepts"
        if role == "ai_automation":
            return "AI-assisted workflow automation, API integrations, and backend tools"
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
    def _certification_sentence(candidate: CandidateProfile, role: RoleKind) -> str:
        """Mention cloud ML certification evidence without implying production work."""
        if role not in {"machine_learning", "legal_ai"}:
            return ""
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
            "Certified in Google Cloud machine learning with exposure to Vertex AI, "
            "BigQuery ML, MLOps, and production ML concepts."
        )

    @staticmethod
    def _should_include_additional_experience(
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        selection: ProjectSelection,
    ) -> bool:
        """Include non-engineering experience only when it helps this specific role."""
        if len(selection.selected) >= NORMAL_PROJECT_LIMIT:
            return False
        job_text = _normalize(
            " ".join(
                [
                    job_analysis.normalized_title,
                    getattr(getattr(job_analysis, "job_description", None), "description_text", ""),
                    *job_analysis.responsibilities,
                    *job_analysis.qualifications,
                    *job_analysis.soft_skills,
                ]
            )
        )
        useful_terms = (
            "communication",
            "teaching",
            "training",
            "mentor",
            "education",
            "management",
            "client",
            "customer",
            "operations",
            "leadership",
        )
        if not any(term in job_text for term in useful_terms):
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
            "outcomes": _prioritize_bullets(project.outcomes, score.matched_terms),
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
            "reason": _selection_reason(score) if selected else _exclusion_reason(score),
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


def _careeros_is_relevant(job_context_text: str) -> bool:
    """Return whether careerOS deserves its role-specific relevance boost."""
    relevant_terms = (
        "ai",
        "automation",
        "workflow",
        "python",
        "fastapi",
        "backend",
        "resume",
        "career",
        "job extraction",
        "ats",
        "application",
    )
    return any(term in job_context_text for term in relevant_terms)


def _careeros_domain_requested(job_context_text: str) -> bool:
    """Return whether a job explicitly asks for career/resume/ATS matching work."""
    terms = (
        "resume",
        "career",
        "ats",
        "job application",
        "candidate",
        "candidate matching",
        "job extraction",
        "application tracking",
    )
    return any(term in job_context_text for term in terms)


def _document_domain_requested(job_context_text: str) -> bool:
    """Return whether document/OCR/legal extraction is actually part of the role."""
    terms = (
        "legal",
        "law",
        "court",
        "ocr",
        "document",
        "document extraction",
        "structured extraction",
        "legal filing",
        "validation",
        "document review",
    )
    return any(term in job_context_text for term in terms)


def _is_legal_ocr_project(project: Project) -> bool:
    """Identify the candidate's legal/OCR/document extraction project by evidence."""
    text = _normalize(
        " ".join([project.title, project.description, *project.technologies, *project.outcomes])
    )
    return "ocr" in text or ("legal" in text and "document" in text)


def _count_terms(text: str, terms: tuple[str, ...]) -> int:
    """Count role-profile terms in normalized text."""
    return sum(1 for term in terms if _normalize(term) in text)


def _selection_reason(score: ProjectScore) -> str:
    """Create a recruiter-facing explanation for selected projects."""
    terms = _deduplicate(score.matched_terms)[:4]
    if terms:
        return f"Selected because the role asks for {', '.join(terms)}."
    return "Selected because it is among the strongest project matches for this role."


def _exclusion_reason(score: ProjectScore) -> str:
    """Create a concise exclusion explanation."""
    if _is_legal_ocr_project(score.project):
        return "Excluded because its legal/OCR focus is less relevant to this role."
    if score.matched_terms:
        return "Excluded because stronger projects matched more target requirements."
    return "Excluded because it has lower relevance for this role."


def _prioritize_bullets(values: list[str], matched_terms: list[str]) -> list[str]:
    """Keep concise, non-duplicate outcome bullets."""
    unique = _deduplicate([value for value in values if value])
    job_terms = {_normalize(term) for term in matched_terms}
    unique.sort(
        key=lambda value: (
            not any(term and term in _normalize(value) for term in job_terms),
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
        if alias in {"api", "apis", "sql"}:
            if key in {"api", "apis"}:
                return True
            if alias == "sql" and key == "sql":
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

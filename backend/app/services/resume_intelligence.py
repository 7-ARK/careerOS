"""Transactional orchestration for evidence-backed resume intelligence."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.features.resume_intelligence import DeterministicResumeIntelligenceEngine
from app.features.resume_intelligence.llm import LLMResumeQualityService
from app.features.resume_intelligence.quality import DeterministicResumeQualityEngine
from app.models import CandidateProfile, JobAnalysis, ResumeAnalysis, ResumeDraft, WorkExperience
from app.models.enums import ResumeDraftStatus, ResumeSectionType
from app.repositories import (
    CandidateProfileRepository,
    JobAnalysisRepository,
    ResumeAnalysisRepository,
    ResumeDraftRepository,
)
from app.schemas import (
    EvidenceReference,
    KeywordCoverage,
    MatchBreakdown,
    ResumeAnalysisCreate,
    ResumeAnalysisRead,
    ResumeAnalysisResult,
    ResumeDraftCreate,
    ResumeDraftRead,
    ResumeRecommendation,
)
from app.services.exceptions import (
    JobAnalysisNotFoundError,
    ProfileNotFoundError,
    ResumeAnalysisNotFoundError,
    ResumeDraftNotFoundError,
)

ANALYSIS_JSON_FIELDS = {
    "matched_keywords",
    "missing_keywords",
    "matched_skills",
    "missing_skills",
    "matched_technologies",
    "missing_technologies",
    "relevant_projects",
    "relevant_experiences",
    "relevant_education",
    "strengths",
    "weaknesses",
    "gap_analysis",
    "tailoring_recommendations",
    "truthfulness_warnings",
    "suggested_resume_sections",
}

DRAFT_JSON_FIELDS = {
    "skills_section",
    "experience_section",
    "projects_section",
    "education_section",
    "certifications_section",
    "ats_keywords_used",
    "omitted_keywords",
    "truthfulness_notes",
    "grounding_manifest",
}


class ResumeIntelligenceService:
    """Analyze candidate truth against a job and persist structured resume drafts."""

    def __init__(
        self,
        session: Session,
        engine: DeterministicResumeIntelligenceEngine | None = None,
        quality_engine: DeterministicResumeQualityEngine | LLMResumeQualityService | None = None,
    ) -> None:
        """Build an injectable resume-intelligence service."""
        self.session = session
        self.engine = engine or DeterministicResumeIntelligenceEngine()
        self.quality_engine = quality_engine or LLMResumeQualityService.from_settings()
        self.profiles = CandidateProfileRepository(session)
        self.job_analyses = JobAnalysisRepository(session)
        self.resume_analyses = ResumeAnalysisRepository(session)
        self.resume_drafts = ResumeDraftRepository(session)

    def analyze_candidate_for_job(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> ResumeAnalysisResult:
        """Create and persist a deterministic candidate-job resume analysis."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        analysis_data = self.engine.analyze(candidate, job_analysis)
        analysis = self.resume_analyses.create_resume_analysis(
            **self._analysis_values(analysis_data)
        )
        self._commit()
        return self._analysis_result(analysis, job_analysis)

    def calculate_keyword_coverage(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> KeywordCoverage:
        """Calculate unique ATS keyword coverage for one candidate-job pair."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        return self.engine.calculate_keyword_coverage(candidate, job_analysis)

    def calculate_skill_coverage(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> dict[str, object]:
        """Calculate required-skill evidence coverage."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        coverage = self.engine.calculate_skill_coverage(candidate, job_analysis)
        return {"matched": coverage.matched, "missing": coverage.missing, "score": coverage.score}

    def calculate_technology_coverage(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> dict[str, object]:
        """Calculate required-technology evidence coverage."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        coverage = self.engine.calculate_technology_coverage(candidate, job_analysis)
        return {"matched": coverage.matched, "missing": coverage.missing, "score": coverage.score}

    def identify_strongest_evidence(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
        *,
        limit: int = 5,
    ) -> list[EvidenceReference]:
        """Return the strongest candidate project and work evidence for a job."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        return self.engine.identify_strongest_evidence(
            self.engine.collect_evidence(candidate),
            terms=[
                *job_analysis.required_skills,
                *job_analysis.required_technologies,
                *job_analysis.preferred_skills,
                *job_analysis.preferred_technologies,
            ],
            source_types={ResumeSectionType.EXPERIENCE, ResumeSectionType.PROJECTS},
            limit=limit,
        )

    def identify_missing_job_requirements(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> dict[str, list[str]]:
        """Return required gaps and unverified preferred terms for review."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        return self.engine.identify_missing_requirements(candidate, job_analysis)

    def generate_tailoring_recommendations(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> list[ResumeRecommendation]:
        """Generate only recommendations supported by candidate evidence."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        evidence = self.engine.collect_evidence(candidate)
        skill_coverage = self.engine.calculate_skill_coverage(
            candidate, job_analysis, evidence=evidence
        )
        technology_coverage = self.engine.calculate_technology_coverage(
            candidate, job_analysis, evidence=evidence
        )
        return self.engine.generate_tailoring_recommendations(
            evidence=evidence,
            matched_terms=[*skill_coverage.matched, *technology_coverage.matched],
        )

    def generate_truthfulness_warnings(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> list[str]:
        """Generate warnings for requirements without candidate evidence."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        evidence = self.engine.collect_evidence(candidate)
        skills = self.engine.calculate_skill_coverage(candidate, job_analysis, evidence=evidence)
        technologies = self.engine.calculate_technology_coverage(
            candidate, job_analysis, evidence=evidence
        )
        return self.engine.generate_truthfulness_warnings(
            skills.missing,
            technologies.missing,
            job_analysis.preferred_skills,
            job_analysis.preferred_technologies,
            evidence,
        )

    def create_resume_draft_from_analysis(self, resume_analysis_id: UUID) -> ResumeDraftRead:
        """Create a structured resume draft from a persisted evidence-backed analysis."""
        analysis = self._require_resume_analysis(resume_analysis_id)
        candidate = self._require_candidate(analysis.candidate_profile_id)
        job_analysis = self._require_job_analysis(analysis.job_analysis_id)
        quality = self.quality_engine.build(candidate, job_analysis, analysis)
        experience_section = self._experience_section(
            candidate,
            analysis,
            include_additional=quality.include_additional_experience,
        )
        education_section = self._education_section(candidate)
        certifications_section = self._certifications_section(candidate)
        draft_data = ResumeDraftCreate(
            resume_analysis_id=analysis.id,
            candidate_profile_id=candidate.id,
            job_analysis_id=job_analysis.id,
            title=f"{job_analysis.normalized_title} Resume",
            target_role=job_analysis.normalized_title,
            summary=quality.summary,
            skills_section=quality.skills_section,
            experience_section=experience_section,
            projects_section=quality.projects_section,
            education_section=education_section,
            certifications_section=certifications_section,
            ats_keywords_used=analysis.matched_keywords,
            omitted_keywords=analysis.missing_keywords,
            truthfulness_notes=self._deduplicate(
                [*analysis.truthfulness_warnings, *quality.warnings]
            ),
            grounding_manifest=self._grounding_manifest(
                candidate,
                analysis,
                summary=quality.summary,
                skills_section=quality.skills_section,
                experience_section=experience_section,
                projects_section=quality.projects_section,
                education_section=education_section,
                certifications_section=certifications_section,
            ),
            status=ResumeDraftStatus.DRAFT,
        )
        draft = self.resume_drafts.create_resume_draft(**self._draft_values(draft_data))
        self._commit()
        return ResumeDraftRead.model_validate(draft)

    def get_project_selection_review(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
        resume_draft_id: UUID | None = None,
    ) -> dict[str, list[dict[str, object]]]:
        """Return selected and excluded project review metadata for the frontend."""
        candidate, job_analysis = self._require_inputs(candidate_profile_id, job_analysis_id)
        selection = self.quality_engine.select_projects(candidate, job_analysis)
        if resume_draft_id is not None:
            draft = self._require_resume_draft(resume_draft_id)
            selected_projects = [
                {
                    "title": str(project.get("title", "")),
                    "score": project.get("relevance_score", 0),
                    "reason": project.get("selection_reason", "Selected for this target role."),
                }
                for project in draft.projects_section
                if project.get("title")
            ]
            selected_titles = {str(project["title"]).casefold() for project in selected_projects}
            excluded_scores = [
                self.quality_engine.score_project(project, job_analysis)
                if hasattr(self.quality_engine, "score_project")
                else self.quality_engine.deterministic_engine.score_project(project, job_analysis)
                for project in candidate.projects
                if project.title.casefold() not in selected_titles
            ]
            excluded_scores.sort(key=lambda item: (-item.score, item.project.title.casefold()))
            return {
                "selected_projects": selected_projects,
                "excluded_projects": [
                    {
                        "title": score.project.title,
                        "score": score.score,
                        "reason": "Excluded because lower relevance score.",
                    }
                    for score in excluded_scores
                ],
            }
        return {
            "selected_projects": [
                {"title": score.project.title, "score": score.score, "reason": score.reason}
                for score in selection.selected
            ],
            "excluded_projects": [
                {
                    "title": score.project.title,
                    "score": score.score,
                    "reason": "Excluded because lower relevance score.",
                }
                for score in selection.excluded
            ],
        }

    def get_resume_analysis(self, resume_analysis_id: UUID) -> ResumeAnalysisRead:
        """Return a persisted resume analysis."""
        return ResumeAnalysisRead.model_validate(self._require_resume_analysis(resume_analysis_id))

    def get_latest_resume_analysis(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> ResumeAnalysisRead:
        """Return the newest analysis for a candidate-job pair."""
        analysis = self.resume_analyses.get_latest_by_candidate_job(
            candidate_profile_id, job_analysis_id
        )
        if analysis is None:
            raise ResumeAnalysisNotFoundError("resume analysis was not found")
        return ResumeAnalysisRead.model_validate(analysis)

    def list_resume_analyses_by_candidate(
        self, candidate_profile_id: UUID
    ) -> list[ResumeAnalysisRead]:
        """List persisted analyses for one candidate."""
        return [
            ResumeAnalysisRead.model_validate(analysis)
            for analysis in self.resume_analyses.list_by_candidate(candidate_profile_id)
        ]

    def list_resume_analyses_by_job(self, job_analysis_id: UUID) -> list[ResumeAnalysisRead]:
        """List persisted analyses for one structured job analysis."""
        return [
            ResumeAnalysisRead.model_validate(analysis)
            for analysis in self.resume_analyses.list_by_job(job_analysis_id)
        ]

    def get_resume_draft(self, resume_draft_id: UUID) -> ResumeDraftRead:
        """Return a structured resume draft."""
        draft = self.resume_drafts.get(resume_draft_id)
        if draft is None:
            raise ResumeDraftNotFoundError(f"resume draft {resume_draft_id} was not found")
        return ResumeDraftRead.model_validate(draft)

    def list_resume_drafts_by_candidate(self, candidate_profile_id: UUID) -> list[ResumeDraftRead]:
        """List structured drafts for one candidate."""
        return [
            ResumeDraftRead.model_validate(draft)
            for draft in self.resume_drafts.list_by_candidate(candidate_profile_id)
        ]

    def list_resume_drafts_by_job(self, job_analysis_id: UUID) -> list[ResumeDraftRead]:
        """List structured drafts generated for one job analysis."""
        return [
            ResumeDraftRead.model_validate(draft)
            for draft in self.resume_drafts.list_by_job(job_analysis_id)
        ]

    def update_resume_draft_status(
        self,
        resume_draft_id: UUID,
        status: ResumeDraftStatus | str,
    ) -> ResumeDraftRead:
        """Update a structured draft lifecycle state."""
        draft = self.resume_drafts.get(resume_draft_id)
        if draft is None:
            raise ResumeDraftNotFoundError(f"resume draft {resume_draft_id} was not found")
        self.resume_drafts.update_status(draft, status)
        self._commit()
        return ResumeDraftRead.model_validate(draft)

    def _analysis_result(
        self,
        analysis: ResumeAnalysis,
        job_analysis: JobAnalysis,
    ) -> ResumeAnalysisResult:
        """Build an API-ready persisted result with explainable projections."""
        analysis_read = ResumeAnalysisRead.model_validate(analysis)
        preferred_keywords = self._deduplicate(
            [*job_analysis.preferred_skills, *job_analysis.preferred_technologies]
        )
        return ResumeAnalysisResult(
            analysis=analysis_read,
            keyword_coverage=KeywordCoverage(
                required_keywords=self._deduplicate(
                    [
                        *job_analysis.required_skills,
                        *job_analysis.required_technologies,
                        *job_analysis.ats_keywords,
                    ]
                ),
                preferred_keywords=preferred_keywords,
                matched_keywords=analysis.matched_keywords,
                missing_keywords=analysis.missing_keywords,
                score=analysis.keyword_match_score,
            ),
            match_breakdown=MatchBreakdown(
                overall_match_score=analysis.overall_match_score,
                keyword_match_score=analysis.keyword_match_score,
                skills_match_score=analysis.skills_match_score,
                technology_match_score=analysis.technology_match_score,
                experience_match_score=analysis.experience_match_score,
                project_match_score=analysis.project_match_score,
                education_match_score=analysis.education_match_score,
                quality=self.engine.quality_for_score(analysis.overall_match_score),
            ),
        )

    def _require_inputs(
        self,
        candidate_profile_id: UUID,
        job_analysis_id: UUID,
    ) -> tuple[CandidateProfile, JobAnalysis]:
        """Load source-of-truth candidate and structured job-analysis inputs."""
        return self._require_candidate(candidate_profile_id), self._require_job_analysis(
            job_analysis_id
        )

    def _require_candidate(self, candidate_profile_id: UUID) -> CandidateProfile:
        """Load a complete candidate knowledge-base aggregate."""
        candidate = self.profiles.get_complete(candidate_profile_id)
        if candidate is None:
            raise ProfileNotFoundError(f"candidate profile {candidate_profile_id} was not found")
        return candidate

    def _require_job_analysis(self, job_analysis_id: UUID) -> JobAnalysis:
        """Load a structured job analysis."""
        job_analysis = self.job_analyses.get(job_analysis_id)
        if job_analysis is None:
            raise JobAnalysisNotFoundError(f"job analysis {job_analysis_id} was not found")
        return job_analysis

    def _require_resume_analysis(self, resume_analysis_id: UUID) -> ResumeAnalysis:
        """Load a persisted resume analysis."""
        analysis = self.resume_analyses.get(resume_analysis_id)
        if analysis is None:
            raise ResumeAnalysisNotFoundError(f"resume analysis {resume_analysis_id} was not found")
        return analysis

    def _require_resume_draft(self, resume_draft_id: UUID) -> ResumeDraft:
        """Load a persisted resume draft."""
        draft = self.resume_drafts.get(resume_draft_id)
        if draft is None:
            raise ResumeDraftNotFoundError(f"resume draft {resume_draft_id} was not found")
        return draft

    @staticmethod
    def _analysis_values(data: ResumeAnalysisCreate) -> dict[str, object]:
        """Prepare ORM values while serializing nested JSON evidence safely."""
        values = data.model_dump()
        json_values = data.model_dump(mode="json")
        for field in ANALYSIS_JSON_FIELDS:
            values[field] = json_values[field]
        return values

    @staticmethod
    def _draft_values(data: ResumeDraftCreate) -> dict[str, object]:
        """Prepare ORM values while preserving UUID foreign keys."""
        values = data.model_dump()
        json_values = data.model_dump(mode="json")
        for field in DRAFT_JSON_FIELDS:
            values[field] = json_values[field]
        values["status"] = str(data.status)
        return values

    @staticmethod
    def _skills_section(
        candidate: CandidateProfile,
        analysis: ResumeAnalysis,
    ) -> list[dict[str, object]]:
        """Order candidate-owned skills by relevance without adding unsupported terms."""
        matched = {
            term.casefold() for term in [*analysis.matched_skills, *analysis.matched_technologies]
        }
        skills = sorted(
            candidate.skills, key=lambda skill: (skill.name.casefold() not in matched, skill.name)
        )
        return [
            {
                "source_id": str(skill.id),
                "name": skill.name,
                "category": skill.category,
                "self_rating": skill.self_rating,
                "years_of_experience": str(skill.years_of_experience),
            }
            for skill in skills
        ]

    @staticmethod
    def _experience_section(
        candidate: CandidateProfile,
        analysis: ResumeAnalysis,
        *,
        include_additional: bool = False,
    ) -> list[dict[str, object]]:
        """Select relevant candidate-owned work records and preserve their facts."""
        relevant_ids = {UUID(reference["source_id"]) for reference in analysis.relevant_experiences}
        entries = []
        for experience in candidate.work_experiences:
            is_additional = _is_additional_experience(experience.job_title, experience.company)
            if experience.id not in relevant_ids and not (include_additional and is_additional):
                continue
            achievements = (
                _additional_experience_bullets(experience)
                if is_additional
                else experience.achievements
            )
            entries.append(
                {
                    "source_id": str(experience.id),
                    "company": experience.company,
                    "job_title": experience.job_title,
                    "start_date": experience.start_date.isoformat(),
                    "end_date": experience.end_date.isoformat() if experience.end_date else None,
                    "description": None if is_additional else experience.description,
                    "achievements": achievements,
                    "is_additional": is_additional,
                }
            )
        return entries

    @staticmethod
    def _projects_section(
        candidate: CandidateProfile,
        analysis: ResumeAnalysis,
    ) -> list[dict[str, object]]:
        """Select relevant candidate-owned projects and preserve their evidence."""
        relevant_ids = {UUID(reference["source_id"]) for reference in analysis.relevant_projects}
        projects = [project for project in candidate.projects if project.id in relevant_ids]
        return [
            {
                "source_id": str(project.id),
                "title": project.title,
                "description": project.description,
                "technologies": project.technologies,
                "outcomes": project.outcomes,
                "github_url": project.github_url,
                "portfolio_url": project.portfolio_url,
            }
            for project in projects
        ]

    @staticmethod
    def _education_section(candidate: CandidateProfile) -> list[dict[str, object]]:
        """Serialize candidate-owned education facts."""
        return [
            {
                "source_id": str(education.id),
                "institution": education.institution,
                "degree": education.degree,
                "field_of_study": education.field_of_study,
            }
            for education in candidate.education
        ]

    @staticmethod
    def _certifications_section(candidate: CandidateProfile) -> list[dict[str, object]]:
        """Serialize compact candidate-owned certification facts."""
        return [
            {
                "source_id": str(certification.id),
                "name": certification.name,
                "issuing_organization": _compact_issuer(certification.issuing_organization),
                "credential_id": None,
                "credential_url": certification.credential_url,
            }
            for certification in candidate.certifications
        ]

    @staticmethod
    def _grounding_manifest(
        candidate: CandidateProfile,
        analysis: ResumeAnalysis,
        *,
        summary: str,
        skills_section: list[dict[str, object]],
        experience_section: list[dict[str, object]],
        projects_section: list[dict[str, object]],
        education_section: list[dict[str, object]],
        certifications_section: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Attach stable evidence IDs to every generated resume claim group."""
        skill_ids = {skill.name.casefold(): f"skill-{skill.id}" for skill in candidate.skills}
        project_ids = {
            term.casefold(): f"project-{project.id}"
            for project in candidate.projects
            for term in [project.title, *project.technologies]
        }
        summary_ids = list(
            dict.fromkeys(
                [
                    *(
                        skill_ids[term.casefold()]
                        for term in analysis.matched_skills
                        if term.casefold() in skill_ids
                    ),
                    *(
                        f"project-{reference['source_id']}"
                        for reference in analysis.relevant_projects
                    ),
                    *(
                        f"experience-{reference['source_id']}"
                        for reference in analysis.relevant_experiences
                    ),
                ]
            )
        )
        if candidate.headline or candidate.summary or candidate.location:
            summary_ids.insert(0, f"profile-{candidate.id}-summary")
        if not summary_ids and candidate.skills:
            summary_ids = [f"skill-{candidate.skills[0].id}"]
        manifest: list[dict[str, object]] = [
            {"claim_type": "summary", "text": summary, "evidence_ids": summary_ids}
        ]
        for group in skills_section:
            for skill_name in group.get("skills", []):
                key = str(skill_name).casefold()
                evidence_id = skill_ids.get(key) or project_ids.get(key)
                manifest.append(
                    {
                        "claim_type": "skill",
                        "text": str(skill_name),
                        "evidence_ids": [evidence_id] if evidence_id else [],
                    }
                )
        manifest.extend(
            {
                "claim_type": "experience",
                "text": str(entry.get("job_title", "Experience entry")),
                "evidence_ids": [f"experience-{entry['source_id']}"],
            }
            for entry in experience_section
            if entry.get("source_id")
        )
        manifest.extend(
            {
                "claim_type": "project",
                "text": str(entry.get("title", "Project entry")),
                "evidence_ids": [f"project-{entry['source_id']}"],
            }
            for entry in projects_section
            if entry.get("source_id")
        )
        manifest.extend(
            {
                "claim_type": "education",
                "text": str(entry.get("degree", "Education entry")),
                "evidence_ids": [f"education-{entry['source_id']}"],
            }
            for entry in education_section
            if entry.get("source_id")
        )
        manifest.extend(
            {
                "claim_type": "certification",
                "text": str(entry.get("name", "Certification entry")),
                "evidence_ids": [f"certification-{entry['source_id']}"],
            }
            for entry in certifications_section
            if entry.get("source_id")
        )
        return manifest

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        """Deduplicate case-insensitively while preserving order."""
        seen: set[str] = set()
        unique = []
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(value)
        return unique

    def _commit(self) -> None:
        """Commit the transaction and rollback consistently on failure."""
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise


def _is_additional_experience(job_title: str, company: str) -> bool:
    """Detect non-engineering business/tutoring experience for a separate section."""
    text = f"{job_title} {company}".casefold()
    return any(term in text for term in ("tutor", "tutoring", "ignite learning", "learning"))


def _additional_experience_bullets(experience: WorkExperience) -> list[str]:
    """Return compact applicant-facing bullets for tutoring/business experience."""
    text = " ".join([experience.description or "", *experience.achievements]).casefold()
    if "ignite" in text or "tutor" in text:
        return [
            (
                "Runs an online tutoring service supporting international students in math, "
                "physics, and English."
            ),
            ("Manages student communication, scheduling, delivery quality, and academic support."),
        ]
    return experience.achievements[:2]


def _compact_issuer(value: str) -> str:
    """Normalize certification issuer text for one-line resume entries."""
    return value.replace(" / ", "/")

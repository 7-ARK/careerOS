"""Deterministic, evidence-backed resume intelligence calculations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.models import CandidateProfile, JobAnalysis
from app.models.enums import MatchQuality, ResumeSectionType
from app.schemas import (
    EvidenceReference,
    KeywordCoverage,
    MatchBreakdown,
    ResumeAnalysisCreate,
    ResumeRecommendation,
)

ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Internal searchable representation of a candidate knowledge-base record."""

    reference: EvidenceReference
    searchable_text: str
    rank: int


@dataclass(frozen=True, slots=True)
class CoverageResult:
    """Internal coverage result with traceable evidence."""

    matched: list[str]
    missing: list[str]
    score: Decimal
    evidence_by_term: dict[str, list[EvidenceReference]]


class DeterministicResumeIntelligenceEngine:
    """Compare candidate truth with job requirements using explainable local rules."""

    def analyze(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
    ) -> ResumeAnalysisCreate:
        """Build a persistable analysis snapshot for one candidate-job pair."""
        evidence = self._collect_evidence(candidate)
        keyword_coverage = self.calculate_keyword_coverage(
            candidate, job_analysis, evidence=evidence
        )
        skill_coverage = self.calculate_skill_coverage(candidate, job_analysis, evidence=evidence)
        technology_coverage = self.calculate_technology_coverage(
            candidate, job_analysis, evidence=evidence
        )
        relevant_projects = self.identify_strongest_evidence(
            evidence,
            terms=[*job_analysis.required_skills, *job_analysis.required_technologies],
            source_types={ResumeSectionType.PROJECTS},
        )
        relevant_experiences = self.identify_strongest_evidence(
            evidence,
            terms=[*job_analysis.required_skills, *job_analysis.required_technologies],
            source_types={ResumeSectionType.EXPERIENCE},
        )
        relevant_education = self._relevant_education(candidate, job_analysis)
        experience_score, candidate_years = self._experience_score(candidate, job_analysis)
        project_score = self._evidence_score(
            evidence,
            terms=[*job_analysis.required_skills, *job_analysis.required_technologies],
            source_types={ResumeSectionType.PROJECTS},
        )
        education_score = self._education_score(candidate, job_analysis)
        breakdown = self._match_breakdown(
            keyword_score=keyword_coverage.score,
            skill_score=skill_coverage.score,
            technology_score=technology_coverage.score,
            experience_score=experience_score,
            project_score=project_score,
            education_score=education_score,
            missing_skills=skill_coverage.missing,
            missing_technologies=technology_coverage.missing,
        )
        recommendations = self.generate_tailoring_recommendations(
            evidence=evidence,
            matched_terms=self._deduplicate(
                [
                    *skill_coverage.matched,
                    *technology_coverage.matched,
                    *job_analysis.preferred_skills,
                    *job_analysis.preferred_technologies,
                ]
            ),
        )
        truthfulness_warnings = self.generate_truthfulness_warnings(
            skill_coverage.missing,
            technology_coverage.missing,
            job_analysis.preferred_skills,
            job_analysis.preferred_technologies,
            evidence,
        )
        strengths = self._strengths(
            skill_coverage,
            technology_coverage,
            relevant_projects,
            relevant_experiences,
        )
        weaknesses = self._weaknesses(
            skill_coverage.missing,
            technology_coverage.missing,
            job_analysis.estimated_years_min,
            candidate_years,
        )
        return ResumeAnalysisCreate(
            candidate_profile_id=candidate.id,
            job_analysis_id=job_analysis.id,
            overall_match_score=breakdown.overall_match_score,
            keyword_match_score=breakdown.keyword_match_score,
            skills_match_score=breakdown.skills_match_score,
            technology_match_score=breakdown.technology_match_score,
            experience_match_score=breakdown.experience_match_score,
            project_match_score=breakdown.project_match_score,
            education_match_score=breakdown.education_match_score,
            matched_keywords=keyword_coverage.matched_keywords,
            missing_keywords=keyword_coverage.missing_keywords,
            matched_skills=skill_coverage.matched,
            missing_skills=skill_coverage.missing,
            matched_technologies=technology_coverage.matched,
            missing_technologies=technology_coverage.missing,
            relevant_projects=relevant_projects,
            relevant_experiences=relevant_experiences,
            relevant_education=relevant_education,
            strengths=strengths,
            weaknesses=weaknesses,
            gap_analysis={
                "missing_required_skills": skill_coverage.missing,
                "missing_required_technologies": technology_coverage.missing,
                "unverified_preferred_skills": self._missing_terms(
                    job_analysis.preferred_skills, evidence
                ),
                "unverified_preferred_technologies": self._missing_terms(
                    job_analysis.preferred_technologies, evidence
                ),
                "candidate_estimated_years": str(candidate_years),
                "required_estimated_years_min": job_analysis.estimated_years_min,
                "technology_match_score": str(technology_coverage.score),
            },
            tailoring_recommendations=recommendations,
            truthfulness_warnings=truthfulness_warnings,
            suggested_resume_summary=self._suggested_summary(
                candidate,
                job_analysis,
                [*skill_coverage.matched, *technology_coverage.matched],
            ),
            suggested_resume_sections=self._suggested_sections(
                relevant_projects,
                relevant_experiences,
                candidate,
            ),
        )

    def collect_evidence(self, candidate: CandidateProfile) -> list[EvidenceItem]:
        """Return searchable candidate evidence for service-level projections."""
        return self._collect_evidence(candidate)

    def quality_for_score(self, score: Decimal) -> MatchQuality:
        """Return the quality band for an overall score."""
        return self._quality(score)

    def calculate_keyword_coverage(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        *,
        evidence: list[EvidenceItem] | None = None,
    ) -> KeywordCoverage:
        """Measure unique ATS keyword support without rewarding repetition."""
        evidence = evidence or self._collect_evidence(candidate)
        required_keywords = self._deduplicate(
            [
                *job_analysis.required_skills,
                *job_analysis.required_technologies,
                *job_analysis.ats_keywords,
            ]
        )
        preferred_keywords = self._deduplicate(
            [*job_analysis.preferred_skills, *job_analysis.preferred_technologies]
        )
        coverage = self._coverage(required_keywords, evidence)
        return KeywordCoverage(
            required_keywords=required_keywords,
            preferred_keywords=preferred_keywords,
            matched_keywords=coverage.matched,
            missing_keywords=coverage.missing,
            score=coverage.score,
        )

    def calculate_skill_coverage(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        *,
        evidence: list[EvidenceItem] | None = None,
    ) -> CoverageResult:
        """Measure candidate evidence for required job skills."""
        return self._coverage(
            job_analysis.required_skills, evidence or self._collect_evidence(candidate)
        )

    def calculate_technology_coverage(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        *,
        evidence: list[EvidenceItem] | None = None,
    ) -> CoverageResult:
        """Measure candidate evidence for required technologies."""
        return self._coverage(
            job_analysis.required_technologies,
            evidence or self._collect_evidence(candidate),
        )

    def identify_missing_requirements(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        *,
        evidence: list[EvidenceItem] | None = None,
    ) -> dict[str, list[str]]:
        """Return required gaps and unverified preferred terms separately."""
        evidence = evidence or self._collect_evidence(candidate)
        return {
            "missing_required_skills": self._missing_terms(job_analysis.required_skills, evidence),
            "missing_required_technologies": self._missing_terms(
                job_analysis.required_technologies, evidence
            ),
            "unverified_preferred_skills": self._missing_terms(
                job_analysis.preferred_skills, evidence
            ),
            "unverified_preferred_technologies": self._missing_terms(
                job_analysis.preferred_technologies, evidence
            ),
        }

    def identify_strongest_evidence(
        self,
        evidence: list[EvidenceItem],
        *,
        terms: list[str],
        source_types: set[ResumeSectionType],
        limit: int = 5,
    ) -> list[EvidenceReference]:
        """Return the strongest records that support target requirements."""
        matches: list[tuple[int, EvidenceReference]] = []
        for item in evidence:
            if item.reference.source_type not in source_types:
                continue
            supported = [term for term in self._deduplicate(terms) if self._matches(term, item)]
            if supported:
                matches.append(
                    (
                        item.rank + len(supported),
                        item.reference.model_copy(update={"matched_terms": supported}),
                    )
                )
        matches.sort(key=lambda match: (-match[0], match[1].label.lower()))
        return [reference for _, reference in matches[:limit]]

    def generate_tailoring_recommendations(
        self,
        *,
        evidence: list[EvidenceItem],
        matched_terms: list[str],
    ) -> list[ResumeRecommendation]:
        """Recommend only supported claims and attach their source evidence."""
        recommendations: list[ResumeRecommendation] = []
        for section in (
            ResumeSectionType.EXPERIENCE,
            ResumeSectionType.PROJECTS,
            ResumeSectionType.SKILLS,
            ResumeSectionType.CERTIFICATIONS,
        ):
            references = self.identify_strongest_evidence(
                evidence,
                terms=matched_terms,
                source_types={section},
                limit=3,
            )
            if not references:
                continue
            supported = self._deduplicate(
                [term for reference in references for term in reference.matched_terms]
            )
            recommendations.append(
                ResumeRecommendation(
                    section=section,
                    recommendation=(
                        f"Highlight {', '.join(supported)} in the {section.value} section "
                        "using the cited candidate evidence."
                    ),
                    rationale=(
                        "These terms are relevant to the target role and supported by the "
                        "knowledge base."
                    ),
                    supported_keywords=supported,
                    evidence=references,
                )
            )
        return recommendations

    def generate_truthfulness_warnings(
        self,
        missing_skills: list[str],
        missing_technologies: list[str],
        preferred_skills: list[str],
        preferred_technologies: list[str],
        evidence: list[EvidenceItem],
    ) -> list[str]:
        """Warn against unsupported claims while preserving gap visibility."""
        required_missing = self._deduplicate([*missing_skills, *missing_technologies])
        preferred_missing = self._missing_terms(
            [*preferred_skills, *preferred_technologies], evidence
        )
        warnings = []
        for term in required_missing:
            cloud_note = self._cloud_certification_note(term, evidence)
            warnings.append(
                cloud_note
                or (
                    f"Do not claim {term}; no supporting Candidate Knowledge Base evidence "
                    "was found."
                )
            )
        for term in preferred_missing:
            cloud_note = self._cloud_certification_note(term, evidence)
            warnings.append(
                cloud_note
                or (
                    f"Preferred requirement {term} is unverified; omit it unless the candidate "
                    "adds evidence."
                )
            )
        return warnings

    def _collect_evidence(self, candidate: CandidateProfile) -> list[EvidenceItem]:
        """Index candidate-owned truth sources for deterministic matching."""
        evidence: list[EvidenceItem] = []
        for skill in candidate.skills:
            evidence.append(
                self._evidence_item(
                    ResumeSectionType.SKILLS,
                    skill.id,
                    skill.name,
                    [skill.name, skill.category],
                    (
                        f"{skill.name}: {skill.years_of_experience} years, "
                        f"rating {skill.self_rating}/5"
                    ),
                    rank=3,
                )
            )
        for project in candidate.projects:
            evidence.append(
                self._evidence_item(
                    ResumeSectionType.PROJECTS,
                    project.id,
                    project.title,
                    [project.title, project.description, *project.technologies, *project.outcomes],
                    project.description,
                    rank=5,
                )
            )
        for experience in candidate.work_experiences:
            evidence.append(
                self._evidence_item(
                    ResumeSectionType.EXPERIENCE,
                    experience.id,
                    f"{experience.job_title} at {experience.company}",
                    [
                        experience.job_title,
                        experience.company,
                        experience.description or "",
                        *experience.achievements,
                    ],
                    experience.description or "; ".join(experience.achievements),
                    rank=5,
                )
            )
        for certification in candidate.certifications:
            evidence.append(
                self._evidence_item(
                    ResumeSectionType.CERTIFICATIONS,
                    certification.id,
                    certification.name,
                    [
                        certification.name,
                        certification.issuing_organization,
                        certification.credential_id or "",
                    ],
                    f"{certification.name} from {certification.issuing_organization}",
                    rank=2,
                )
            )
        for education in candidate.education:
            evidence.append(
                self._evidence_item(
                    ResumeSectionType.EDUCATION,
                    education.id,
                    f"{education.degree} at {education.institution}",
                    [
                        education.institution,
                        education.degree,
                        education.field_of_study or "",
                        education.description or "",
                    ],
                    education.description,
                    rank=1,
                )
            )
        return evidence

    def _coverage(self, terms: list[str], evidence: list[EvidenceItem]) -> CoverageResult:
        """Measure unique supported terms and collect their evidence."""
        matched: list[str] = []
        missing: list[str] = []
        evidence_by_term: dict[str, list[EvidenceReference]] = {}
        for term in self._deduplicate(terms):
            references = [
                item.reference.model_copy(update={"matched_terms": [term]})
                for item in evidence
                if self._matches(term, item)
            ]
            if references:
                matched.append(term)
                evidence_by_term[term] = references
            else:
                missing.append(term)
        return CoverageResult(
            matched=matched,
            missing=missing,
            score=self._ratio_score(len(matched), len(matched) + len(missing)),
            evidence_by_term=evidence_by_term,
        )

    def _evidence_score(
        self,
        evidence: list[EvidenceItem],
        *,
        terms: list[str],
        source_types: set[ResumeSectionType],
    ) -> Decimal:
        """Measure requirement coverage within selected source types."""
        scoped_evidence = [item for item in evidence if item.reference.source_type in source_types]
        return self._coverage(terms, scoped_evidence).score if terms else Decimal("50.00")

    def _experience_score(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
    ) -> tuple[Decimal, Decimal]:
        """Estimate candidate experience conservatively and compare it to the requirement."""
        skill_years = [skill.years_of_experience for skill in candidate.skills]
        work_years = sum(
            (
                Decimal(str(self._duration_years(experience.start_date, experience.end_date)))
                for experience in candidate.work_experiences
            ),
            start=ZERO,
        )
        candidate_years = max([work_years, *skill_years], default=ZERO)
        required_years = job_analysis.estimated_years_min
        if required_years is None:
            return (Decimal("50.00") if candidate_years == ZERO else HUNDRED), candidate_years
        if required_years == 0 or candidate_years >= required_years:
            return HUNDRED, candidate_years
        return self._bounded_score(
            candidate_years / Decimal(required_years) * HUNDRED
        ), candidate_years

    def _education_score(self, candidate: CandidateProfile, job_analysis: JobAnalysis) -> Decimal:
        """Score education conservatively for an explicit degree requirement."""
        qualifications = " ".join(job_analysis.qualifications).lower()
        requires_degree = any(term in qualifications for term in ("degree", "bachelor", "master"))
        if not requires_degree:
            return Decimal("50.00")
        return HUNDRED if candidate.education else ZERO

    def _relevant_education(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
    ) -> list[EvidenceReference]:
        """Return education records when the posting contains an explicit degree requirement."""
        qualifications = " ".join(job_analysis.qualifications).lower()
        if not any(term in qualifications for term in ("degree", "bachelor", "master")):
            return []
        return [
            EvidenceReference(
                source_type=ResumeSectionType.EDUCATION,
                source_id=education.id,
                label=f"{education.degree} at {education.institution}",
                excerpt=education.description,
            )
            for education in candidate.education
        ]

    def _match_breakdown(
        self,
        *,
        keyword_score: Decimal,
        skill_score: Decimal,
        technology_score: Decimal,
        experience_score: Decimal,
        project_score: Decimal,
        education_score: Decimal,
        missing_skills: list[str],
        missing_technologies: list[str],
    ) -> MatchBreakdown:
        """Combine explainable score components and penalize missing required evidence."""
        weighted = (
            keyword_score * Decimal("0.20")
            + skill_score * Decimal("0.25")
            + technology_score * Decimal("0.25")
            + experience_score * Decimal("0.15")
            + project_score * Decimal("0.10")
            + education_score * Decimal("0.05")
        )
        penalty = min(Decimal("20"), Decimal(4 * (len(missing_skills) + len(missing_technologies))))
        overall = self._bounded_score(weighted - penalty)
        return MatchBreakdown(
            overall_match_score=overall,
            keyword_match_score=keyword_score,
            skills_match_score=skill_score,
            technology_match_score=technology_score,
            experience_match_score=experience_score,
            project_match_score=project_score,
            education_match_score=education_score,
            quality=self._quality(overall),
        )

    def _suggested_summary(
        self,
        candidate: CandidateProfile,
        job_analysis: JobAnalysis,
        matched_terms: list[str],
    ) -> str:
        """Build a conservative summary using only candidate-supported terms."""
        terms = self._deduplicate(matched_terms)[:5]
        base = candidate.headline or f"Candidate for {job_analysis.normalized_title}"
        if terms:
            return f"{base} with knowledge-base evidence in {', '.join(terms)}."
        return f"{base}. Review the knowledge base before adding role-specific claims."

    @staticmethod
    def _suggested_sections(
        relevant_projects: list[EvidenceReference],
        relevant_experiences: list[EvidenceReference],
        candidate: CandidateProfile,
    ) -> list[ResumeSectionType]:
        """Choose an ordered resume structure based on available evidence."""
        sections = [ResumeSectionType.SUMMARY, ResumeSectionType.SKILLS]
        if relevant_experiences or candidate.work_experiences:
            sections.append(ResumeSectionType.EXPERIENCE)
        if relevant_projects or candidate.projects:
            sections.append(ResumeSectionType.PROJECTS)
        if candidate.education:
            sections.append(ResumeSectionType.EDUCATION)
        if candidate.certifications:
            sections.append(ResumeSectionType.CERTIFICATIONS)
        return sections

    @staticmethod
    def _strengths(
        skills: CoverageResult,
        technologies: CoverageResult,
        projects: list[EvidenceReference],
        experiences: list[EvidenceReference],
    ) -> list[str]:
        """Describe the strongest evidence-backed match signals."""
        strengths = []
        if skills.matched:
            strengths.append(f"Supported required skills: {', '.join(skills.matched)}")
        if technologies.matched:
            strengths.append(f"Supported required technologies: {', '.join(technologies.matched)}")
        if projects:
            strengths.append(
                f"Relevant project evidence: {', '.join(item.label for item in projects)}"
            )
        if experiences:
            strengths.append(
                f"Relevant work evidence: {', '.join(item.label for item in experiences)}"
            )
        return strengths

    @staticmethod
    def _weaknesses(
        missing_skills: list[str],
        missing_technologies: list[str],
        required_years: int | None,
        candidate_years: Decimal,
    ) -> list[str]:
        """Describe evidence gaps without inventing candidate claims."""
        weaknesses = []
        if missing_skills:
            weaknesses.append(f"Missing required skill evidence: {', '.join(missing_skills)}")
        if missing_technologies:
            weaknesses.append(
                f"Missing required technology evidence: {', '.join(missing_technologies)}"
            )
        if required_years is not None and candidate_years < required_years:
            weaknesses.append(
                f"Estimated experience evidence is {candidate_years} years; role requests "
                f"at least {required_years} years."
            )
        return weaknesses

    def _missing_terms(self, terms: list[str], evidence: list[EvidenceItem]) -> list[str]:
        """Return terms that have no candidate evidence."""
        return self._coverage(terms, evidence).missing

    @classmethod
    def _cloud_certification_note(cls, term: str, evidence: list[EvidenceItem]) -> str | None:
        """Return nuanced cloud-certification wording for coursework evidence."""
        normalized_term = cls._normalize(term)
        cloud_terms = {
            "gcp",
            "google cloud",
            "vertex ai",
            "bigquery ml",
            "cloud infrastructure",
            "cloud ai",
        }
        if not any(value in normalized_term for value in cloud_terms):
            return None
        evidence_text = " ".join(
            f"{item.reference.label} {item.reference.excerpt or ''}" for item in evidence
        ).casefold()
        if not any(
            value in evidence_text for value in ("google cloud", "vertex ai", "bigquery ml")
        ):
            return None
        return (
            "Can mention Google Cloud ML certifications and coursework, but avoid claiming "
            "production GCP deployment experience unless supported."
        )

    @classmethod
    def _matches(cls, term: str, item: EvidenceItem) -> bool:
        """Match a canonical requirement against searchable candidate evidence."""
        normalized_term = cls._normalize(term)
        return bool(normalized_term) and normalized_term in item.searchable_text

    @classmethod
    def _evidence_item(
        cls,
        source_type: ResumeSectionType,
        source_id: UUID,
        label: str,
        searchable_values: list[str],
        excerpt: str | None,
        *,
        rank: int,
    ) -> EvidenceItem:
        """Create an indexed evidence record."""
        return EvidenceItem(
            reference=EvidenceReference(
                source_type=source_type,
                source_id=source_id,
                label=label,
                excerpt=excerpt,
            ),
            searchable_text=cls._normalize(" ".join(searchable_values)),
            rank=rank,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize common variants before deterministic matching."""
        normalized = value.lower()
        replacements = {
            "apis": "api",
            "databases": "database",
            "workflows": "workflow",
            "technologies": "technology",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return re.sub(r"[^a-z0-9+#.]+", " ", normalized).strip()

    @staticmethod
    def _ratio_score(matched_count: int, total_count: int) -> Decimal:
        """Calculate a bounded percentage for unique-term coverage."""
        if total_count == 0:
            return Decimal("50.00")
        return DeterministicResumeIntelligenceEngine._bounded_score(
            Decimal(matched_count) / Decimal(total_count) * HUNDRED
        )

    @staticmethod
    def _bounded_score(score: Decimal) -> Decimal:
        """Clamp and round a percentage to two decimal places."""
        return max(ZERO, min(HUNDRED, score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _quality(score: Decimal) -> MatchQuality:
        """Map a score to an explainable quality band."""
        if score >= 85:
            return MatchQuality.EXCELLENT
        if score >= 70:
            return MatchQuality.STRONG
        if score >= 50:
            return MatchQuality.MODERATE
        if score >= 30:
            return MatchQuality.WEAK
        return MatchQuality.LIMITED

    @staticmethod
    def _duration_years(start_date: date, end_date: date | None) -> float:
        """Return an approximate duration in years for experience scoring."""
        effective_end = end_date or datetime.now(UTC).date()
        return max(0.0, (effective_end - start_date).days / 365.25)

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        """Deduplicate case-insensitively while preserving source order."""
        seen: set[str] = set()
        unique = []
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(value)
        return unique

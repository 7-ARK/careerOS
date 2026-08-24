"""Requirement extraction and evidence-grounded candidate-job matching."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.features.resume_intelligence.retrieval import (
    CandidateEvidenceRetriever,
    normalize_text,
)
from app.models import CandidateProfile, JobAnalysis, JobDescription
from app.models.enums import RequirementMatchStatus
from app.repositories import (
    CandidateProfileRepository,
    JobAnalysisRepository,
    JobDescriptionRepository,
)
from app.schemas import (
    CandidateEvidence,
    EvidenceCoverageBreakdown,
    JobRequirement,
    MatchExplanation,
    RequirementEvidenceMatch,
    RetrievedCandidateEvidence,
    StructuredJobRequirements,
)
from app.services.exceptions import (
    JobAnalysisNotFoundError,
    JobDescriptionNotFoundError,
    ProfileNotFoundError,
)

REQUIRED_WEIGHT = Decimal("2")
PREFERRED_WEIGHT = Decimal("1")
MATCHED_VALUE = Decimal("1")
PARTIAL_VALUE = Decimal("0.5")
AI_ML_TERMS = {
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml",
    "llm",
    "rag",
    "langchain",
    "pytorch",
    "tensorflow",
    "scikit learn",
    "openai",
}
BACKEND_TERMS = {
    "api",
    "fastapi",
    "django",
    "flask",
    "python",
    "postgresql",
    "sql",
    "redis",
    "backend",
}
CLOUD_TERMS = {
    "aws",
    "azure",
    "gcp",
    "google cloud",
    "docker",
    "kubernetes",
    "cloud",
    "deployment",
    "ci cd",
}
EXPLICIT_EVIDENCE_RULES: dict[str, tuple[str, ...]] = {
    "AWS": ("aws", "amazon web services", "amazon ec2", "amazon s3", "aws lambda"),
    "Kubernetes": ("kubernetes", "k8s"),
    "CI/CD": (
        "ci cd",
        "continuous integration",
        "continuous delivery",
        "continuous deployment",
    ),
}
EXPERIENCE_RANGE_PATTERN = re.compile(
    r"\b(?P<minimum>\d+(?:\.\d+)?)\s*(?:-|\u2013|\u2014|to)\s*"
    r"(?P<maximum>\d+(?:\.\d+)?)\s*years?\b",
    flags=re.I,
)
EXPERIENCE_MINIMUM_PATTERN = re.compile(
    r"(?:\bat\s+least\s+)?\b(?P<minimum>\d+(?:\.\d+)?)\s*\+?\s*years?\b",
    flags=re.I,
)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "build",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "using",
    "with",
    "work",
}


class EvidenceMatchService:
    """Map structured job requirements to verified candidate evidence."""

    def __init__(
        self,
        session: Session,
        *,
        retriever: CandidateEvidenceRetriever | None = None,
    ) -> None:
        self.session = session
        self.profiles = CandidateProfileRepository(session)
        self.job_descriptions = JobDescriptionRepository(session)
        self.job_analyses = JobAnalysisRepository(session)
        self.retriever = retriever or CandidateEvidenceRetriever()

    def explain(
        self,
        candidate_profile_id: UUID,
        job_description_id: UUID,
        *,
        top_k: int = 3,
    ) -> MatchExplanation:
        """Return transparent requirement statuses, citations, and a calculated score."""
        candidate = self._require_candidate(candidate_profile_id)
        job = self._require_job(job_description_id)
        analysis = self.job_analyses.get_latest_for_job_description(job.id)
        if analysis is None:
            raise JobAnalysisNotFoundError(
                f"job description {job_description_id} has not been analyzed"
            )
        requirements = self.structured_requirements(job, analysis)
        matches = [
            self._match_requirement(candidate, requirement, top_k=top_k)
            for requirement in requirements.requirements
        ]
        coverage = self.calculate_coverage(matches)
        strongest = [
            match.requirement.text
            for match in matches
            if match.status == RequirementMatchStatus.MATCHED
            and match.requirement.priority != "context"
        ]
        partial = [
            match.requirement.text
            for match in matches
            if match.status == RequirementMatchStatus.PARTIALLY_MATCHED
            and match.requirement.priority != "context"
        ]
        missing = [
            match.requirement.text
            for match in matches
            if match.status == RequirementMatchStatus.NOT_EVIDENCED
            and match.requirement.priority != "context"
        ]
        relevant_projects = self._unique_evidence(
            evidence
            for match in matches
            for evidence in match.supporting_evidence
            if evidence.category == "project"
        )[:5]
        supported_terms = {
            normalize_text(match.requirement.text)
            for match in matches
            if match.status
            in {RequirementMatchStatus.MATCHED, RequirementMatchStatus.PARTIALLY_MATCHED}
        }
        supported_ats = [
            keyword
            for keyword in requirements.important_ats_keywords
            if any(
                normalize_text(keyword) in requirement_text
                or requirement_text in normalize_text(keyword)
                for requirement_text in supported_terms
            )
        ]
        unsupported_ats = [
            keyword
            for keyword in requirements.important_ats_keywords
            if keyword not in supported_ats
        ]
        return MatchExplanation(
            candidate_profile_id=candidate.id,
            job_description_id=job.id,
            job_analysis_id=analysis.id,
            requirements=requirements,
            requirement_matches=matches,
            evidence_coverage=coverage,
            overall_fit_summary=self._fit_summary(coverage, strongest, partial, missing),
            strongest_matches=strongest[:5],
            partial_matches=partial,
            missing_requirements=missing,
            relevant_projects=relevant_projects,
            supported_ats_keywords=supported_ats,
            unsupported_ats_keywords=unsupported_ats,
            learning_priorities=[
                f"Build or document verified evidence for {requirement}."
                for requirement in missing[:5]
            ],
            interview_preparation_topics=[*partial, *missing][:6],
            retrieval_provider=self.retriever.provider.provider_name,
            embedding_model=self.retriever.provider.model_name,
        )

    @classmethod
    def structured_requirements(
        cls,
        job: JobDescription,
        analysis: JobAnalysis,
    ) -> StructuredJobRequirements:
        """Project the existing validated job analysis into recruiter-facing requirements."""
        canonical_payloads = analysis.match_relevant_signals.get("canonical_requirements", [])
        requirements = cls._requirements_from_canonical(analysis, canonical_payloads)
        if not requirements:
            requirements = cls._legacy_requirements(analysis)

        all_technology_terms = [
            *analysis.required_technologies,
            *analysis.preferred_technologies,
            *analysis.required_skills,
            *analysis.preferred_skills,
        ]
        ai_ml = cls._terms_in_catalog(all_technology_terms, AI_ML_TERMS)
        backend = cls._terms_in_catalog(all_technology_terms, BACKEND_TERMS)
        cloud = cls._terms_in_catalog(
            [*all_technology_terms, *analysis.responsibilities], CLOUD_TERMS
        )
        required_experience = (
            f"{analysis.estimated_years_min}+ years"
            if analysis.estimated_years_min is not None
            else None
        )
        education = [
            value
            for value in analysis.qualifications
            if any(term in value.casefold() for term in ("degree", "bachelor", "master"))
        ]
        return StructuredJobRequirements(
            job_description_id=job.id,
            job_analysis_id=analysis.id,
            job_title=analysis.normalized_title,
            company=job.company_name,
            location=job.location,
            employment_type=job.employment_type,
            seniority=analysis.seniority_level,
            required_skills=[*analysis.required_skills, *analysis.required_technologies],
            preferred_skills=[*analysis.preferred_skills, *analysis.preferred_technologies],
            responsibilities=analysis.responsibilities,
            required_experience=required_experience,
            education_requirements=education,
            ai_ml_technologies=ai_ml,
            backend_technologies=backend,
            cloud_deployment_requirements=cloud,
            important_ats_keywords=analysis.ats_keywords,
            requirements=requirements,
            original_job_description=job.description_text,
        )

    @classmethod
    def _requirements_from_canonical(
        cls,
        analysis: JobAnalysis,
        payloads: object,
    ) -> list[JobRequirement]:
        """Build score rows from original required/preferred JD bullets only."""
        if not isinstance(payloads, list):
            return []
        requirements: list[JobRequirement] = []
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            text = payload.get("text")
            priority = payload.get("priority")
            if not isinstance(text, str) or not text.strip() or priority not in {
                "required",
                "preferred",
            }:
                continue
            alternatives = [
                value.strip()
                for value in payload.get("alternatives", [])
                if isinstance(value, str) and value.strip()
            ]
            requested_logic = payload.get("logic")
            logic = "any" if requested_logic == "any" and len(alternatives) >= 2 else "all"
            requirements.append(
                cls._requirement(
                    analysis.id,
                    text.strip(),
                    str(payload.get("kind", "skill")),
                    str(priority),
                    logic=logic,
                    alternatives=alternatives if logic == "any" else [],
                )
            )
        return requirements

    @classmethod
    def _legacy_requirements(cls, analysis: JobAnalysis) -> list[JobRequirement]:
        """Preserve matching for analyses stored before canonical bullet extraction."""
        requirements: list[JobRequirement] = []
        group_payloads = analysis.match_relevant_signals.get("requirement_groups", [])
        grouped_terms: set[str] = set()
        grouped_texts: set[str] = set()
        if isinstance(group_payloads, list):
            for payload in group_payloads:
                if not isinstance(payload, dict):
                    continue
                alternatives = [
                    value
                    for value in payload.get("alternatives", [])
                    if isinstance(value, str) and value.strip()
                ]
                if len(alternatives) < 2:
                    continue
                grouped_terms.update(normalize_text(value) for value in alternatives)
                group_text = str(payload.get("text", " or ".join(alternatives)))
                grouped_texts.add(normalize_text(group_text))
                requirements.append(
                    cls._requirement(
                        analysis.id,
                        group_text,
                        str(payload.get("kind", "skill")),
                        str(payload.get("priority", "required")),
                        logic="any",
                        alternatives=alternatives,
                    )
                )
        for value in analysis.required_skills:
            if normalize_text(value) not in grouped_terms:
                requirements.append(cls._requirement(analysis.id, value, "skill", "required"))
        for value in analysis.required_technologies:
            if normalize_text(value) not in grouped_terms:
                requirements.append(cls._requirement(analysis.id, value, "technology", "required"))
        for value in analysis.preferred_skills:
            if normalize_text(value) not in grouped_terms:
                requirements.append(cls._requirement(analysis.id, value, "skill", "preferred"))
        for value in analysis.preferred_technologies:
            if normalize_text(value) not in grouped_terms:
                requirements.append(cls._requirement(analysis.id, value, "technology", "preferred"))
        if analysis.estimated_years_min is not None:
            experience = f"At least {analysis.estimated_years_min} years of relevant experience"
            requirements.append(
                cls._requirement(analysis.id, experience, "experience", "required")
            )
        education = [
            value
            for value in analysis.qualifications
            if any(term in value.casefold() for term in ("degree", "bachelor", "master"))
        ]
        preferred_qualifications = analysis.match_relevant_signals.get(
            "preferred_qualifications", []
        )
        preferred_qualification_text = {
            normalize_text(value)
            for value in preferred_qualifications
            if isinstance(value, str)
        }
        for value in education:
            normalized_value = normalize_text(value)
            if normalized_value in grouped_terms or any(
                normalized_value in group_text or group_text in normalized_value
                for group_text in grouped_texts
            ):
                continue
            priority = (
                "preferred"
                if normalize_text(value) in preferred_qualification_text
                else "required"
            )
            requirements.append(cls._requirement(analysis.id, value, "education", priority))
        for value in analysis.responsibilities:
            requirements.append(cls._requirement(analysis.id, value, "responsibility", "context"))
        return requirements

    @staticmethod
    def calculate_coverage(
        matches: list[RequirementEvidenceMatch],
    ) -> EvidenceCoverageBreakdown:
        """Calculate weighted evidence coverage in code, excluding context-only rows."""
        earned = Decimal("0")
        possible = Decimal("0")
        counts = {status: 0 for status in RequirementMatchStatus}
        for match in matches:
            counts[match.status] += 1
            if (
                match.requirement.priority == "context"
                or match.status == RequirementMatchStatus.NOT_APPLICABLE
            ):
                continue
            weight = (
                REQUIRED_WEIGHT
                if match.requirement.priority == "required"
                else PREFERRED_WEIGHT
            )
            possible += weight
            if match.status == RequirementMatchStatus.MATCHED:
                earned += weight * MATCHED_VALUE
            elif match.status == RequirementMatchStatus.PARTIALLY_MATCHED:
                earned += weight * PARTIAL_VALUE
        score = (
            (earned / possible * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if possible
            else Decimal("0.00")
        )
        return EvidenceCoverageBreakdown(
            score=score,
            formula=(
                "100 * earned weight / possible weight; required requirements weigh 2, "
                "preferred requirements weigh 1, matched earns 1, partial earns 0.5, "
                "and context/not-applicable rows are excluded."
            ),
            earned_weight=earned,
            possible_weight=possible,
            matched_count=counts[RequirementMatchStatus.MATCHED],
            partially_matched_count=counts[RequirementMatchStatus.PARTIALLY_MATCHED],
            not_evidenced_count=counts[RequirementMatchStatus.NOT_EVIDENCED],
            not_applicable_count=counts[RequirementMatchStatus.NOT_APPLICABLE],
        )

    def _match_requirement(
        self,
        candidate: CandidateProfile,
        requirement: JobRequirement,
        *,
        top_k: int,
    ) -> RequirementEvidenceMatch:
        if requirement.kind == "experience":
            return self._match_experience_requirement(candidate, requirement)
        if requirement.logic == "any":
            evaluations = [
                (alternative, *self._evaluate_text(candidate, alternative, top_k=top_k))
                for alternative in requirement.alternatives
            ]
            rank = {
                RequirementMatchStatus.NOT_EVIDENCED: 0,
                RequirementMatchStatus.PARTIALLY_MATCHED: 1,
                RequirementMatchStatus.MATCHED: 2,
                RequirementMatchStatus.NOT_APPLICABLE: -1,
            }
            alternative, status, citations = max(
                evaluations,
                key=lambda item: (
                    rank[item[1]],
                    max((citation.lexical_score for citation in item[2]), default=Decimal("0")),
                ),
            )
            if status == RequirementMatchStatus.MATCHED:
                explanation = f"Verified evidence satisfies the allowed alternative: {alternative}."
                recommendation = None
            elif status == RequirementMatchStatus.PARTIALLY_MATCHED:
                explanation = f"Evidence partially supports the allowed alternative: {alternative}."
                recommendation = (
                    "Add stronger verified evidence for one of: "
                    f"{', '.join(requirement.alternatives)}."
                )
            else:
                explanation = "No verified evidence supports any allowed alternative."
                recommendation = (
                    "Build verified evidence for one of: "
                    f"{', '.join(requirement.alternatives)}."
                )
            return RequirementEvidenceMatch(
                requirement=requirement,
                status=status,
                supporting_evidence=citations,
                explanation=explanation,
                recommendation=recommendation,
            )

        status, citations = self._evaluate_text(candidate, requirement.text, top_k=top_k)
        meaningful = self._signal_tokens(requirement.text)
        if not meaningful:
            return RequirementEvidenceMatch(
                requirement=requirement,
                status=RequirementMatchStatus.NOT_APPLICABLE,
                explanation="The requirement contains no specific evidence signal to verify.",
            )
        if status == RequirementMatchStatus.MATCHED:
            explanation = "Verified candidate evidence directly supports this requirement."
            recommendation = None
        elif status == RequirementMatchStatus.PARTIALLY_MATCHED:
            explanation = (
                "Verified evidence overlaps with part of the requirement but does not prove the "
                "full scope."
            )
            recommendation = (
                f"Strengthen the candidate profile with a verified outcome demonstrating "
                f"{requirement.text}."
            )
        else:
            explanation = "No verified candidate evidence supports this requirement."
            recommendation = (
                f"Add a verified project or experience demonstrating {requirement.text}; "
                "do not add it to the resume before evidence exists."
            )
            citations = []
        return RequirementEvidenceMatch(
            requirement=requirement,
            status=status,
            supporting_evidence=citations,
            explanation=explanation,
            recommendation=recommendation,
        )

    def _evaluate_text(
        self,
        candidate: CandidateProfile,
        text: str,
        *,
        top_k: int,
    ) -> tuple[RequirementMatchStatus, list[RetrievedCandidateEvidence]]:
        explicit_rules = self._explicit_rules_for_requirement(text)
        if explicit_rules:
            return self._evaluate_explicit_evidence(candidate, explicit_rules)
        retrieved = self.retriever.retrieve(candidate, text, top_k=top_k)
        citations = [
            item
            for item in retrieved
            if item.lexical_score > 0 or item.vector_score >= Decimal("0.45")
        ]
        best_lexical = max((item.lexical_score for item in citations), default=Decimal("0"))
        exact = any(normalize_text(text) in normalize_text(item.text) for item in citations)
        if citations and (exact or best_lexical >= Decimal("0.65")):
            return RequirementMatchStatus.MATCHED, citations
        if citations and best_lexical >= Decimal("0.25"):
            return RequirementMatchStatus.PARTIALLY_MATCHED, citations
        return RequirementMatchStatus.NOT_EVIDENCED, []

    def _evaluate_explicit_evidence(
        self,
        candidate: CandidateProfile,
        rules: list[tuple[str, tuple[str, ...]]],
    ) -> tuple[RequirementMatchStatus, list[RetrievedCandidateEvidence]]:
        """Require named cloud/tool evidence instead of semantic neighborhood matches."""
        evidence = self.retriever.collect(candidate)
        matched_rules: list[str] = []
        citations: list[RetrievedCandidateEvidence] = []
        for label, aliases in rules:
            matched = [
                item
                for item in evidence
                if any(self._contains_phrase(item.text, alias) for alias in aliases)
            ]
            if matched:
                matched_rules.append(label)
                citations.extend(
                    self._direct_citation(
                        item,
                        f"Verified evidence explicitly names {label} or an accepted alias.",
                    )
                    for item in matched
                )
        unique = self._unique_evidence(citations)
        if len(matched_rules) == len(rules):
            return RequirementMatchStatus.MATCHED, unique
        if matched_rules:
            return RequirementMatchStatus.PARTIALLY_MATCHED, unique
        return RequirementMatchStatus.NOT_EVIDENCED, []

    def _match_experience_requirement(
        self,
        candidate: CandidateProfile,
        requirement: JobRequirement,
    ) -> RequirementEvidenceMatch:
        """Compare required years with merged, non-overlapping employment date ranges."""
        expected = self._experience_range(requirement.text)
        years = self._candidate_experience_years(candidate)
        evidence = [
            item
            for item in self.retriever.collect(candidate)
            if item.category == "experience"
        ]
        citations = [
            self._direct_citation(
                item,
                "Employment dates contribute to the non-overlapping experience calculation.",
            )
            for item in evidence
        ]
        if expected is None:
            return RequirementEvidenceMatch(
                requirement=requirement,
                status=RequirementMatchStatus.NOT_APPLICABLE,
                explanation="The experience requirement did not contain a parseable year range.",
            )
        minimum, maximum = expected
        if not evidence:
            return RequirementEvidenceMatch(
                requirement=requirement,
                status=RequirementMatchStatus.NOT_EVIDENCED,
                explanation="No dated employment history is available to verify experience length.",
                recommendation=(
                    "Add verified employment or internship dates before claiming experience."
                ),
            )
        if maximum is not None and years > maximum:
            return RequirementEvidenceMatch(
                requirement=requirement,
                status=RequirementMatchStatus.PARTIALLY_MATCHED,
                supporting_evidence=citations,
                explanation=(
                    f"Dated, non-overlapping employment history totals {years:.2f} years, "
                    f"which exceeds the stated {minimum.normalize()}-"
                    f"{maximum.normalize()} year range. Experience is evidenced, but the "
                    "range fit is not exact."
                ),
                recommendation=(
                    "Treat this as a role-level fit question for human review, not as missing "
                    "experience."
                ),
            )
        if years >= minimum:
            range_text = (
                f"{minimum.normalize()}-{maximum.normalize()} years"
                if maximum is not None
                else f"at least {minimum.normalize()} years"
            )
            return RequirementEvidenceMatch(
                requirement=requirement,
                status=RequirementMatchStatus.MATCHED,
                supporting_evidence=citations,
                explanation=(
                    f"Dated, non-overlapping employment history totals {years:.2f} years, "
                    f"satisfying the stated {range_text} requirement."
                ),
            )
        status = (
            RequirementMatchStatus.PARTIALLY_MATCHED
            if minimum > 0 and years >= minimum / Decimal("2")
            else RequirementMatchStatus.NOT_EVIDENCED
        )
        return RequirementEvidenceMatch(
            requirement=requirement,
            status=status,
            supporting_evidence=(
                citations if status == RequirementMatchStatus.PARTIALLY_MATCHED else []
            ),
            explanation=(
                f"Dated, non-overlapping employment history totals {years:.2f} years; "
                f"the requirement asks for at least {minimum.normalize()} years."
            ),
            recommendation="Add verified dated experience before claiming the full requirement.",
        )

    @classmethod
    def _explicit_rules_for_requirement(
        cls,
        text: str,
    ) -> list[tuple[str, tuple[str, ...]]]:
        """Return strict rules only for explicitly named high-risk infrastructure terms."""
        return [
            (label, aliases)
            for label, aliases in EXPLICIT_EVIDENCE_RULES.items()
            if any(cls._contains_phrase(text, alias) for alias in aliases)
        ]

    @staticmethod
    def _contains_phrase(value: str, phrase: str) -> bool:
        """Match a normalized token phrase without accepting substring collisions."""
        value_tokens = normalize_text(value).split()
        phrase_tokens = normalize_text(phrase).split()
        width = len(phrase_tokens)
        return bool(width) and any(
            value_tokens[index : index + width] == phrase_tokens
            for index in range(len(value_tokens) - width + 1)
        )

    @staticmethod
    def _experience_range(text: str) -> tuple[Decimal, Decimal | None] | None:
        """Parse bounded and minimum year requirements without inferring missing values."""
        bounded = EXPERIENCE_RANGE_PATTERN.search(text)
        if bounded:
            return Decimal(bounded.group("minimum")), Decimal(bounded.group("maximum"))
        minimum = EXPERIENCE_MINIMUM_PATTERN.search(text)
        if minimum:
            return Decimal(minimum.group("minimum")), None
        return None

    @staticmethod
    def _candidate_experience_years(
        candidate: CandidateProfile,
        *,
        as_of: date | None = None,
    ) -> Decimal:
        """Sum merged employment intervals so overlapping roles are never double-counted."""
        effective_today = as_of or date.today()
        intervals = sorted(
            (
                experience.start_date,
                min(experience.end_date or effective_today, effective_today),
            )
            for experience in candidate.work_experiences
            if experience.start_date <= effective_today
        )
        merged: list[tuple[date, date]] = []
        for start, end in intervals:
            if end < start:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        days = sum((end - start).days for start, end in merged)
        return (Decimal(days) / Decimal("365.2425")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _direct_citation(
        evidence: CandidateEvidence,
        explanation: str,
    ) -> RetrievedCandidateEvidence:
        """Convert verified source evidence into a transparent direct-match citation."""
        return RetrievedCandidateEvidence(
            **evidence.model_dump(),
            retrieval_score=Decimal("1"),
            lexical_score=Decimal("1"),
            vector_score=Decimal("0"),
            why_retrieved=explanation,
        )

    def _require_candidate(self, candidate_profile_id: UUID) -> CandidateProfile:
        candidate = self.profiles.get_complete(candidate_profile_id)
        if candidate is None:
            raise ProfileNotFoundError(f"candidate profile {candidate_profile_id} was not found")
        return candidate

    def _require_job(self, job_description_id: UUID) -> JobDescription:
        job = self.job_descriptions.get(job_description_id)
        if job is None:
            raise JobDescriptionNotFoundError(
                f"job description {job_description_id} was not found"
            )
        return job

    @staticmethod
    def _requirement(
        analysis_id: UUID,
        text: str,
        kind: str,
        priority: str,
        *,
        logic: str = "all",
        alternatives: list[str] | None = None,
    ) -> JobRequirement:
        digest = hashlib.sha256(
            f"{analysis_id}:{priority}:{kind}:{logic}:{normalize_text(text)}".encode()
        ).hexdigest()[:16]
        return JobRequirement(
            requirement_id=f"req-{digest}",
            text=text,
            kind=kind,
            priority=priority,
            logic=logic,
            alternatives=alternatives or [],
        )

    @staticmethod
    def _terms_in_catalog(values: list[str], catalog: set[str]) -> list[str]:
        return list(
            dict.fromkeys(
                value
                for value in values
                if any(term in normalize_text(value) for term in catalog)
            )
        )

    @staticmethod
    def _signal_tokens(value: str) -> set[str]:
        return {
            token
            for token in normalize_text(value).split()
            if token not in STOP_WORDS and len(token) > 1
        }

    @staticmethod
    def _unique_evidence(
        evidence: Iterable[RetrievedCandidateEvidence],
    ) -> list[RetrievedCandidateEvidence]:
        unique: dict[str, RetrievedCandidateEvidence] = {}
        for item in evidence:
            current = unique.get(item.evidence_id)
            if current is None or item.retrieval_score > current.retrieval_score:
                unique[item.evidence_id] = item
        return sorted(
            unique.values(), key=lambda item: (-item.retrieval_score, item.evidence_id)
        )

    @staticmethod
    def _fit_summary(
        coverage: EvidenceCoverageBreakdown,
        strongest: list[str],
        partial: list[str],
        missing: list[str],
    ) -> str:
        return (
            f"Evidence Coverage Score: {coverage.score}%. "
            f"Verified evidence fully supports {len(strongest)} scored requirements, "
            f"partially supports {len(partial)}, and does not evidence {len(missing)}."
        )

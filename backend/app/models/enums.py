"""Enumerations shared by knowledge-base models and schemas."""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    """Lifecycle states for a job application."""

    NOT_APPLIED = "not_applied"
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"


class RemotePreference(StrEnum):
    """Preferred workplace arrangement."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    FLEXIBLE = "flexible"


class RelocationPreference(StrEnum):
    """Candidate willingness to relocate."""

    WILLING = "willing"
    NOT_WILLING = "not_willing"
    CONDITIONAL = "conditional"


class ResumeStyle(StrEnum):
    """Supported resume presentation styles."""

    ATS_FOCUSED = "ats_focused"
    CLASSIC = "classic"
    MINIMAL = "minimal"
    MODERN = "modern"


class SourcePlatform(StrEnum):
    """Common job-posting sources while allowing custom stored values."""

    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    COMPANY_SITE = "company_site"
    REFERRAL = "referral"
    OTHER = "other"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    """Common employment arrangements while allowing custom stored values."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    OTHER = "other"
    UNKNOWN = "unknown"


class WorkplaceType(StrEnum):
    """Common workplace arrangements while allowing custom stored values."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    OTHER = "other"
    UNKNOWN = "unknown"


class SeniorityLevel(StrEnum):
    """Normalized seniority levels extracted from job descriptions."""

    INTERN = "intern"
    JUNIOR = "junior"
    MID_LEVEL = "mid_level"
    SENIOR = "senior"
    LEAD = "lead"
    STAFF = "staff"
    PRINCIPAL = "principal"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class ResumeDraftStatus(StrEnum):
    """Lifecycle states for a structured resume draft."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ResumeSectionType(StrEnum):
    """Supported structured resume sections."""

    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"


class MatchQuality(StrEnum):
    """Explainable candidate-job match quality bands."""

    EXCELLENT = "excellent"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    LIMITED = "limited"


class DocumentFormat(StrEnum):
    """Supported locally generated resume document formats."""

    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"


class DocumentGenerationStatus(StrEnum):
    """Lifecycle states for generated resume files."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ResumeTemplateName(StrEnum):
    """Code-based ATS-safe resume templates."""

    CLEAN_ATS = "clean_ats"
    MODERN_PROFESSIONAL = "modern_professional"


class PipelineStage(StrEnum):
    """Named stages in the manual end-to-end application pipeline."""

    JOB_IMPORT = "job_import"
    RESUME_ANALYSIS = "resume_analysis"
    RESUME_DRAFT = "resume_draft"
    RESUME_DRAFT_APPROVAL = "resume_draft_approval"
    DOCUMENT_GENERATION = "document_generation"
    APPLICATION_RECORD_UPDATE = "application_record_update"


class PipelineStatus(StrEnum):
    """Completion states returned by a successful pipeline run."""

    COMPLETED = "completed"


class CareerAnalysisStatus(StrEnum):
    """Persisted states for the human-reviewed golden career flow."""

    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class CareerAnalysisStage(StrEnum):
    """Inspectable bounded stages in the golden career flow."""

    PROFILE_VALIDATION = "profile_validation"
    JOB_IMPORT = "job_import"
    REQUIREMENT_EXTRACTION = "requirement_extraction"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    MATCH_ANALYSIS = "match_analysis"
    RESUME_DRAFT = "resume_draft"
    GROUNDING_VALIDATION = "grounding_validation"
    HUMAN_REVIEW = "human_review"
    DOCUMENT_EXPORT = "document_export"
    APPLICATION_TRACKING = "application_tracking"


class RequirementMatchStatus(StrEnum):
    """Evidence status assigned to one structured job requirement."""

    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    NOT_EVIDENCED = "not_evidenced"
    NOT_APPLICABLE = "not_applicable"

# Resume Intelligence Engine

The Resume Intelligence Engine compares structured candidate evidence with a
stored job analysis. It produces an auditable match assessment and an optional
resume draft plan without treating an uploaded resume as the source of truth.

## Purpose

Resume tailoring must begin with candidate-approved facts. The engine reads the
Candidate Knowledge Base, evaluates those facts against a `JobAnalysis`, and
stores a versioned `ResumeAnalysis`. A `ResumeDraft` is a derived artifact that
can later feed document generation after candidate review.

## Architecture

The engine follows the layered design used elsewhere in careerOS:

* SQLAlchemy models persist versioned analyses and generated draft plans.
* Pydantic schemas validate create, update, read, evidence, and score contracts.
* Repositories own persistence, latest-revision queries, listing, and status
  updates.
* `DeterministicResumeIntelligenceEngine` performs local evidence collection,
  matching, scoring, gap analysis, and recommendation generation.
* `ResumeIntelligenceService` owns transaction boundaries and API-ready
  workflows.

The deterministic engine is dependency-injection friendly. A future AI-assisted
implementation can use the same schemas and persistence layer while preserving
the local analyzer as a reproducible baseline.

## Data Flow

1. A candidate profile and a stored job analysis are loaded by UUID.
2. Candidate-owned skills, projects, work experience, education, and
   certifications are converted into evidence references.
3. Required and preferred job terms are compared with normalized candidate
   evidence.
4. The engine stores a `ResumeAnalysis` with score components, evidence,
   gaps, warnings, and tailoring recommendations.
5. When requested, the service derives a `ResumeDraft` plan from the analysis
   and Candidate Knowledge Base facts.
6. Later document generators can consume an approved draft without inventing
   candidate claims.

## Scoring Strategy

Deterministic v1 calculates a weighted score:

| Component | Weight |
| --- | ---: |
| Keyword coverage | 20% |
| Skill coverage | 25% |
| Technology coverage | 25% |
| Experience alignment | 15% |
| Project relevance | 10% |
| Education relevance | 5% |

The engine applies a conservative penalty for missing required skills and
technologies. Keyword coverage is deduplicated before scoring so repeated terms
do not inflate a candidate-job assessment.

Scores are persisted separately for later inspection and tuning. Match quality
labels provide a stable presentation layer while retaining numeric detail.

## Evidence and Truthfulness

Every recommended claim must be supported by Candidate Knowledge Base evidence.
Evidence references contain:

* Source entity type.
* Source entity UUID.
* Human-readable label.
* Matched terms.
* A concise source excerpt.

Projects and work experience receive the strongest evidence ranking because
they show applied work. Skills, certifications, and education can support a
recommendation but do not override missing applied evidence.

Unsupported required or preferred terms generate truthfulness warnings. The
engine may identify a gap such as Kubernetes or OpenAI, but it must never place
that gap into a recommended candidate claim.

## Database Design

`ResumeAnalysis` stores one versioned candidate-job assessment. It references a
`CandidateProfile` and a `JobAnalysis`, allowing later deterministic and
AI-assisted revisions to coexist. JSON fields preserve detailed evidence,
strengths, gaps, recommendations, and warnings while numeric columns keep score
filtering straightforward.

`ResumeDraft` stores an editable, reviewable plan derived from one analysis.
It includes target role, summary, ordered sections, ATS coverage lists,
truthfulness notes, and a lifecycle status: draft, reviewed, approved, or
archived.

## Limitations

Rule-based v1 uses normalized text matching. It intentionally does not infer
unstated capabilities, rewrite bullet points, generate document files, call an
OpenAI model, or calculate semantic similarity. Experience alignment is
conservative and should be tuned with measured product usage.

## Future OpenAI Plan

A future provider may improve semantic matching and phrasing while remaining
bounded by the same evidence references. Structured output should validate
against the existing schemas, preserve provider and prompt metadata, and
surface unsupported claims as warnings for candidate review.

## Resume Generation Roadmap

The next layer should convert an approved `ResumeDraft` into local DOCX and PDF
documents. Canva can be added later as an optional presentation adapter, not as
the source of candidate data. ATS tailoring, embeddings, LangGraph workflows,
and application-specific resume versions can build on the same analysis and
evidence contracts.

# Job Analyzer Engine

The Job Analyzer Engine converts captured job postings into structured,
machine-readable intelligence. Its output is designed for later use by resume
intelligence, ATS scoring, cover letters, application tracking, recommendation
agents, and platform integrations.

## Purpose

Raw job descriptions are inconsistent documents. The engine preserves the
original source text in `JobDescription` and stores derived `JobAnalysis`
revisions separately. Downstream systems can use a stable structure without
discarding the original posting or overwriting earlier analysis results.

## Architecture

The engine follows the same layering used by the Candidate Knowledge Base:

* SQLAlchemy models persist captured postings and versioned analysis revisions.
* Pydantic schemas validate create, update, read, provider, and search contracts.
* Repositories own CRUD operations, latest-revision queries, filtering, and
  search across source metadata and extracted signals.
* `JobAnalysisService` owns transaction boundaries and API-ready workflows.
* `BaseJobAnalyzer` defines a provider-independent extraction interface.
* `RuleBasedJobAnalyzer` implements deterministic local extraction.
* `FutureOpenAIJobAnalyzer` reserves the interface for structured AI output
  without importing or calling an OpenAI client.

## Data Flow

1. `JobDescriptionCreate` validates captured posting metadata and source text.
2. `JobAnalysisService.create_job_description` stores the original posting.
3. `JobAnalysisService.analyze_job_description` passes a `JobDescriptionInput`
   snapshot to the configured analyzer.
4. The analyzer emits a provider-independent `JobAnalysisResult`.
5. The service stores a versioned `JobAnalysis` revision.
6. Search and matching consumers read the latest revision while earlier
   revisions remain available for audit and re-analysis history.

## Extraction Strategy

Rule-based v1:

* Normalizes common job-title abbreviations and workplace suffixes.
* Infers seniority from title markers and explicit years of experience.
* Reads responsibility, qualification, and preference sections when present.
* Extracts common programming languages, frameworks, cloud tools, AI concepts,
  automation platforms, scraping tools, domain terms, and soft skills.
* Separates required from preferred skills and technologies using local context.
* Identifies missing information in weak or incomplete postings.
* Flags explicit phrases that deserve candidate review.
* Emits `match_relevant_signals` for a later scoring layer.

The service does not calculate a candidate-job score in v1.

## Database Design

`JobDescription` stores source-platform metadata, the complete posting text,
salary fields, employment type, workplace arrangement, and optional posting
timestamp. Canonical metadata enums are available to callers, but source fields
remain string-backed so custom integration values can be stored safely.

`JobAnalysis` stores one derived intelligence snapshot per revision. Each record
includes provider name and version, allowing deterministic and future AI
analyses to coexist. `ApplicationHistory` may optionally reference the captured
posting used for an application.

## Rule-Based Limitations

Deterministic extraction is intentionally conservative. It cannot reliably
interpret every narrative job posting, infer implied requirements, resolve
ambiguous technologies, or summarize nuanced organizational context. Keyword
catalogs should expand based on measured product usage.

## Future OpenAI Analyzer

OpenAI is intentionally not called in v1. Local deterministic extraction keeps
development and tests reproducible, avoids an API-key requirement, and gives us
a stable structured contract to evaluate before introducing model variability.

A future OpenAI implementation should subclass `FutureOpenAIJobAnalyzer`, use
structured output matching `JobAnalysisResult`, and retain provider and prompt
version metadata. It should remain injectable through `JobAnalysisService` so
tests and local workflows can continue using deterministic extraction.

## Resume Intelligence Connection

The next matching layer should compare `match_relevant_signals` against the
Candidate Knowledge Base. Resume tailoring can then select candidate-approved
facts that address a posting's required skills, technologies, responsibilities,
and ATS keywords without treating an existing resume as the source of truth.

## Future Extensions

* Add candidate-job match scoring as a separate service.
* Add ATS keyword weighting and evidence-backed gap analysis.
* Add LangGraph workflows that select analyzer providers and request review.
* Add LinkedIn and Indeed adapters that create `JobDescription` records.
* Add PostgreSQL GIN indexes for JSON search after measuring query patterns.

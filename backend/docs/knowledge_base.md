# Candidate Knowledge Base

The Candidate Knowledge Base is the durable source of truth for careerOS. Resume
versions are derived artifacts, not the primary representation of a candidate.
Job analysis, cover letters, ATS optimization, and future agent workflows should
read structured candidate data before generating output.

## Entity Relationships

`CandidateProfile` is the aggregate root. It owns:

* Many `Education` records.
* Many `WorkExperience` records.
* Many `Project` records.
* Many `Skill` records.
* Many `Certification` records.
* One optional `CareerGoal` record.
* One optional `Preference` record.
* Many `ResumeVersion` records.
* Many `ApplicationHistory` records.

An `ApplicationHistory` record may reference the `ResumeVersion` used for that
application. Deleting a candidate cascades to candidate-owned knowledge. Deleting
a resume version preserves application history and clears only that optional
reference.

## Design Decisions

### Relational Source of Truth

Core career facts are first-class relational entities. This allows targeted
updates, filtering, history-aware workflows, and strong integrity constraints.
PostgreSQL-compatible UUID keys make records safe to synchronize across future
services.

### Flexible Structured Fields

Naturally variable lists and maps use JSON columns: technologies, outcomes,
achievements, target roles, industries, geographic preferences, resume content,
and preference maps. PostgreSQL can later add GIN indexes where query patterns
justify them.

### Layered Boundaries

* SQLAlchemy models define persistence and database-level integrity.
* Pydantic schemas validate create, update, and read boundaries.
* Repositories own CRUD, text search, exact filtering, and profile-scoped access.
* `KnowledgeBaseService` owns transactions and cross-entity business rules.

### Resume Versions

A resume version stores a derived content snapshot and the profile update time
used to generate it. This supports reproducibility while ensuring new generation
always begins with the knowledge base.

## Database Integrity

* Every entity uses a UUID primary key and creation/update timestamps.
* Candidate-owned rows use foreign keys with cascading deletion.
* Skills are unique per profile by name.
* Skill rating and experience duration have database checks.
* Career goals enforce one record per profile and a coherent salary range.
* Preferences enforce one record per profile.
* Search and filter paths have profile-aware indexes.

## Future Roadmap

### AI and ATS Intelligence

* Add OpenAI-backed extractors that turn candidate-approved documents into
  proposed knowledge-base updates.
* Add ATS scoring services that compare structured profile facts with job
  requirements.
* Add citation metadata so generated claims trace back to candidate evidence.

### Retrieval and Memory

* Add embedding records keyed to entity UUIDs and update timestamps.
* Add a vector store adapter without changing relational source-of-truth models.
* Add LangGraph workflows that read through repositories and persist only
  candidate-approved changes.

### Operational Growth

* Add Alembic migrations before the first deployed database.
* Add PostgreSQL GIN indexes for JSON search after measuring query patterns.
* Add application events for richer status history and automation auditing.
* Add browser, LinkedIn, and Indeed adapters behind explicit integration
  interfaces.

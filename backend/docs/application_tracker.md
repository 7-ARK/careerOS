# Lightweight Application Tracker

The Lightweight Application Tracker records whether a candidate has applied to
a company role and which generated resume document was selected. It is
intentionally small.

## Purpose

The tracker answers five questions:

* Which company?
* Which role?
* Which generated resume was used?
* Has the candidate applied?
* Is a company email address available?

## What It Tracks

`ApplicationRecord` stores:

* Candidate profile UUID.
* Optional captured job-description and job-analysis UUIDs.
* Optional generated-document UUID.
* Company name and role title.
* Optional company email, job URL, and notes.
* A two-state status: `not_applied` or `applied`.
* The application timestamp when the record is applied.

The optional source links allow a role to be recorded before every downstream
artifact exists. When links are present, the service verifies that they belong
to the selected candidate and job.

## What It Does Not Track

v1 does not implement:

* Interview stages.
* Recruiter contacts.
* Reminders.
* Follow-up workflows.
* Complex pipeline states.
* Browser or platform automation.

The Candidate Knowledge Base still contains the earlier `ApplicationHistory`
entity for compatibility with historical records. New lightweight workflows
should use `ApplicationRecord`, whose database constraint and Pydantic schemas
permit only `not_applied` and `applied`.

## Data Flow

1. A user stores or imports a job description.
2. careerOS may analyze the job and create a tailored resume draft.
3. An approved draft may be exported as a generated document.
4. `ApplicationTrackerService.create_application_record` stores the role.
5. `attach_resume_document` records the generated resume selected for use.
6. `mark_as_applied` sets `applied_at` once.
7. `mark_as_not_applied` clears `applied_at`.

## Relationship With Generated Resumes

`generated_document_id` is optional. When attached, it references the local
document metadata stored by the Document Generation Engine. The tracker does
not copy files, regenerate resumes, or alter candidate facts.

## Future Extensions

The next useful addition is Manual Job Importer v1: accept pasted job URLs and
description text, store a `JobDescription`, run deterministic analysis, and
optionally create a not-applied `ApplicationRecord`.

Future product work may add richer tracking only when measured user needs
justify it. The lightweight tracker should remain a simple default workflow.

# Application Pipeline Orchestrator

The Application Pipeline Orchestrator connects existing careerOS services into
one usable local workflow. It remains deliberately thin: each domain service
continues to own its business rules.

## Purpose

`ApplicationPipelineService.run_manual_job_pipeline` performs:

`Manual Job Import -> Job Analysis -> Resume Analysis -> Resume Draft -> Draft Approval -> Document Generation -> Application Record Update`

The pipeline lets a caller provide pasted job data and receive the generated
resume path, important record UUIDs, match score, truthfulness warnings, and
next actions in one result.

## Data Flow

1. `ManualJobImportService` stores the pasted `JobDescription`, runs
   deterministic job analysis, and optionally creates a `not_applied`
   `ApplicationRecord`.
2. `ResumeIntelligenceService` compares the candidate knowledge base with the
   stored `JobAnalysis`.
3. `ResumeIntelligenceService` creates a structured `ResumeDraft`.
4. The pipeline explicitly marks its newly generated draft as approved through
   the existing draft lifecycle method.
5. `DocumentGenerationService` exports the approved draft as Markdown, DOCX, or
   PDF.
6. If an application record exists, `ApplicationTrackerService` attaches the
   generated document metadata.

## Why This Layer Exists

The underlying services are useful independently, but a product-facing caller
should not need to manually coordinate every UUID. The pipeline owns sequence
and stage-level error reporting only. It does not copy parsing, scoring,
drafting, exporting, or tracking logic.

## Failure Behavior

Each delegated call is wrapped with a `PipelineStage`. Failures raise
`PipelineExecutionError` with the exact failed stage.

Existing domain services commit successful records at their own boundaries.
If document generation fails, captured job data, analysis, and the approved
draft remain available for inspection or retry. A failed generated-document
metadata record is preserved, while partial local files are removed. An
optional `not_applied` application record remains a truthful imported-job
tracker record and is not linked to a failed document.

## What It Does Not Do

v1 does not:

* Scrape LinkedIn, Indeed, Glassdoor, or company pages.
* Launch browser automation.
* Call OpenAI.
* Generate Canva designs.
* Submit applications.
* Build a frontend.

## Example

```python
from app.schemas import ManualJobPipelineRequest
from app.services import ApplicationPipelineService

service = ApplicationPipelineService(session)
result = service.run_manual_job_pipeline(
    ManualJobPipelineRequest(
        candidate_profile_id=profile_id,
        raw_title="Backend Engineer",
        company_name="Platform Labs",
        source_platform="LinkedIn",
        job_url="https://example.com/jobs/backend",
        description_text="Build reliable Python and FastAPI services.",
    )
)
print(result.generated_file_path)
```

## Future Connections

A future Playwright URL extractor should sit upstream of this pipeline. With
explicit user authorization, it can extract visible page content and populate
the same request fields. The pipeline remains the stable downstream workflow.

A frontend can later call this service through an API endpoint and display
match warnings before submission. A Canva adapter can remain an optional
document-generation destination after the local export workflow.

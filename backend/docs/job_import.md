# Manual Job Importer

The Manual Job Importer captures pasted job-posting data, runs deterministic job
analysis, and optionally creates a lightweight not-applied application record.
It is intentionally a thin orchestration layer.

## Purpose

Users can paste a job URL and description text from LinkedIn, Indeed,
Glassdoor, or another source. careerOS preserves that source text before
deriving structured job intelligence.

The importer follows this flow:

`Manual Input -> JobDescription -> JobAnalysis -> optional ApplicationRecord`

## Manual Import Flow

`ManualJobImportService.import_job_posting`:

1. Validates the candidate profile and pasted input.
2. Delegates source capture to `JobAnalysisService.create_job_description`.
3. Delegates deterministic extraction to
   `JobAnalysisService.analyze_job_description`.
4. Optionally delegates not-applied record creation to
   `ApplicationTrackerService.create_application_record`.
5. Returns the stored job description, analysis, and optional application
   record.

Supported source-platform labels include:

* `linkedin`
* `indeed`
* `glassdoor`
* `other`
* `unknown`

## Validation

The importer requires a candidate UUID, raw job title, company name, and
description text. It validates optional HTTP URLs, company email addresses,
currency codes, and salary ranges before persistence.

## Why Scraping Is Deferred

v1 does not fetch pages, scrape HTML, automate browsers, or call external APIs.
Manual paste keeps the workflow deterministic and avoids platform-policy,
authentication, and page-structure complexity while the core product flow is
still taking shape.

## LinkedIn, Indeed, and Glassdoor

The importer stores the selected platform and original job URL. This gives
future platform adapters a stable destination: they can populate the same
`ManualJobImportRequest`-compatible fields without changing job analysis or
application tracking.

## Future Scraper and Browser Automation Plan

Future adapters should sit upstream of the importer:

1. Receive explicit user authorization.
2. Capture source URL and posting text within platform rules.
3. Normalize the extracted fields.
4. Call the same import orchestration boundary.
5. Preserve manual import as a reliable fallback.

## Next Step

Build an end-to-end pipeline service:

`Manual Job Import -> Resume Analysis -> Resume Draft -> Document Generation -> Application Record update`

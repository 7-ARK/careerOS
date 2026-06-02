# Playwright Job URL Extractor

The Playwright Job URL Extractor is a read-only upstream adapter for careerOS.
It accepts one user-authorized job URL, extracts visible posting text, and can
pass sufficiently complete data into the existing application pipeline.

## Purpose

The extractor supports this flow:

`URL -> Playwright extraction -> ManualJobPipelineRequest -> ApplicationPipelineService`

It reduces manual copy and paste while preserving the deterministic careerOS
backend. Manual import remains available as a reliable fallback.

## Architecture

The feature lives in `app/features/job_url_extraction/`:

* `extractors/base.py` defines the provider interface.
* `extractors/playwright.py` implements read-only Chromium extraction and a
  pure visible-text parsing core.
* `JobUrlPipelineService` runs extraction once and delegates pipeline-ready
  results to `ApplicationPipelineService`.
* Pydantic schemas define extraction and URL-pipeline request and result
  contracts.

The parsing core is intentionally separate from browser navigation. Platform
detection, noise cleanup, safety-wall detection, generic inference, and
pipeline-ready gating can be tested without launching Chromium.

## Setup

Install Python dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install Playwright Chromium once:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Supported Sources

Domain detection recognizes:

* `linkedin.com`
* `indeed.com`
* `glassdoor.com`
* Company career pages and unknown generic job pages

The extractor tries common platform-specific selectors first. If they are not
available, it falls back to visible page text and page-title inference.

## Safety Rules

v1 is user-authorized single-URL extraction only. It must not:

* Click Apply buttons.
* Submit forms.
* Bypass login walls.
* Bypass CAPTCHA, paywalls, or anti-bot systems.
* Scrape at scale.
* Attempt authentication.

When a page appears blocked or gated, extraction stops with warnings and
`pipeline_ready=False`. The caller should offer manual import fallback.

## Known Limitations

* Dynamic sites may hide useful text until user interaction.
* Some pages expose ambiguous titles, companies, or locations.
* Login-gated LinkedIn, Indeed, or Glassdoor pages cannot be bypassed.
* v1 does not infer salary ranges from free-form text.
* Generic pages with weak visible content may require manual import.

## Optional Browser Test

Default test runs skip Chromium:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

After installing Chromium, run the opt-in local HTML browser test:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m browser --run-browser
```

The browser test uses a local `data:` HTML page. It does not contact LinkedIn,
Indeed, Glassdoor, or any external website.

## Pipeline Connection

```python
from app.schemas import JobUrlPipelineRequest
from app.services import JobUrlPipelineService

service = JobUrlPipelineService(session)
result = service.run_url_pipeline(
    JobUrlPipelineRequest(
        candidate_profile_id=profile_id,
        job_url="https://careers.example.com/jobs/backend-engineer",
    )
)

if not result.extraction.pipeline_ready:
    print(result.extraction.extraction_warnings)
else:
    print(result.pipeline.generated_file_path)
```

## Future Plan

The next backend step is FastAPI endpoints for:

* Manual job pipeline execution.
* URL job pipeline execution.
* Generated-document download.

A future frontend can display extraction warnings and route gated pages to
manual import without changing the downstream pipeline.

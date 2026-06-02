# FastAPI Endpoints

careerOS exposes its existing backend workflows through thin FastAPI routes.
The API layer validates requests, delegates to application services, and
returns structured responses suitable for a future frontend.

## Run Locally

Add a PostgreSQL-compatible database URL to the ignored local `backend/.env` file:

```dotenv
DATABASE_URL=postgresql+psycopg://user:password@localhost/careeros
```

Start the development server:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Equivalent command when the virtual environment is active:

```powershell
uvicorn app.main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

### Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "service": "careerOS",
  "version": "0.1.0"
}
```

### Manual Pipeline

```http
POST /api/v1/pipeline/manual
```

Request:

```json
{
  "candidate_profile_id": "00000000-0000-0000-0000-000000000000",
  "raw_title": "Backend Engineer",
  "company_name": "Platform Labs",
  "source_platform": "linkedin",
  "job_url": "https://example.com/jobs/backend",
  "description_text": "Build reliable Python and FastAPI services."
}
```

This delegates to `ApplicationPipelineService.run_manual_job_pipeline`.

### URL Pipeline

```http
POST /api/v1/pipeline/url
```

Request:

```json
{
  "candidate_profile_id": "00000000-0000-0000-0000-000000000000",
  "job_url": "https://careers.example.com/jobs/backend"
}
```

This delegates to `JobUrlPipelineService.run_url_pipeline`. If visible page
content is gated or incomplete, the response includes extraction warnings and
does not run the downstream pipeline.

### Download Generated Document

```http
GET /api/v1/documents/{document_id}/download
```

Returns the generated local file with its recorded filename. Missing metadata
or a missing local file returns HTTP `404`.

### Application Records

```http
GET /api/v1/applications/{candidate_profile_id}
PATCH /api/v1/applications/{application_id}/applied
PATCH /api/v1/applications/{application_id}/not-applied
```

These delegate to the lightweight two-state application tracker.

## Error Format

Validation, missing records, missing document files, and pipeline execution
errors return a consistent envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": []
  }
}
```

## Frontend Integration

A future frontend can:

1. Submit pasted job descriptions to the manual pipeline endpoint.
2. Submit authorized URLs to the URL pipeline endpoint.
3. Display extraction and resume truthfulness warnings.
4. Download the generated resume.
5. Display and update lightweight application status.

Authentication, file uploads, Canva, and auto-apply remain intentionally out of
scope for v1.

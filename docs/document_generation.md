# Document Generation Engine

The Document Generation Engine converts an approved structured `ResumeDraft`
into professional local resume files. It is a downstream presentation layer:
the Candidate Knowledge Base remains the source of truth.

## Purpose

careerOS now supports the complete deterministic flow:

`Candidate Knowledge Base -> Job Analysis -> Resume Analysis -> ResumeDraft -> Generated Document`

Generated documents are immutable local artifacts. They can be regenerated from
an approved draft without changing candidate facts or resume-intelligence
results.

## Architecture

The feature lives in `app/features/document_generation/`:

* `templates/` converts a structured draft and candidate identity into a neutral
  single-column resume representation.
* `renderers/` converts that representation into portable text where needed.
* `exporters/` writes Markdown, DOCX, and PDF files.
* `service.py` validates approval, selects templates and exporters, writes local
  files, calculates checksums, and persists metadata.
* `GeneratedDocumentRepository` owns metadata retrieval and scoped listing.
* `GeneratedDocument` stores one immutable generation attempt.

Internal omitted keywords and truthfulness notes remain review metadata. They
are deliberately excluded from published files.

## Supported Formats

### Markdown

`MarkdownExporter` writes UTF-8 Markdown. It is useful for inspection, source
control outside the generated directory, and future integrations.

### DOCX

`DocxExporter` uses `python-docx` to create editable, single-column resumes with
standard headings and bullet lists. It avoids table-heavy layouts for ATS
compatibility.

### PDF

`PdfExporter` uses ReportLab. This keeps Windows installation reliable because
it does not require the native libraries commonly needed by HTML-to-PDF
toolchains. The generated PDF contains selectable text.

## Templates

### `clean_ats`

Minimal ATS-first format with restrained styling and conventional section
ordering.

### `modern_professional`

A polished but still ATS-safe format with a muted accent and experience-first
ordering. It is appropriate for LinkedIn, AI, and automation roles without
introducing multi-column parsing risks.

## Local Storage

Files are written to `generated/resumes/` by default. The `generated/`
directory is ignored by Git. Callers may provide another output directory for
testing or future storage adapters.

Each `GeneratedDocument` stores:

* Resume draft, candidate, and job-analysis UUID references.
* Template and output format.
* File name, absolute local path, and byte size.
* SHA-256 checksum.
* Pending, completed, or failed generation status.
* Error details for failed attempts.

## Why Canva Is Deferred

Canva is intentionally not part of v1. Local generation provides deterministic
outputs, offline tests, and a stable document contract before adding an
external presentation adapter. Canva must remain an optional downstream
integration, never the source of candidate data.

## Future Canva Adapter

A future Canva adapter should consume the same approved `ResumeDraft`, map its
sections into a Canva template, and persist an external artifact reference
alongside generation metadata. It should not bypass approval checks or add
unsupported claims.

## Future Secure Storage

Local paths are suitable for development only. Production should add a storage
interface with encrypted object storage, short-lived signed download URLs,
tenant-aware access control, retention policies, and audit events. The
`GeneratedDocument` record can remain the metadata boundary.

## Limitations

* v1 does not perform page-count optimization.
* v1 does not generate Canva designs.
* v1 does not use OpenAI for rewriting.
* v1 exports approved structured content without editing candidate facts.
* Local filesystem storage is not intended for multi-instance production use.

## Usage

```python
from app.features.document_generation import DocumentGenerationService

service = DocumentGenerationService(session)
result = service.generate_docx(approved_resume_draft_id)
print(result.document.file_path)
```

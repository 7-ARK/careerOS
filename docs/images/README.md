# Portfolio Media Guide

This directory is reserved for recruiter-facing media captured from the production frontend build.
Do not add blank placeholders or broken image links.

## Required captures

| File | Required content |
| --- | --- |
| `career-analysis-overview.png` | Job context, pipeline status, and canonical 64.29% coverage |
| `requirement-evidence-map.png` | A citation-backed match and a truthful not-evidenced requirement |
| `grounded-resume-preview.png` | Grounded draft plus explicit review/export state |
| `application-tracker.png` | Synthetic saved application with evidence coverage and read-only status |

## Capture rules

- Use the fictional Amina Rahman demo profile and disposable preview database only.
- Build with `npm run build` and serve with `npm run preview`; do not capture Vite development UI.
- Use a clean 16:9 browser viewport without bookmarks, unrelated tabs, or local filesystem paths.
- Exclude `.env` values, tokens, private candidate records, real contact data, and temporary tunnel
  URLs.
- Inspect every image at full size before adding its README link.

The four PNG captures were produced from the deterministic production preview and visually checked
at 1440x810. The final product walkthrough is linked from the root README; no raw video is stored in
this repository.

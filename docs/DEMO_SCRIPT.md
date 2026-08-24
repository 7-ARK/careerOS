# Recruiter Demo Script

## 90-120 seconds

**0:00-0:12 - Product and profile**

Open `http://localhost:3000`, sign in with the seeded local demo account, and show the structured candidate profile. Say: "careerOS treats these candidate-owned records as the only verified evidence source. Generated suggestions never become evidence automatically."

**0:12-0:28 - Manual job input**

Select the candidate and paste an Applied AI Engineer description containing Python, FastAPI, PostgreSQL, RAG, Docker, and AWS. Point out deterministic demo mode and start **Analyze evidence**.

**0:28-0:48 - Inspect the bounded run**

Show the stage timeline, provider `deterministic_local`, zero estimated cost, and the Evidence Coverage Score. Explain the required/preferred weighting and that the value is calculated in Python.

**0:48-1:05 - Evidence and gaps**

Expand one matched FastAPI requirement to show the stable project evidence ID, verified source, text, and retrieval score. Expand AWS to show `Not evidenced` and the truthful project/learning recommendation instead of a fabricated claim.

**1:05-1:20 - Grounded resume and approval**

Scroll through the resume preview and grounding citation counts. Explain that the backend validates claim groups before this screen and validates again at approval. Approve the draft; mention that no document existed before that click.

**1:20-1:34 - Export and tracking**

Download the PDF, switch to **Applications**, and update the saved record from Saved to Applied. Point out the stored Evidence Coverage Score.

**1:34-1:50 - Engineering proof**

Show `/docs`, the GitHub Actions workflow, and the terminal results for pytest, Ruff, TypeScript/build, Playwright, and the three deterministic evaluation fixtures. Close with: "The project is intentionally bounded: no automatic applications, no bulk scraping, and no unsupported resume claims."

## Screenshot checklist

Capture the production frontend build at a 16:9 desktop viewport with only the fictional Amina
Rahman fixture. Use the filenames documented in `docs/images/README.md`:

1. `career-analysis-overview.png` - pipeline stages, canonical 64.29% score, and job context.
2. `requirement-evidence-map.png` - one citation-backed match and one not-evidenced requirement.
3. `grounded-resume-preview.png` - grounded resume preview and approval/export state.
4. `application-tracker.png` - the synthetic saved application and read-only status.

Optional supporting captures may show the candidate profile, Swagger career-analysis endpoints,
or clean verification output. Do not capture a Vite development server, browser bookmarks,
temporary tunnel URL, `.env`, tokens, local paths, real contact data, private resumes, or database
contents.

The 90-120 second recording should follow the same sequence and use `careeros-demo.gif` only when
the final file remains readable at GitHub width. Otherwise host an MP4 and link it from the README.

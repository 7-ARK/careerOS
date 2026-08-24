# Deterministic Evaluation

## Purpose

The evaluation suite checks behavior that matters for an evidence-grounded recruiter demo without calling a paid provider. Fixtures live in `backend/evals/fixtures/` for:

- Applied AI Engineer
- Junior Machine Learning Engineer
- Python/AI Backend Internship

Each fixture defines a job description, verified candidate evidence, expected extracted terms, expected top retrieval IDs, genuine missing requirements, and unsupported claims that must not appear as evidence.

## Executable checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\evals -q
```

The tests execute the real `RuleBasedJobAnalyzer`, deterministic embedding provider, and `LocalVectorStore`. Golden-flow integration tests separately execute persistence, matching, grounding, approval, DOCX/PDF export, and application tracking.

## Metrics and definitions

- **Structured-output validity:** fixture analyses that pass the typed `JobAnalysisResult` contract.
- **Expected retrieval:** fixture queries whose top result is the specified stable evidence ID.
- **Evidence citation coverage:** percentage of generated claim groups carrying known evidence IDs.
- **Unsupported-claim acceptance:** tampered unsupported claim groups that incorrectly pass approval.
- **Golden-flow completion:** integration flows that reach reviewed export and tracking.

The checked-in expectations are deliberately small and deterministic. Final measured counts are reported from the verification run; they are not benchmark claims and should not be compared with production embedding systems.

## Measured local result

Measured with deterministic providers and no API credentials:

| Check | Result |
| --- | ---: |
| Typed fixture analyses valid | 3 / 3 |
| Expected top evidence retrievals | 6 / 6 |
| Fixture unsupported statements present in verified evidence | 0 / 3 |
| Golden-flow API completed after approval | 1 / 1 |
| Grounding citation coverage in the golden fixture | 100% |
| Tampered unsupported approvals accepted | 0 / 1 |

The canonical Applied AI Engineer demonstration fixture extracts 16 scored requirements: 6 fully
supported, 6 partially supported, and 4 not evidenced. Its code-calculated coverage is 64.29%.
Explicit negative controls keep AWS, Kubernetes, and CI/CD requirements from matching unrelated
Docker or generic backend evidence, while date-aware experience checks return partial support when
the verified timeline falls outside the requested range.

These are small regression-fixture counts, not statistical model-quality claims. The verified full
backend run containing these checks passed `228` tests with one optional browser-extraction test
skipped; the separate frontend browser suite passed `7` journeys.

## Failure policy

Malformed provider output is validated and falls back to deterministic resume quality. Missing credentials select local retrieval. Unknown evidence IDs or uncited claims block approval and create no document. A failed fixture is a failing test, not a silently adjusted expected result.

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

The checked-in fixture expectations above are deliberately small and deterministic. Those fixture counts are regression checks, not the retrieval benchmark. The frozen 24-case comparison of lexical, feature-hash hybrid, and OpenAI semantic hybrid ranking is summarized in the root [Evidence RAG / retrieval](../README.md#evidence-rag--retrieval) section. Case-level tables are in `backend/evals/results/retrieval_report.md`. After that measurement, status-gate diagnosis left the product match rules unchanged. See `backend/evals/results/status_gate_diagnosis.md`.

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

## Curated retrieval benchmark

From `backend/`:

```powershell
python -m scripts.retrieval_eval
```

Lexical and feature-hash arms always run. The OpenAI arm runs only when `OPENAI_API_KEY` is set and does not print the key. Results are written to `evals/results/results.json` and `evals/results/retrieval_report.md`. `python -m scripts.status_gate_diagnosis` rewrites the diagnosis report from that JSON and does not call OpenAI. Neither command changes product ranking or match rules.

On the recorded run, semantic retrieval improved paraphrase ranking. Paraphrase Recall@1 moved from 0/6 lexical to 5/6 with OpenAI `text-embedding-3-small`, and from 1/6 with feature-hash hybrid. Overall Recall@1 on the 14 graded cases moved from 8/14 lexical to 9/14 feature-hash to 13/14 OpenAI. MRR on those 14 cases was 0.7679, 0.7881, and 0.9643. Overall status accuracy stayed 19/24 in every mode. Unsupported false positives stayed 0/5 and near-miss false positives stayed 0/5. The OpenAI arm made 25 embedding requests, reported 961 prompt tokens, and estimated a list-price cost of 0.00001922 USD. That cost is not an invoice. The product status gate was left unchanged.

## Failure policy

Malformed provider output is validated and falls back to deterministic resume quality. `RAG_EMBEDDING_PROVIDER=deterministic` and preview mode use local retrieval. `RAG_EMBEDDING_PROVIDER=openai` without `OPENAI_API_KEY` fails instead of silently selecting local embeddings. Unknown evidence IDs or uncited claims block approval and create no document. A failed fixture is a failing test, not a silently adjusted expected result.

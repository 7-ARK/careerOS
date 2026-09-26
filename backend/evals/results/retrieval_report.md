# CareerOS retrieval evaluation

Evaluation only. This run leaves hybrid weights, chunking, reranking, and product match rules as they are.

## Corpus

The corpus is the Amina Rahman demo profile from `scripts/seed_candidate.py`, turned into chunks by `CandidateEvidenceRetriever.collect`. It contains 26 chunks. Google Cloud, AWS, Kubernetes, and CI/CD are absent from this profile. Those tools are not treated as demonstrated experience.

## Benchmark

24 frozen cases: 8 exact, 6 paraphrase, 5 near-miss, 5 unsupported. Ground truth was written from the chunk text before the three modes were scored.

| Case | Category | Query | Relevant evidence | Expected status |
| --- | --- | --- | --- | --- |
| exact-postman | exact | Postman API Fundamentals Student Expert | certification:Postman | matched |
| exact-civic-tech | exact | Civic Tech Lab | experience:Civic Tech Lab | matched |
| exact-northstar | exact | Northstar Digital Studio | experience:Northstar Digital Studio | matched |
| exact-legal-title | exact | Legal Document OCR and Extraction System | project:Legal Document OCR and Extraction System | matched |
| exact-job-tool-title | exact | Web Scraping and Job Data Extraction Tool | project:Web Scraping and Job Data Extraction Tool | matched |
| exact-rag-outcome | exact | Used RAG patterns to ground generated responses in retrieved context. | project:AI Workflow Automation System | matched |
| exact-education | exact | Bachelor of Science Computer Science at Metro Institute of Technology | education:Metro Institute of Technology | matched |
| exact-zapier | exact | Zapier | skill:Zapier, project:AI Workflow Automation System, experience:Northstar Digital Studio | matched |
| para-ocr | paraphrase | optical character recognition | project:Legal Document OCR and Extraction System, experience:Civic Tech Lab | matched |
| para-sql-expansion | paraphrase | structured query language | skill:SQL, project:AI Resume Automation / careerOS, project:Legal Document OCR and Extraction System, experience:Civic Tech Lab | matched |
| para-containers | paraphrase | operating-system level containers | skill:Docker, project:AI Resume Automation / careerOS, project:Legal Document OCR and Extraction System, project:Web Scraping and Job Data Extraction Tool, experience:Northstar Digital Studio | matched |
| para-python-web-framework | paraphrase | Python web API framework | profile, skill:FastAPI, project:AI Resume Automation / careerOS, project:Legal Document OCR and Extraction System, experience:Northstar Digital Studio | matched |
| para-human-approval | paraphrase | human approval of machine-generated text | project:AI Workflow Automation System | matched |
| para-relational-databases | paraphrase | relational databases | skill:SQL, skill:PostgreSQL, project:AI Resume Automation / careerOS, project:Legal Document OCR and Extraction System, experience:Northstar Digital Studio, experience:Civic Tech Lab | matched |
| near-kubernetes | near-miss | Kubernetes | — | not_evidenced |
| near-cicd | near-miss | CI/CD | — | not_evidenced |
| near-django | near-miss | Django | — | not_evidenced |
| near-spring | near-miss | Java Spring Boot | — | not_evidenced |
| near-attorney | near-miss | licensed attorney | — | not_evidenced |
| unsup-aws | unsupported | Amazon Web Services | — | not_evidenced |
| unsup-terraform | unsupported | Terraform | — | not_evidenced |
| unsup-salesforce | unsupported | Salesforce | — | not_evidenced |
| unsup-swiftui | unsupported | SwiftUI | — | not_evidenced |
| unsup-rust | unsupported | Rust | — | not_evidenced |

## Metric definitions

- **Recall@k** is 1 when at least one relevant chunk is in the first k ranks of the full corpus ranking. The reported value is that count over the cases that have relevant evidence.
- **MRR** is the mean of 1/rank for those same graded cases. A graded miss contributes 0.
- Near-miss and unsupported cases have no relevant chunk. Recall and MRR are omitted for them.
- **Status** uses `EvidenceMatchService._match_requirement` on the mode's top 3. Labels are `matched`, `partially_matched`, `not_evidenced`, and `not_applicable`. Requirement kind is `technology`, so the experience-year path stays unused.
- Lexical-only sorts by the lexical score `rank_evidence` already computed, then sets `vector_score` to 0 before the status call.
- Feature-hash hybrid and OpenAI semantic hybrid keep the `rank_evidence` order and scores. That function is lexical 0.7 / vector 0.3.
- AWS, Kubernetes, and CI/CD queries hit the product's explicit phrase rules. Those status labels follow the phrase rule.
- An **unsupported false positive** is an unsupported case predicted `matched` or `partially_matched`. Near-miss false positives use the same rule.
- **neighbor_ranked_first** means the top chunk is a labeled distractor with a positive lexical score, or a hybrid vector score of at least 0.45. An all-zero tie is left uncounted.

## Results

### Lexical only

Provider `deterministic_local`, model `feature-hash-v1`.
Ranking: lexical_score desc, evidence_id asc.

| Slice | Recall@1 | Recall@3 | MRR | Status accuracy | Unsupported FP | Near-miss FP | Neighbor at rank 1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 8/14 | 13/14 | 0.7679 (n=14) | 19/24 | 0/5 | 0/5 | 5/10 |
| exact | 8/8 | 8/8 | 1.0000 (n=8) | 8/8 | n/a | n/a | n/a |
| paraphrase | 0/6 | 5/6 | 0.4583 (n=6) | 1/6 | n/a | n/a | 5/5 |
| near-miss | n/a | n/a | n/a | 5/5 | n/a | 0/5 | 0/5 |
| unsupported | n/a | n/a | n/a | 5/5 | 0/5 | n/a | n/a |

| Case | Category | Top 1 | Relevant rank | Status | FP | Neighbor |
| --- | --- | --- | --- | --- | --- | --- |
| exact-postman | exact | certification:Postman | 1 | matched (correct) | no | no |
| exact-civic-tech | exact | experience:Civic Tech Lab | 1 | matched (correct) | no | no |
| exact-northstar | exact | experience:Northstar Digital Studio | 1 | matched (correct) | no | no |
| exact-legal-title | exact | project:Legal Document OCR and Extraction System | 1 | matched (correct) | no | no |
| exact-job-tool-title | exact | project:Web Scraping and Job Data Extraction Tool | 1 | matched (correct) | no | no |
| exact-rag-outcome | exact | project:AI Workflow Automation System | 1 | matched (correct) | no | no |
| exact-education | exact | education:Metro Institute of Technology | 1 | matched (correct) | no | no |
| exact-zapier | exact | experience:Northstar Digital Studio | 1 | matched (correct) | no | no |
| para-ocr | paraphrase | certification:Postman | 4 | not_evidenced (incorrect) | no | no |
| para-sql-expansion | paraphrase | experience:Northstar Digital Studio | 2 | partially_matched (incorrect) | no | yes |
| para-containers | paraphrase | project:AI Workflow Automation System | 2 | partially_matched (incorrect) | no | yes |
| para-python-web-framework | paraphrase | project:Web Scraping and Job Data Extraction Tool | 2 | matched (correct) | no | yes |
| para-human-approval | paraphrase | education:Metro Institute of Technology | 2 | partially_matched (incorrect) | no | yes |
| para-relational-databases | paraphrase | education:Metro Institute of Technology | 2 | partially_matched (incorrect) | no | yes |
| near-kubernetes | near-miss | certification:Postman | n/a | not_evidenced (correct) | no | no |
| near-cicd | near-miss | certification:Postman | n/a | not_evidenced (correct) | no | no |
| near-django | near-miss | certification:Postman | n/a | not_evidenced (correct) | no | no |
| near-spring | near-miss | certification:Postman | n/a | not_evidenced (correct) | no | no |
| near-attorney | near-miss | certification:Postman | n/a | not_evidenced (correct) | no | no |
| unsup-aws | unsupported | education:Metro Institute of Technology | n/a | not_evidenced (correct) | no | no |
| unsup-terraform | unsupported | certification:Postman | n/a | not_evidenced (correct) | no | no |
| unsup-salesforce | unsupported | certification:Postman | n/a | not_evidenced (correct) | no | no |
| unsup-swiftui | unsupported | certification:Postman | n/a | not_evidenced (correct) | no | no |
| unsup-rust | unsupported | certification:Postman | n/a | not_evidenced (correct) | no | no |

Unsupported false positives: none.
Near-miss false positives: none.
Labeled neighbor at rank 1: para-sql-expansion, para-containers, para-python-web-framework, para-human-approval, para-relational-databases.

### Feature-hash hybrid

Provider `deterministic_local`, model `feature-hash-v1`.
Ranking: rank_evidence order (lexical 0.7 / vector 0.3).

| Slice | Recall@1 | Recall@3 | MRR | Status accuracy | Unsupported FP | Near-miss FP | Neighbor at rank 1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 9/14 | 13/14 | 0.7881 (n=14) | 19/24 | 0/5 | 0/5 | 4/10 |
| exact | 8/8 | 8/8 | 1.0000 (n=8) | 8/8 | n/a | n/a | n/a |
| paraphrase | 1/6 | 5/6 | 0.5056 (n=6) | 1/6 | n/a | n/a | 4/5 |
| near-miss | n/a | n/a | n/a | 5/5 | n/a | 0/5 | 0/5 |
| unsupported | n/a | n/a | n/a | 5/5 | 0/5 | n/a | n/a |

| Case | Category | Top 1 | Relevant rank | Status | FP | Neighbor |
| --- | --- | --- | --- | --- | --- | --- |
| exact-postman | exact | certification:Postman | 1 | matched (correct) | no | no |
| exact-civic-tech | exact | experience:Civic Tech Lab | 1 | matched (correct) | no | no |
| exact-northstar | exact | experience:Northstar Digital Studio | 1 | matched (correct) | no | no |
| exact-legal-title | exact | project:Legal Document OCR and Extraction System | 1 | matched (correct) | no | no |
| exact-job-tool-title | exact | project:Web Scraping and Job Data Extraction Tool | 1 | matched (correct) | no | no |
| exact-rag-outcome | exact | project:AI Workflow Automation System | 1 | matched (correct) | no | no |
| exact-education | exact | education:Metro Institute of Technology | 1 | matched (correct) | no | no |
| exact-zapier | exact | skill:Zapier | 1 | matched (correct) | no | no |
| para-ocr | paraphrase | profile | 5 | not_evidenced (incorrect) | no | no |
| para-sql-expansion | paraphrase | project:Legal Document OCR and Extraction System | 1 | partially_matched (incorrect) | no | no |
| para-containers | paraphrase | project:AI Workflow Automation System | 2 | partially_matched (incorrect) | no | yes |
| para-python-web-framework | paraphrase | project:Web Scraping and Job Data Extraction Tool | 3 | matched (correct) | no | yes |
| para-human-approval | paraphrase | education:Metro Institute of Technology | 2 | partially_matched (incorrect) | no | yes |
| para-relational-databases | paraphrase | education:Metro Institute of Technology | 2 | partially_matched (incorrect) | no | yes |
| near-kubernetes | near-miss | project:Legal Document OCR and Extraction System | n/a | not_evidenced (correct) | no | no |
| near-cicd | near-miss | project:Web Scraping and Job Data Extraction Tool | n/a | not_evidenced (correct) | no | no |
| near-django | near-miss | certification:Postman | n/a | not_evidenced (correct) | no | no |
| near-spring | near-miss | project:Legal Document OCR and Extraction System | n/a | not_evidenced (correct) | no | no |
| near-attorney | near-miss | skill:Playwright | n/a | not_evidenced (correct) | no | no |
| unsup-aws | unsupported | profile | n/a | not_evidenced (correct) | no | no |
| unsup-terraform | unsupported | experience:Northstar Digital Studio | n/a | not_evidenced (correct) | no | no |
| unsup-salesforce | unsupported | education:Metro Institute of Technology | n/a | not_evidenced (correct) | no | no |
| unsup-swiftui | unsupported | experience:Civic Tech Lab | n/a | not_evidenced (correct) | no | no |
| unsup-rust | unsupported | certification:Postman | n/a | not_evidenced (correct) | no | no |

Unsupported false positives: none.
Near-miss false positives: none.
Labeled neighbor at rank 1: para-containers, para-python-web-framework, para-human-approval, para-relational-databases.

### OpenAI semantic hybrid

OPENAI_API_KEY is not set, so the semantic arm was not run. No OpenAI score was invented. Re-run `python -m scripts.retrieval_eval` from backend/ with OPENAI_API_KEY set. The default model is text-embedding-3-small. RAG_EMBEDDING_MODEL overrides it. Leave RAG_EMBEDDING_DIMENSIONS unset unless you intend to request a shortened vector.

## Cases helped or hurt

### Feature-hash hybrid compared with lexical only

Helped: para-sql-expansion.
Hurt: para-ocr, para-python-web-framework.

| Case | Category | Retrieval | Status | Neighbor | Detail |
| --- | --- | --- | --- | --- | --- |
| para-ocr | paraphrase | hurt | unchanged | unchanged | relevant rank 4 -> 5; status not_evidenced -> not_evidenced; neighbor_ranked_first False -> False |
| para-sql-expansion | paraphrase | helped | unchanged | helped | relevant rank 2 -> 1; status partially_matched -> partially_matched; neighbor_ranked_first True -> False |
| para-python-web-framework | paraphrase | hurt | unchanged | unchanged | relevant rank 2 -> 3; status matched -> matched; neighbor_ranked_first True -> True |

OpenAI comparisons are omitted because the semantic arm did not run.

## Recommendation

Choice: **investigate**.

Investigate the lexical status gate. Leave the 0.7 / 0.3 weights in place. Exact Recall@1 is 8/8 lexical and 8/8 feature-hash, with status 8/8 and 8/8. Unsupported false positives are 0/5 lexical and 0/5 feature-hash. Near-miss false positives are 0/5 lexical and 0/5 feature-hash. On the lexical arm, `unsup-aws` tops out at lexical 0.3333 on education:Metro Institute of Technology and stays `not_evidenced` under the explicit AWS phrase rule. Paraphrase Recall@1 is 0/6 lexical and 1/6 feature-hash. Paraphrase Recall@3 is 5/6 lexical and 5/6 feature-hash. `para-ocr` is outside the top 3 at rank 4 lexical and rank 5 feature-hash, with status `not_evidenced` and a top-hit lexical score of 0.0000. Paraphrase status accuracy is 1/6 lexical and 1/6 feature-hash. Paraphrase cases with a correct feature-hash status: `para-python-web-framework`. `para-python-web-framework` has feature-hash top hit project:Web Scraping and Job Data Extraction Tool at lexical 0.7500, a labeled distractor. Feature-hash versus lexical helped: para-sql-expansion. Hurt: para-ocr, para-python-web-framework. Status labels on those changed cases stayed the same. Overall Recall@1 is 8/14 lexical and 9/14 feature-hash. The OpenAI arm did not run. This file contains no semantic score. Re-run with OPENAI_API_KEY on this same fixture before treating live embeddings as measured. The measured rank movement is too small to justify a weight change, and a zero-lexical chunk stays below the product's 0.65 lexical bar for `matched`.

This recommendation is not implemented.

## How to reproduce

```text
cd backend
python -m scripts.retrieval_eval
```

The command writes `evals/results/results.json` and `evals/results/retrieval_report.md`. With `OPENAI_API_KEY` set, it also runs the semantic arm and caches vectors under `evals/cache/`. That cache is local reuse and is gitignored. `RAG_EMBEDDING_MODEL` defaults to `text-embedding-3-small`. The command does not print the key.

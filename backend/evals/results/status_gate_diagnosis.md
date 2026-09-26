# Phase 4 status-gate diagnosis

Diagnosis only. Product matching, hybrid weights, chunking, and models stay as they are. Scores are the recorded OpenAI semantic hybrid hits in `evals/results/results.json` (`openai` / `text-embedding-3-small`, rank_evidence order (lexical 0.7 / vector 0.3)). This command does not embed new text.

## Where status is decided

The retrieval eval calls `EvidenceMatchService._match_requirement` with requirement kind `technology` and `top_k=3`. That path reaches `_evaluate_text` in `backend/app/features/resume_intelligence/matching.py`.

Decision order:

1. **Explicit phrase rules** run first. `EXPLICIT_EVIDENCE_RULES` (line 80) covers AWS (`aws`, `amazon web services`, `amazon ec2`, `amazon s3`, `aws lambda`), Kubernetes (`kubernetes`, `k8s`), and CI/CD (`ci cd`, `continuous integration`, `continuous delivery`, `continuous deployment`). `_evaluate_explicit_evidence` (line 551) scans the whole corpus for those aliases. Hybrid scores are not read. Status is `matched` only when every triggered rule has a chunk that contains the name or an accepted alias, `partially_matched` when only some of the triggered rules hit, and `not_evidenced` when none hit.
2. **Citation filter** on the top 3: keep a chunk when `lexical_score > 0` or `vector_score >= 0.45` (line 541).
3. **Matched** when a citation exists and either the normalized query is an exact substring of a citation or `best_lexical >= 0.65` (line 545).
4. **Partially matched** when a citation exists and `best_lexical >= 0.25` (line 547).
5. **Not evidenced** when the citation list is empty or the best admitted lexical score is below 0.25.

The 0.65 figure is the single `Decimal("0.65")` comparison in the matcher, on line 545. It is `best_lexical` among admitted citations. The explicit-rule path returns before that line. An empty citation list returns `not_evidenced` before that line is evaluated.

Lexical score is `|query tokens ∩ evidence tokens| / |query tokens|` after `normalize_text`. `retrieval_score` is the ranking combination `min(1, 0.7 * lexical + 0.3 * vector)`. `_evaluate_text` does not read `retrieval_score`. Stop-words are removed only by `_signal_tokens`, which decides `not_applicable`. They still count in the lexical score.

## Paraphrase cases

Expected status is `matched`. Scores below are the rank-1 chunk. Correct rank is the best relevant chunk in the full recorded ordering.

| Case | Top-1 evidence | Lexical | Vector | Combined | Correct rank | Status | Rule |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| para-ocr | project:Legal Document OCR and Extraction System | 0.0000 | 0.3141 | 0.0942 | 1 | not_evidenced (expected matched) | citation_filter_empty |
| para-sql-expansion | experience:Civic Tech Lab | 0.3333 | 0.2078 | 0.2957 | 1 | partially_matched (expected matched) | lexical_partial_below_matched_bar |
| para-containers | project:Legal Document OCR and Extraction System | 0.2500 | 0.2318 | 0.2445 | 1 | partially_matched (expected matched) | lexical_partial_below_matched_bar |
| para-python-web-framework | project:Web Scraping and Job Data Extraction Tool | 0.7500 | 0.3939 | 0.6432 | 2 | matched (expected matched) | lexical_matched_bar |
| para-human-approval | project:AI Workflow Automation System | 0.3333 | 0.4406 | 0.3655 | 1 | partially_matched (expected matched) | lexical_partial_below_matched_bar |
| para-relational-databases | skill:SQL | 0.5000 | 0.3413 | 0.4524 | 1 | partially_matched (expected matched) | lexical_partial_below_matched_bar |

### para-ocr

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 project:Legal Document OCR and Extraction System has lexical 0.0000 and vector 0.3141. The highest top-3 vector is 0.3141. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. Relevant evidence the citation filter excluded: `project:Legal Document OCR and Extraction System` is rank 1 with lexical 0.0000 and vector 0.3141; `experience:Civic Tech Lab` is rank 3 with lexical 0.0000 and vector 0.2229. Vector is below 0.45 and lexical is 0, so those chunks do not enter the 0.65 comparison. This rule blocked the expected status.

### para-sql-expansion

Admitted citations have best lexical 0.3333 (experience:Civic Tech Lab overlap ['structured']; project:Legal Document OCR and Extraction System overlap ['structured']; project:AI Resume Automation / careerOS overlap ['structured']). That is below the 0.65 matched bar and at least the 0.25 partial bar, so status is partially_matched. The normalized query is not an exact substring of an admitted citation. Labeled relevant evidence outside the recorded top 5: `skill:SQL`. This rule blocked the expected status.

### para-containers

Admitted citations have best lexical 0.2500 (project:Legal Document OCR and Extraction System overlap ['system']; project:AI Workflow Automation System overlap ['system']). That is below the 0.65 matched bar and at least the 0.25 partial bar, so status is partially_matched. The normalized query is not an exact substring of an admitted citation. Relevant evidence the citation filter excluded: `skill:Docker` is rank 3 with lexical 0.0000 and vector 0.4279. Vector is below 0.45 and lexical is 0, so those chunks do not enter the 0.65 comparison. Labeled relevant evidence outside the recorded top 5: `project:Web Scraping and Job Data Extraction Tool`. This rule blocked the expected status.

### para-python-web-framework

best lexical 0.7500 on project:Web Scraping and Job Data Extraction Tool (overlap ['api', 'python', 'web']) meets the 0.65 matched bar. First relevant chunk is rank 2 profile (lexical 0.5000, vector 0.3870, combined 0.4661). Labeled relevant evidence outside the recorded top 5: `skill:FastAPI`, `project:Legal Document OCR and Extraction System`. This rule produced the expected status.

### para-human-approval

Admitted citations have best lexical 0.3333 (project:AI Workflow Automation System overlap ['generated', 'human']; education:Metro Institute of Technology overlap ['machine', 'of']). That is below the 0.65 matched bar and at least the 0.25 partial bar, so status is partially_matched. The normalized query is not an exact substring of an admitted citation. This rule blocked the expected status.

### para-relational-databases

Admitted citations have best lexical 0.5000 (skill:SQL overlap ['database']; skill:PostgreSQL overlap ['database']; education:Metro Institute of Technology overlap ['database']). That is below the 0.65 matched bar and at least the 0.25 partial bar, so status is partially_matched. The normalized query is not an exact substring of an admitted citation. Labeled relevant evidence outside the recorded top 5: `project:AI Resume Automation / careerOS`, `project:Legal Document OCR and Extraction System`, `experience:Northstar Digital Studio`, `experience:Civic Tech Lab`. This rule blocked the expected status.

## Near-miss and unsupported cases

These ten cases have no relevant chunk. Correct rank is n/a. Scores are the rank-1 neighbor. Expected status is `not_evidenced`.

| Case | Top-1 evidence | Lexical | Vector | Combined | Correct rank | Status | Rule |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| near-kubernetes | skill:Docker | 0.0000 | 0.3471 | 0.1041 | n/a | not_evidenced (expected not_evidenced) | explicit_phrase_absent |
| near-cicd | skill:Docker | 0.0000 | 0.3974 | 0.1192 | n/a | not_evidenced (expected not_evidenced) | explicit_phrase_absent |
| near-django | experience:Northstar Digital Studio | 0.0000 | 0.3459 | 0.1038 | n/a | not_evidenced (expected not_evidenced) | citation_filter_empty |
| near-spring | project:AI Resume Automation / careerOS | 0.0000 | 0.2433 | 0.0730 | n/a | not_evidenced (expected not_evidenced) | citation_filter_empty |
| near-attorney | skill:LangGraph | 0.0000 | 0.1911 | 0.0573 | n/a | not_evidenced (expected not_evidenced) | citation_filter_empty |
| unsup-aws | profile | 0.3333 | 0.3602 | 0.3414 | n/a | not_evidenced (expected not_evidenced) | explicit_phrase_absent |
| unsup-terraform | skill:GitHub | 0.0000 | 0.2062 | 0.0619 | n/a | not_evidenced (expected not_evidenced) | citation_filter_empty |
| unsup-salesforce | experience:Northstar Digital Studio | 0.0000 | 0.3527 | 0.1058 | n/a | not_evidenced (expected not_evidenced) | citation_filter_empty |
| unsup-swiftui | skill:FastAPI | 0.0000 | 0.2295 | 0.0688 | n/a | not_evidenced (expected not_evidenced) | citation_filter_empty |
| unsup-rust | skill:GitHub | 0.0000 | 0.2465 | 0.0739 | n/a | not_evidenced (expected not_evidenced) | citation_filter_empty |

### near-kubernetes

Query triggers explicit phrase rule Kubernetes. `_evaluate_explicit_evidence` found no corpus chunk with the required alias, so status is not_evidenced. Hybrid scores are not consulted. Rank-1 neighbor is skill:Docker at lexical 0.0000, vector 0.3471, combined 0.1041 (overlap none). This rule produced the expected status.

### near-cicd

Query triggers explicit phrase rule CI/CD. `_evaluate_explicit_evidence` found no corpus chunk with the required alias, so status is not_evidenced. Hybrid scores are not consulted. Rank-1 neighbor is skill:Docker at lexical 0.0000, vector 0.3974, combined 0.1192 (overlap none). This rule produced the expected status.

### near-django

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 experience:Northstar Digital Studio has lexical 0.0000 and vector 0.3459. The highest top-3 vector is 0.3459. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. This rule produced the expected status.

### near-spring

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 project:AI Resume Automation / careerOS has lexical 0.0000 and vector 0.2433. The highest top-3 vector is 0.2433. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. This rule produced the expected status.

### near-attorney

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 skill:LangGraph has lexical 0.0000 and vector 0.1911. The highest top-3 vector is 0.1911. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. This rule produced the expected status.

### unsup-aws

Query triggers explicit phrase rule AWS. `_evaluate_explicit_evidence` found no corpus chunk with the required alias, so status is not_evidenced. Hybrid scores are not consulted. Rank-1 neighbor is profile at lexical 0.3333, vector 0.3602, combined 0.3414 (overlap ['services']). This rule produced the expected status.

### unsup-terraform

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 skill:GitHub has lexical 0.0000 and vector 0.2062. The highest top-3 vector is 0.2062. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. This rule produced the expected status.

### unsup-salesforce

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 experience:Northstar Digital Studio has lexical 0.0000 and vector 0.3527. The highest top-3 vector is 0.3527. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. This rule produced the expected status.

### unsup-swiftui

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 skill:FastAPI has lexical 0.0000 and vector 0.2295. The highest top-3 vector is 0.2295. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. This rule produced the expected status.

### unsup-rust

No top-3 chunk was admitted. Admission requires lexical_score > 0 or vector_score >= 0.45. Rank-1 skill:GitHub has lexical 0.0000 and vector 0.2465. The highest top-3 vector is 0.2465. `_evaluate_text` returns not_evidenced on the empty citation list, before the 0.65 lexical bar is evaluated. This rule produced the expected status.

## What the scores can separate

`para-ocr` rank 1 vector is 0.3141. The non-explicit negatives at or above that vector are `near-django`, `unsup-salesforce`. A vector matched bar low enough to accept `para-ocr` therefore adds near-miss and unsupported false positives on this run.

Among negatives that do not trigger an explicit phrase rule, the strongest top-3 vector is 0.3527 on `unsup-salesforce`. A vector matched bar above that score adds no near-miss or unsupported false positive on this run. Paraphrase cases above it: `para-containers`, `para-python-web-framework`, `para-human-approval`.

The existing 0.45 citation floor is above every paraphrase top-3 vector in this arm (none). `para-human-approval` reaches 0.4406 and `para-containers` `skill:Docker` reaches 0.4279. Lowering the citation floor by itself does not change status, because after admission the matched decision still requires an exact substring or lexical score >= 0.65.

## Simulated options

Both options are applied offline to the same recorded top 3. Explicit phrase rules stay in front and keep the product status. The current lexical matched path also stays. An option can only add `matched`. Product source is unchanged.

### Option A: top-3 vector matched bar (0.42)

After the explicit phrase rules and the current matched conditions (exact substring or lexical >= 0.65), also mark `matched` when any top-3 chunk has vector_score >= 0.42. 0.42 sits inside the measured zero-false-positive band: above Salesforce 0.3527 and CI/CD's Docker neighbor 0.3974, and still at or below `para-containers` skill:Docker 0.4279 and `para-human-approval` 0.4406.

Cases that change:

- `para-containers`: partially_matched -> matched via skill:Docker (lexical 0.0000, vector 0.4279, combined 0.1284)
- `para-human-approval`: partially_matched -> matched via project:AI Workflow Automation System (lexical 0.3333, vector 0.4406, combined 0.3655)

### Option B: same-chunk partial confirmation (lexical 0.25 and vector 0.30)

After the explicit phrase rules and the current matched conditions, also mark `matched` when one top-3 chunk has lexical_score >= 0.25 and vector_score >= 0.30. The lexical floor is the existing partial bar. The vector floor sits below `para-relational-databases` skill:SQL 0.3413 and `para-human-approval` 0.4406, and above the incidental partials `para-sql-expansion` 0.2078 and the `para-containers` "system" overlap 0.2318. Lexical and vector must come from the same chunk.

Cases that change:

- `para-human-approval`: partially_matched -> matched via project:AI Workflow Automation System (lexical 0.3333, vector 0.4406, combined 0.3655)
- `para-relational-databases`: partially_matched -> matched via skill:SQL (lexical 0.5000, vector 0.3413, combined 0.4524)

## Comparison

| Option | Status accuracy | Paraphrase status | Unsupported FP | Near-miss FP | Cases that change |
| --- | ---: | ---: | ---: | ---: | --- |
| Current product gate | 19/24 | 1/6 | 0/5 | 0/5 | — |
| Option A: top-3 vector matched bar (0.42) | 21/24 | 3/6 | 0/5 | 0/5 | para-containers, para-human-approval |
| Option B: same-chunk partial confirmation (lexical 0.25 and vector 0.30) | 21/24 | 3/6 | 0/5 | 0/5 | para-human-approval, para-relational-databases |

## Recommendation

Choice: **leave_unchanged**.

Leave the product status gate unchanged. The measured miss that retrieval already ranked correctly is `para-ocr`: relevant evidence is rank 1 with lexical 0.0000 and vector 0.3141. Both simulated options leave that case `not_evidenced`. An absolute vector cut low enough to admit that 0.3141 score also admits `near-django`, `unsup-salesforce` on this frozen run (Django vector 0.3459, Salesforce vector 0.3527), even while the AWS, Kubernetes, and CI/CD phrase rules stay in front. The 0.42 vector bar moves `para-containers` (partially_matched -> matched), `para-human-approval` (partially_matched -> matched). The accepted Docker skill vector is 0.4279 and the CI/CD neighbor on `skill:Docker` is 0.3974. That gap is too small to add a new constant from one 24-case run. The same-chunk partial confirmation moves `para-human-approval` (partially_matched -> matched), `para-relational-databases` (partially_matched -> matched). It still misses `para-ocr` and `para-sql-expansion`. `unsup-aws` would satisfy the same numeric test (lexical 0.3333, vector 0.3602) if the explicit AWS phrase rule did not return first. Unsupported false positives stay 0/5 and near-miss false positives stay 0/5 under both options. Those safe counts do not repair the rank-correct zero-lexical miss, so neither rule is worth implementing yet.

This recommendation is not implemented in product code.

## How to reproduce

```text
cd backend
python -m scripts.status_gate_diagnosis
```

The command rewrites `evals/results/status_gate_diagnosis.json` and `evals/results/status_gate_diagnosis.md` from `evals/results/results.json`. It does not read `OPENAI_API_KEY`.

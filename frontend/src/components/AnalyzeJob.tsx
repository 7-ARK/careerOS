import {FormEvent, ReactNode, useEffect, useState} from 'react';
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  FileCheck2,
  FileText,
  History,
  Link2,
  LoaderCircle,
  SearchCheck,
  ShieldCheck,
  X,
} from 'lucide-react';
import {
  ApiError,
  CandidateEvidence,
  DocumentFormat,
  downloadGeneratedDocument,
  extractJobUrl,
  GeneratedDocument,
  getActiveCandidateId,
  getGoldenCareerAnalysis,
  GoldenCareerAnalysis,
  listCandidateCareerAnalyses,
  RequirementEvidenceMatch,
  reviewGoldenCareerAnalysis,
  SourcePlatform,
  startGoldenCareerAnalysis,
  setActiveCandidateId,
} from '../lib/api';
import {CandidateProfiles} from './CandidateProfiles';

type ImportMode = 'manual' | 'url';
type ManualPlatform = 'linkedin' | 'indeed' | 'glassdoor' | 'company' | 'other' | 'unknown';

const PLATFORM_OPTIONS: {label: string; value: ManualPlatform}[] = [
  {label: 'Company page', value: 'company'},
  {label: 'LinkedIn', value: 'linkedin'},
  {label: 'Indeed', value: 'indeed'},
  {label: 'Glassdoor', value: 'glassdoor'},
  {label: 'Other', value: 'other'},
  {label: 'Unknown', value: 'unknown'},
];

const SOURCE_PLATFORM: Record<ManualPlatform, SourcePlatform> = {
  linkedin: 'linkedin',
  indeed: 'indeed',
  glassdoor: 'glassdoor',
  company: 'company_site',
  other: 'other',
  unknown: 'unknown',
};
const IS_EXTERNAL_PREVIEW = import.meta.env.VITE_PREVIEW_MODE === 'true';

interface AnalyzeJobProps {
  analysisSelection: {analysisId: string; candidateProfileId: string} | null;
}

export function AnalyzeJob({analysisSelection}: AnalyzeJobProps) {
  const [candidateProfileId, setCandidateProfileId] = useState(getActiveCandidateId);
  const [importMode, setImportMode] = useState<ImportMode>('manual');
  const [jobUrl, setJobUrl] = useState('');
  const [rawTitle, setRawTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [location, setLocation] = useState('');
  const [descriptionText, setDescriptionText] = useState('');
  const [sourcePlatform, setSourcePlatform] = useState<ManualPlatform>('company');
  const [run, setRun] = useState<GoldenCareerAnalysis | null>(null);
  const [history, setHistory] = useState<GoldenCareerAnalysis[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [reviewNotes, setReviewNotes] = useState('');
  const [isWorking, setIsWorking] = useState(false);
  const [downloadingId, setDownloadingId] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let active = true;
    async function loadHistory() {
      if (!candidateProfileId) {
        setHistory([]);
        return;
      }
      setIsLoadingHistory(true);
      try {
        const items = await listCandidateCareerAnalyses(candidateProfileId);
        if (active) setHistory(items);
      } catch (error) {
        if (active) {
          setErrorMessage(getErrorMessage(error, 'Analysis history could not be loaded.'));
        }
      } finally {
        if (active) setIsLoadingHistory(false);
      }
    }
    void loadHistory();
    return () => { active = false; };
  }, [candidateProfileId]);

  useEffect(() => {
    if (!analysisSelection) return;
    let active = true;
    setCandidateProfileId(analysisSelection.candidateProfileId);
    setActiveCandidateId(analysisSelection.candidateProfileId);
    setIsWorking(true);
    setErrorMessage('');
    void getGoldenCareerAnalysis(analysisSelection.analysisId)
      .then((persistedRun) => {
        if (!active) return;
        setRun(persistedRun);
        setReviewNotes(persistedRun.review_notes ?? '');
        setHistory((items) => [
          persistedRun,
          ...items.filter((item) => item.id !== persistedRun.id),
        ]);
        requestAnimationFrame(() => document.getElementById('analysis-results')?.focus());
      })
      .catch((error) => {
        if (active) {
          setErrorMessage(getErrorMessage(error, 'The saved analysis could not be loaded.'));
        }
      })
      .finally(() => {
        if (active) setIsWorking(false);
      });
    return () => { active = false; };
  }, [analysisSelection]);

  async function handleUrlExtraction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidateProfileId) {
      setErrorMessage('Select a candidate profile first.');
      return;
    }
    setIsWorking(true);
    setErrorMessage('');
    try {
      const extracted = await extractJobUrl({
        candidate_profile_id: candidateProfileId,
        job_url: jobUrl.trim(),
        create_application_record: false,
        headless: true,
        timeout_seconds: 30,
      });
      if (!extracted.pipeline_ready) {
        throw new ApiError('Automatic extraction was incomplete. Paste the job description manually.', {
          code: 'extraction_incomplete',
        });
      }
      setRawTitle(extracted.raw_title ?? '');
      setCompanyName(extracted.company_name ?? '');
      setLocation(extracted.location ?? '');
      setDescriptionText(extracted.description_text);
      setSourcePlatform(extracted.detected_platform === 'company_site' ? 'company' : extracted.detected_platform);
      setImportMode('manual');
    } catch (error) {
      setImportMode('manual');
      setErrorMessage(getErrorMessage(error, 'Job extraction failed. Paste the description manually.'));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleAnalysis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidateProfileId) {
      setErrorMessage('Select a candidate profile before starting analysis.');
      return;
    }
    setIsWorking(true);
    setRun(null);
    setErrorMessage('');
    try {
      const completedRun = await startGoldenCareerAnalysis({
        candidate_profile_id: candidateProfileId,
        raw_title: rawTitle.trim(),
        company_name: companyName.trim(),
        location: location.trim(),
        source_platform: SOURCE_PLATFORM[sourcePlatform],
        job_url: jobUrl.trim(),
        description_text: descriptionText.trim(),
        mode: 'mock',
      });
      setRun(completedRun);
      setHistory((items) => [
        completedRun,
        ...items.filter((item) => item.id !== completedRun.id),
      ]);
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'The evidence analysis could not be completed.'));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleReview(decision: 'approve' | 'reject') {
    if (!run) return;
    setIsWorking(true);
    setErrorMessage('');
    try {
      const reviewedRun = await reviewGoldenCareerAnalysis(
        run.id,
        decision,
        reviewNotes.trim(),
      );
      setRun(reviewedRun);
      setHistory((items) =>
        items.map((item) => item.id === reviewedRun.id ? reviewedRun : item),
      );
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'The review decision could not be saved.'));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleDownload(document: GeneratedDocument) {
    setDownloadingId(document.id);
    setErrorMessage('');
    try {
      await downloadGeneratedDocument(document.id);
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'The document download failed.'));
    } finally {
      setDownloadingId('');
    }
  }

  return (
    <section className="px-4 pb-16 pt-8 sm:px-6" id="analyze-job">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-3xl">
          <span className="cozy-label mb-3 block">Golden Career Analysis Flow</span>
          <h2 className="text-2xl font-semibold leading-tight text-foreground sm:text-3xl">
            Tailor a resume for one job posting.
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Compare a verified candidate profile with one job, inspect every evidence citation, then approve the grounded draft before export.
          </p>
        </div>

        <CandidateProfiles
          selectedCandidateId={candidateProfileId}
          onSelectionChange={(candidateId) => {
            setCandidateProfileId(candidateId);
            setActiveCandidateId(candidateId);
          }}
        />

        <section className="border-b border-border/60 py-5" aria-labelledby="analysis-history-title">
          <div className="flex items-center gap-2">
            <History className="size-4 text-primary" />
            <h3 className="text-sm font-semibold" id="analysis-history-title">
              Analysis history
            </h3>
            {isLoadingHistory && (
              <LoaderCircle className="size-3.5 animate-spin text-muted-foreground" />
            )}
          </div>
          {history.length ? (
            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {(IS_EXTERNAL_PREVIEW ? history.slice(0, 10) : history).map((item) => (
                <button
                  aria-label={historyAccessibleName(item)}
                  aria-pressed={run?.id === item.id}
                  className={`min-w-64 rounded-md border px-3 py-3 text-left text-xs transition ${run?.id === item.id ? 'border-primary bg-primary/10 ring-1 ring-primary/25' : 'border-border bg-card hover:border-primary/40'}`}
                  key={item.id}
                  onClick={() => {
                    setRun(item);
                    setReviewNotes(item.review_notes ?? '');
                  }}
                  type="button"
                >
                  <strong className="block truncate text-foreground">
                    {analysisTitle(item)}
                  </strong>
                  <span className="mt-1 block truncate text-muted-foreground">{analysisCompany(item)}</span>
                  {analysisLocation(item) && <span className="mt-1 block truncate text-muted-foreground">{analysisLocation(item)}</span>}
                  <span className="mt-2 flex items-center justify-between gap-3 text-muted-foreground">
                    <span>{formatAnalysisDate(item.started_at)}</span>
                    <strong className="font-semibold text-primary">{formatScore(item.evidence_coverage_score)}%</strong>
                  </span>
                  <span className="mt-1 block font-medium text-foreground">{analysisState(item.status)}</span>
                </button>
              ))}
            </div>
          ) : !isLoadingHistory ? (
            <p className="mt-2 text-xs text-muted-foreground">
              No saved analyses for this profile yet.
            </p>
          ) : null}
        </section>

        <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="cozy-panel rounded-lg p-5 sm:p-6">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
              <div>
                <p className="cozy-label">Job input</p>
                <h3 className="mt-1 text-lg font-semibold">Manual description is the reliable path</h3>
              </div>
              <div className="cozy-panel-soft inline-flex rounded-lg p-1" aria-label="Job input method">
                <ModeButton active={importMode === 'manual'} label="Paste job manually" icon={<FileText className="size-4" />} onClick={() => setImportMode('manual')} />
                <ModeButton active={importMode === 'url'} disabled={IS_EXTERNAL_PREVIEW} label="Use job URL" icon={<Link2 className="size-4" />} onClick={() => setImportMode('url')} title="URL extraction is disabled in the shared demo; paste the job description manually." />
              </div>
            </div>

            {IS_EXTERNAL_PREVIEW && (
              <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
                Job URL extraction is disabled in this shared demo. Paste the job description manually to keep the preview local and deterministic.
              </p>
            )}

            {importMode === 'url' ? (
              <form className="space-y-4" onSubmit={handleUrlExtraction}>
                <Field label="Job URL">
                  <input className="cozy-field w-full rounded-lg px-3 py-2.5 text-sm outline-none" type="url" value={jobUrl} onChange={(event) => setJobUrl(event.target.value)} required />
                </Field>
                <PrimaryButton disabled={isWorking} label="Extract job details" loading={isWorking} />
              </form>
            ) : (
              <form className="space-y-4" onSubmit={handleAnalysis}>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Job title"><input className="cozy-field w-full rounded-lg px-3 py-2.5 text-sm outline-none" value={rawTitle} onChange={(event) => setRawTitle(event.target.value)} maxLength={250} required /></Field>
                  <Field label="Company"><input className="cozy-field w-full rounded-lg px-3 py-2.5 text-sm outline-none" value={companyName} onChange={(event) => setCompanyName(event.target.value)} maxLength={250} required /></Field>
                  <Field label="Location"><input className="cozy-field w-full rounded-lg px-3 py-2.5 text-sm outline-none" value={location} onChange={(event) => setLocation(event.target.value)} maxLength={250} /></Field>
                  <Field label="Source"><select className="cozy-field w-full rounded-lg px-3 py-2.5 text-sm outline-none" value={sourcePlatform} onChange={(event) => setSourcePlatform(event.target.value as ManualPlatform)}>{PLATFORM_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field>
                </div>
                <Field label="Job description">
                  <textarea className="cozy-field min-h-48 w-full resize-y rounded-lg px-3 py-2.5 text-sm leading-relaxed outline-none" value={descriptionText} onChange={(event) => setDescriptionText(event.target.value)} minLength={80} maxLength={50000} required />
                </Field>
                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <p className="text-xs text-muted-foreground">Deterministic demo mode uses no paid API key.</p>
                  <PrimaryButton disabled={isWorking} label="Analyze evidence" loading={isWorking} />
                </div>
              </form>
            )}
          </div>

          <aside className="cozy-panel self-start rounded-lg p-5">
            <p className="cozy-label">Bounded workflow</p>
            <ol className="mt-4 space-y-3 text-sm">
              {['Validate profile and job', 'Extract typed requirements', 'Retrieve verified evidence', 'Calculate coverage in code', 'Draft and validate claims', 'Wait for human approval'].map((label, index) => (
                <li className="flex items-start gap-3" key={label}><span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold">{index + 1}</span><span className="pt-0.5 text-muted-foreground">{label}</span></li>
              ))}
            </ol>
            <div className="mt-5 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
              Suggestions remain separate from verified profile evidence. Exports stay blocked until approval.
            </div>
          </aside>
        </div>

        {errorMessage && <div className="mt-5 flex items-start gap-2 rounded-lg border border-destructive/35 bg-destructive/5 px-4 py-3 text-sm text-destructive" role="alert"><AlertCircle className="mt-0.5 size-4 shrink-0" />{errorMessage}</div>}
        {run && <AnalysisResults run={run} reviewNotes={reviewNotes} setReviewNotes={setReviewNotes} isWorking={isWorking} onReview={handleReview} onDownload={handleDownload} downloadingId={downloadingId} />}
      </div>
    </section>
  );
}

function AnalysisResults({run, reviewNotes, setReviewNotes, isWorking, onReview, onDownload, downloadingId}: {
  run: GoldenCareerAnalysis;
  reviewNotes: string;
  setReviewNotes: (value: string) => void;
  isWorking: boolean;
  onReview: (decision: 'approve' | 'reject') => void;
  onDownload: (document: GeneratedDocument) => void;
  downloadingId: string;
}) {
  const explanation = run.match_explanation;
  return (
    <div className="mt-8 space-y-6 outline-none" aria-live="polite" id="analysis-results" tabIndex={-1}>
      <section className="cozy-panel rounded-lg p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><p className="cozy-label">Saved evidence analysis</p><h3 className="mt-2 text-2xl font-semibold">{run.resume_draft?.target_role ?? 'Career analysis'}</h3><p className="mt-1 text-sm text-muted-foreground">{run.match_explanation?.requirements.company}</p></div>
          <div className="grid min-w-56 grid-cols-2 gap-3">
            <Metric label="Evidence coverage" value={`${formatScore(run.evidence_coverage_score)}%`} />
            <Metric label="Grounding" value={run.grounding_validation?.valid ? 'Validated' : 'Review'} />
          </div>
        </div>
        <div className="mt-5 grid gap-2 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
          {run.stages.map((stage) => <div className="flex items-start gap-2 rounded-md bg-secondary/55 px-3 py-2 text-xs" key={stage.stage}>{stage.status === 'completed' ? <Check className="mt-0.5 size-3.5 shrink-0 text-primary" /> : <LoaderCircle className="mt-0.5 size-3.5 shrink-0 text-brand-amber" />}<span><strong className="block font-medium text-foreground">{humanize(stage.stage)}</strong><span className="text-muted-foreground">{stage.latency_ms === null ? 'Waiting' : `${stage.latency_ms} ms`}</span></span></div>)}
        </div>
      </section>

      {explanation && (
        <section className="cozy-panel rounded-lg p-5 sm:p-6">
          <div className="flex items-start gap-3"><SearchCheck className="mt-0.5 size-5 text-primary" /><div><h3 className="text-lg font-semibold">Requirement-to-evidence map</h3><p className="mt-1 text-sm leading-relaxed text-muted-foreground">{explanation.overall_fit_summary}</p></div></div>
          <div className="mt-5 divide-y divide-border border-y border-border">
            {explanation.requirement_matches.map((match) => <div key={match.requirement.requirement_id}><RequirementRow match={match} /></div>)}
          </div>
          <p className="mt-4 text-xs text-muted-foreground">Score formula: {explanation.evidence_coverage.formula}</p>
        </section>
      )}

      {run.resume_draft && <ResumePreview run={run} />}

      {run.status === 'awaiting_review' && (
        <section className="cozy-panel rounded-lg p-5 sm:p-6">
          <div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 size-5 text-primary" /><div><h3 className="text-lg font-semibold">Human review required</h3><p className="mt-1 text-sm text-muted-foreground">Approval confirms you reviewed the cited draft. Only then will DOCX and PDF files be generated.</p></div></div>
          <label className="mt-5 block"><span className="cozy-label mb-2 block">Review notes</span><textarea className="cozy-field min-h-24 w-full rounded-lg px-3 py-2.5 text-sm outline-none" value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} maxLength={2000} /></label>
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="cozy-button inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50" disabled={isWorking} onClick={() => onReview('approve')} type="button">{isWorking ? <LoaderCircle className="size-4 animate-spin" /> : <FileCheck2 className="size-4" />}Approve and export</button>
            <button className="cozy-button-secondary inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50" disabled={isWorking} onClick={() => onReview('reject')} type="button"><X className="size-4" />Reject draft</button>
          </div>
        </section>
      )}

      {run.status === 'completed' && (
        <section className="cozy-panel rounded-lg p-5 sm:p-6">
          <div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 size-5 text-primary" /><div><h3 className="text-lg font-semibold">Approved and saved</h3><p className="mt-1 text-sm text-muted-foreground">The grounded resume was exported and the application remains available in the tracker.</p></div></div>
          <div className="mt-5 flex flex-wrap gap-3">{run.generated_documents.map((document) => <button className="cozy-button inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium" key={document.id} onClick={() => onDownload(document)} type="button">{downloadingId === document.id ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}Download {document.output_format.toUpperCase()}</button>)}</div>
        </section>
      )}

      {run.status === 'rejected' && (
        <section className="cozy-panel rounded-lg border-destructive/35 p-5 sm:p-6" role="status">
          <div className="flex items-start gap-3">
            <X className="mt-0.5 size-5 text-destructive" />
            <div>
              <h3 className="text-lg font-semibold">Rejected</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                This draft was rejected during human review. No documents were exported.
              </p>
              {run.review_notes && (
                <p className="mt-3 text-sm"><strong>Review note:</strong> {run.review_notes}</p>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function RequirementRow({match}: {match: RequirementEvidenceMatch}) {
  const [open, setOpen] = useState(match.status !== 'matched');
  return (
    <div className="py-3">
      <button aria-expanded={open} className="flex w-full items-start justify-between gap-4 text-left" onClick={() => setOpen((value) => !value)} type="button">
        <span className="flex items-start gap-3"><StatusIcon status={match.status} /><span><strong className="block text-sm font-medium">{match.requirement.text}</strong><span className="mt-0.5 block text-xs text-muted-foreground">{humanize(match.status)} · {match.requirement.priority}</span></span></span>
        {open ? <ChevronDown className="size-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="size-4 shrink-0 text-muted-foreground" />}
      </button>
      {open && <div className="ml-8 mt-3 space-y-2"><p className="text-sm text-muted-foreground">{match.explanation}</p>{match.supporting_evidence.map((evidence) => <div key={evidence.evidence_id}><EvidenceCitation evidence={evidence} /></div>)}{match.recommendation && <p className="rounded-md bg-accent/40 px-3 py-2 text-sm"><strong>Next step:</strong> {match.recommendation}</p>}</div>}
    </div>
  );
}

function EvidenceCitation({evidence}: {evidence: CandidateEvidence}) {
  return <div className="rounded-md border border-border bg-card px-3 py-2"><div className="flex flex-wrap items-center gap-2 text-xs"><span className="font-mono text-primary">{evidence.evidence_id}</span><span className="text-muted-foreground">verified {evidence.category} · score {Number(evidence.retrieval_score).toFixed(2)}</span></div><p className="mt-1 text-sm leading-relaxed">{evidence.text}</p></div>;
}

function ResumePreview({run}: {run: GoldenCareerAnalysis}) {
  const draft = run.resume_draft!;
  return <section className="cozy-panel rounded-lg p-5 sm:p-6"><div className="flex items-start gap-3"><FileText className="mt-0.5 size-5 text-primary" /><div><h3 className="text-lg font-semibold">Grounded resume preview</h3><p className="mt-1 text-sm text-muted-foreground">Every generated claim group stores supporting evidence IDs.</p></div></div><div className="mt-5 rounded-lg border border-border bg-card p-5"><h4 className="text-xl font-semibold">{draft.title}</h4><p className="mt-3 text-sm leading-relaxed">{draft.summary}</p><PreviewSection label="Skills" items={draft.skills_section} /><PreviewSection label="Experience" items={draft.experience_section} /><PreviewSection label="Projects" items={draft.projects_section} /><PreviewSection label="Education" items={draft.education_section} /><PreviewSection label="Certifications" items={draft.certifications_section} /></div><div className="mt-4 flex flex-wrap gap-2">{draft.grounding_manifest.map((claim, index) => <span className="rounded-md bg-secondary px-2.5 py-1 text-xs text-muted-foreground" key={`${claim.claim_type}-${index}`}>{claim.claim_type}: {claim.evidence_ids.length} citation(s)</span>)}</div></section>;
}

function PreviewSection({label, items}: {label: string; items: Record<string, unknown>[]}) {
  if (!items.length) return null;
  return <div className="mt-5"><h5 className="cozy-label">{label}</h5><ul className="mt-2 space-y-3 text-sm">{items.map((item, index) => <li className="border-l-2 border-primary/30 pl-3" key={index}><PreviewItem item={item} section={label} /></li>)}</ul></div>;
}

function PreviewItem({item, section}: {item: Record<string, unknown>; section: string}) {
  if (section === 'Skills') {
    const skills = listValue(item, 'skills');
    return <><strong className="font-medium">{textValue(item, 'category') ?? textValue(item, 'name') ?? 'Skills'}</strong>{skills.length ? `: ${skills.join(', ')}` : ''}</>;
  }
  const heading = section === 'Experience'
    ? [textValue(item, 'job_title'), textValue(item, 'company')].filter(Boolean).join(' at ')
    : section === 'Projects'
      ? textValue(item, 'title')
      : section === 'Education'
        ? [textValue(item, 'degree'), textValue(item, 'institution')].filter(Boolean).join(' at ')
        : [textValue(item, 'name'), textValue(item, 'issuing_organization')].filter(Boolean).join(' - ');
  const description = textValue(item, 'description') ?? (section === 'Education' ? textValue(item, 'field_of_study') : null);
  const details = section === 'Projects' ? listValue(item, 'technologies') : [];
  const bullets = section === 'Projects' ? listValue(item, 'outcomes') : listValue(item, 'achievements');
  const dateRange = section === 'Experience' ? previewDateRange(item.start_date, item.end_date) : null;
  const links = section === 'Projects'
    ? [
        ['GitHub', textValue(item, 'github_url')],
        ['Project link', textValue(item, 'portfolio_url')],
      ].filter((entry): entry is [string, string] => Boolean(entry[1]))
    : [];
  return <div><div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1"><strong className="font-medium">{heading || section}</strong>{dateRange && <span className="text-xs text-muted-foreground">{dateRange}</span>}</div>{details.length > 0 && <p className="mt-1 text-xs text-muted-foreground">{details.join(', ')}</p>}{description && <p className="mt-1 leading-relaxed text-muted-foreground">{description}</p>}{bullets.length > 0 && <ul className="mt-1 list-disc space-y-1 pl-4 text-muted-foreground">{bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>}{links.length > 0 && <div className="mt-2 flex gap-3">{links.map(([label, url]) => <a className="text-xs font-medium text-primary underline-offset-2 hover:underline" href={url} key={url} rel="noreferrer" target="_blank">{label}</a>)}</div>}</div>;
}

function Field({label, children}: {label: string; children: ReactNode}) {
  return <label className="block"><span className="cozy-label mb-2 block">{label}</span>{children}</label>;
}

function ModeButton({active, disabled = false, label, icon, onClick, title}: {active: boolean; disabled?: boolean; label: string; icon: ReactNode; onClick: () => void; title?: string}) {
  return <button className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`} disabled={disabled} onClick={onClick} title={title} type="button">{icon}{label}</button>;
}

function PrimaryButton({disabled, label, loading}: {disabled: boolean; label: string; loading: boolean}) {
  return <button className="cozy-button inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50" disabled={disabled} type="submit">{loading ? <LoaderCircle className="size-4 animate-spin" /> : <SearchCheck className="size-4" />}{label}</button>;
}

function Metric({label, value}: {label: string; value: string}) {
  return <div className="rounded-md border border-border bg-card px-3 py-2"><span className="cozy-label block">{label}</span><strong className="mt-1 block text-sm">{value}</strong></div>;
}

function StatusIcon({status}: {status: RequirementEvidenceMatch['status']}) {
  if (status === 'matched') return <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />;
  if (status === 'partially_matched') return <AlertCircle className="mt-0.5 size-4 shrink-0 text-brand-amber" />;
  return <X className="mt-0.5 size-4 shrink-0 text-destructive" />;
}

function textValue(item: Record<string, unknown>, key: string): string | null {
  const value = item[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

function listValue(item: Record<string, unknown>, key: string): string[] {
  const value = item[key];
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string' && Boolean(entry.trim())) : [];
}

function previewDateRange(start: unknown, end: unknown): string | null {
  if (typeof start !== 'string') return null;
  return `${formatPreviewDate(start)} - ${typeof end === 'string' ? formatPreviewDate(end) : 'Present'}`;
}

function formatPreviewDate(value: string): string {
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.valueOf()) ? value : new Intl.DateTimeFormat(undefined, {month: 'short', year: 'numeric'}).format(parsed);
}

function formatScore(score: string | null): string {
  return score === null ? '0' : Number(score).toFixed(1);
}

function analysisTitle(analysis: GoldenCareerAnalysis): string {
  return analysis.structured_requirements?.job_title
    ?? analysis.match_explanation?.requirements.job_title
    ?? analysis.resume_draft?.target_role
    ?? 'Career analysis';
}

function analysisCompany(analysis: GoldenCareerAnalysis): string {
  return analysis.structured_requirements?.company
    ?? analysis.match_explanation?.requirements.company
    ?? 'Company not recorded';
}

function analysisLocation(analysis: GoldenCareerAnalysis): string | null {
  return analysis.structured_requirements?.location
    ?? analysis.match_explanation?.requirements.location
    ?? null;
}

function analysisState(status: GoldenCareerAnalysis['status']): string {
  if (status === 'awaiting_review' || status === 'running') return 'Awaiting review';
  if (status === 'completed') return 'Completed';
  if (status === 'rejected') return 'Rejected';
  return 'Analysis unavailable';
}

function formatAnalysisDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? 'Date unavailable'
    : new Intl.DateTimeFormat(undefined, {dateStyle: 'medium'}).format(date);
}

function historyAccessibleName(analysis: GoldenCareerAnalysis): string {
  const date = new Date(analysis.started_at);
  const accessibleDate = Number.isNaN(date.valueOf())
    ? 'date unavailable'
    : new Intl.DateTimeFormat(undefined, {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      }).format(date);
  return [
    `${analysisTitle(analysis)} at ${analysisCompany(analysis)}`,
    analysisLocation(analysis),
    analysisState(analysis.status).toLowerCase(),
    `${formatScore(analysis.evidence_coverage_score)}% coverage`,
    accessibleDate,
  ].filter(Boolean).join(', ');
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

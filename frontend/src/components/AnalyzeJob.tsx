import {FormEvent, ReactNode, useState} from 'react';
import {AlertCircle, CheckCircle2, Download, Link2, LoaderCircle, SlidersHorizontal} from 'lucide-react';
import {motion} from 'motion/react';
import {
  ApiError,
  downloadGeneratedDocument,
  JobUrlPipelineResult,
  runUrlPipeline,
  SourcePlatform,
} from '../lib/api';

type WorkflowState = 'idle' | 'loading' | 'success' | 'extraction_failed' | 'pipeline_failed';

const MANUAL_IMPORT_URL = 'http://127.0.0.1:8000/docs#/pipeline/run_manual_pipeline_api_v1_pipeline_manual_post';

export function AnalyzeJob() {
  const [candidateProfileId, setCandidateProfileId] = useState('');
  const [jobUrl, setJobUrl] = useState('');
  const [sourcePlatform, setSourcePlatform] = useState<SourcePlatform | ''>('');
  const [workflowState, setWorkflowState] = useState<WorkflowState>('idle');
  const [result, setResult] = useState<JobUrlPipelineResult | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [isDownloading, setIsDownloading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorkflowState('loading');
    setResult(null);
    setErrorMessage('');

    try {
      const response = await runUrlPipeline({
        candidate_profile_id: candidateProfileId.trim(),
        job_url: jobUrl.trim(),
        ...(sourcePlatform ? {source_platform: sourcePlatform} : {}),
        create_application_record: true,
        resume_template_name: 'clean_ats',
        document_format: 'pdf',
        headless: true,
        timeout_seconds: 30,
      });
      setResult(response);
      setWorkflowState(response.pipeline ? 'success' : 'extraction_failed');
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'The pipeline could not be completed.');
      setWorkflowState('pipeline_failed');
    }
  }

  async function handleDownload() {
    if (!result?.pipeline) {
      return;
    }

    setIsDownloading(true);
    setErrorMessage('');
    try {
      await downloadGeneratedDocument(result.pipeline.generated_document_id);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'The resume download failed.');
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <section className="border-y border-border/50 bg-card/40 px-6 py-20 md:py-24" id="analyze-job">
      <div className="mx-auto grid max-w-5xl gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.75fr)] lg:gap-14">
        <div>
          <span className="mb-3 inline-block text-xs font-semibold uppercase tracking-widest text-brand-amber">
            Analyze a Job
          </span>
          <h2 className="max-w-2xl font-serif text-3xl font-medium leading-tight text-foreground sm:text-4xl">
            Turn a live posting into a tailored resume.
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Paste a public job link. careerOS reads the page, compares it with your candidate profile, and prepares an ATS-safe resume.
          </p>

          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Candidate profile ID
              </span>
              <input
                required
                value={candidateProfileId}
                onChange={(event) => setCandidateProfileId(event.target.value)}
                placeholder="Paste your candidate_profile_id"
                className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
              <span className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                <SlidersHorizontal className="size-3.5 text-brand-amber" />
                Temporary advanced field until candidate accounts are available.
              </span>
            </label>

            <label className="block">
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Job posting URL
              </span>
              <div className="flex items-center rounded-lg border border-border bg-background px-4 transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
                <Link2 className="mr-3 size-4 shrink-0 text-brand-amber" />
                <input
                  required
                  type="url"
                  value={jobUrl}
                  onChange={(event) => setJobUrl(event.target.value)}
                  placeholder="https://www.linkedin.com/jobs/view/..."
                  className="min-w-0 flex-1 bg-transparent py-3 text-sm text-foreground outline-none"
                />
              </div>
            </label>

            <label className="block max-w-xs">
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Source platform
              </span>
              <select
                value={sourcePlatform}
                onChange={(event) => setSourcePlatform(event.target.value as SourcePlatform | '')}
                className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              >
                <option value="">Detect automatically</option>
                <option value="linkedin">LinkedIn</option>
                <option value="indeed">Indeed</option>
                <option value="glassdoor">Glassdoor</option>
                <option value="company_site">Company careers page</option>
                <option value="other">Other</option>
              </select>
            </label>

            <motion.button
              type="submit"
              disabled={workflowState === 'loading'}
              whileHover={workflowState === 'loading' ? undefined : {scale: 1.01}}
              whileTap={workflowState === 'loading' ? undefined : {scale: 0.99}}
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground shadow-md shadow-primary/10 transition hover:brightness-110 disabled:cursor-wait disabled:opacity-70"
            >
              {workflowState === 'loading' ? <LoaderCircle className="size-4 animate-spin" /> : <Link2 className="size-4" />}
              {workflowState === 'loading' ? 'Analyzing job' : 'Analyze job'}
            </motion.button>
          </form>
        </div>

        <WorkflowResult
          state={workflowState}
          result={result}
          errorMessage={errorMessage}
          isDownloading={isDownloading}
          onDownload={handleDownload}
        />
      </div>
    </section>
  );
}

interface WorkflowResultProps {
  state: WorkflowState;
  result: JobUrlPipelineResult | null;
  errorMessage: string;
  isDownloading: boolean;
  onDownload: () => void;
}

function WorkflowResult({state, result, errorMessage, isDownloading, onDownload}: WorkflowResultProps) {
  if (state === 'loading') {
    return (
      <ResultPanel>
        <LoaderCircle className="size-7 animate-spin text-primary" />
        <p className="mt-5 text-sm leading-relaxed text-foreground">
          Reading job page and preparing your resume...
        </p>
      </ResultPanel>
    );
  }

  if (state === 'extraction_failed') {
    return (
      <ResultPanel>
        <AlertCircle className="size-7 text-brand-amber" />
        <h3 className="mt-5 font-serif text-xl text-foreground">We need a little more detail.</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          URL extraction did not return enough detail. Use manual import instead.
        </p>
        <Warnings warnings={result?.extraction.extraction_warnings || []} />
        <a
          href={MANUAL_IMPORT_URL}
          target="_blank"
          rel="noreferrer"
          className="mt-6 inline-flex rounded-full border border-brand-amber/50 px-5 py-2.5 text-sm font-medium text-brand-amber transition hover:bg-brand-amber/10"
        >
          Use manual import
        </a>
      </ResultPanel>
    );
  }

  if (state === 'pipeline_failed') {
    return (
      <ResultPanel>
        <AlertCircle className="size-7 text-destructive" />
        <h3 className="mt-5 font-serif text-xl text-foreground">The pipeline could not finish.</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{errorMessage}</p>
      </ResultPanel>
    );
  }

  if (state === 'success' && result?.pipeline) {
    const {pipeline, extraction} = result;
    const warnings = [...extraction.extraction_warnings, ...pipeline.warnings];
    return (
      <ResultPanel>
        <CheckCircle2 className="size-7 text-primary" />
        <h3 className="mt-5 font-serif text-2xl text-foreground">{pipeline.role_title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{pipeline.company_name}</p>
        <div className="mt-6 grid grid-cols-2 gap-3">
          <ResultMetric label="Match score" value={`${pipeline.match_score}%`} />
          <ResultMetric label="Status" value={pipeline.status} />
        </div>
        <ResultId label="Document ID" value={pipeline.generated_document_id} />
        {pipeline.application_record_id && <ResultId label="Application ID" value={pipeline.application_record_id} />}
        <Warnings warnings={warnings} />
        {errorMessage && <p className="mt-4 text-xs leading-relaxed text-destructive">{errorMessage}</p>}
        <button
          type="button"
          disabled={isDownloading}
          onClick={onDownload}
          className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition hover:brightness-110 disabled:cursor-wait disabled:opacity-70"
        >
          {isDownloading ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
          {isDownloading ? 'Preparing download' : 'Download resume'}
        </button>
      </ResultPanel>
    );
  }

  return (
    <ResultPanel>
      <Link2 className="size-7 text-brand-amber" />
      <h3 className="mt-5 font-serif text-xl text-foreground">Your tailored result will appear here.</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Keep your candidate profile ID handy, then paste a posting from LinkedIn, Indeed, Glassdoor, or a public careers page.
      </p>
    </ResultPanel>
  );
}

function ResultPanel({children}: {children: ReactNode}) {
  return <aside className="self-start rounded-lg border border-border bg-background/80 p-6 shadow-xl shadow-black/10 lg:mt-8">{children}</aside>;
}

function ResultMetric({label, value}: {label: string; value: string}) {
  return (
    <div className="rounded-lg border border-border/70 bg-secondary/50 p-3">
      <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="mt-1 block text-sm capitalize text-foreground">{value.replaceAll('_', ' ')}</span>
    </div>
  );
}

function ResultId({label, value}: {label: string; value: string}) {
  return (
    <div className="mt-4">
      <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="mt-1 block break-all font-mono text-[11px] leading-relaxed text-foreground/80">{value}</span>
    </div>
  );
}

function Warnings({warnings}: {warnings: string[]}) {
  if (!warnings.length) {
    return null;
  }
  return (
    <div className="mt-5 border-t border-border/60 pt-4">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-amber">Extraction warnings</span>
      <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-muted-foreground">
        {warnings.map((warning) => <li key={warning}>{warning}</li>)}
      </ul>
    </div>
  );
}

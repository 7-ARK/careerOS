import {FormEvent, ReactNode, useState} from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileText,
  Link2,
  LoaderCircle,
  SlidersHorizontal,
} from 'lucide-react';
import {motion} from 'motion/react';
import {
  ApiError,
  DocumentFormat,
  downloadGeneratedDocument,
  ManualJobPipelineResult,
  ResumeTemplateName,
  runManualPipeline,
  runUrlPipeline,
  SourcePlatform,
} from '../lib/api';

type ImportMode = 'url' | 'manual';
type WorkflowState = 'idle' | 'loading' | 'success' | 'extraction_failed' | 'pipeline_failed';
type ManualPlatform =
  | 'linkedin'
  | 'indeed'
  | 'glassdoor'
  | 'greenhouse'
  | 'lever'
  | 'ashby'
  | 'company'
  | 'other'
  | 'unknown';

const PLATFORM_OPTIONS: {label: string; value: ManualPlatform}[] = [
  {label: 'LinkedIn', value: 'linkedin'},
  {label: 'Indeed', value: 'indeed'},
  {label: 'Glassdoor', value: 'glassdoor'},
  {label: 'Greenhouse', value: 'greenhouse'},
  {label: 'Lever', value: 'lever'},
  {label: 'Ashby', value: 'ashby'},
  {label: 'Company page', value: 'company'},
  {label: 'Other', value: 'other'},
  {label: 'Unknown', value: 'unknown'},
];

const MANUAL_PLATFORM_TO_SOURCE: Record<ManualPlatform, SourcePlatform> = {
  linkedin: 'linkedin',
  indeed: 'indeed',
  glassdoor: 'glassdoor',
  greenhouse: 'company_site',
  lever: 'company_site',
  ashby: 'company_site',
  company: 'company_site',
  other: 'other',
  unknown: 'unknown',
};

export function AnalyzeJob() {
  const [mode, setMode] = useState<ImportMode>('url');
  const [candidateProfileId, setCandidateProfileId] = useState('');
  const [jobUrl, setJobUrl] = useState('');
  const [sourcePlatform, setSourcePlatform] = useState<ManualPlatform>('unknown');
  const [rawTitle, setRawTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [location, setLocation] = useState('');
  const [descriptionText, setDescriptionText] = useState('');
  const [companyEmail, setCompanyEmail] = useState('');
  const [documentFormat, setDocumentFormat] = useState<DocumentFormat>('pdf');
  const [templateName, setTemplateName] = useState<ResumeTemplateName>('clean_ats');
  const [createApplicationRecord, setCreateApplicationRecord] = useState(true);
  const [workflowState, setWorkflowState] = useState<WorkflowState>('idle');
  const [pipelineResult, setPipelineResult] = useState<ManualJobPipelineResult | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState('');
  const [isDownloading, setIsDownloading] = useState(false);

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorkflowState('loading');
    setPipelineResult(null);
    setWarnings([]);
    setErrorMessage('');

    try {
      const response = await runUrlPipeline({
        candidate_profile_id: candidateProfileId.trim(),
        job_url: jobUrl.trim(),
        source_platform: MANUAL_PLATFORM_TO_SOURCE[sourcePlatform],
        create_application_record: true,
        resume_template_name: 'clean_ats',
        document_format: 'pdf',
        headless: true,
        timeout_seconds: 30,
      });
      setWarnings(response.extraction.extraction_warnings ?? []);
      if (response.pipeline) {
        setPipelineResult(response.pipeline);
        setWorkflowState('success');
      } else {
        setWorkflowState('extraction_failed');
      }
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'The pipeline could not be completed.');
      setWorkflowState('pipeline_failed');
    }
  }

  async function handleManualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorkflowState('loading');
    setPipelineResult(null);
    setWarnings([]);
    setErrorMessage('');

    try {
      const response = await runManualPipeline({
        candidate_profile_id: candidateProfileId.trim(),
        raw_title: rawTitle.trim(),
        company_name: companyName.trim(),
        location: location.trim(),
        source_platform: MANUAL_PLATFORM_TO_SOURCE[sourcePlatform],
        job_url: jobUrl.trim(),
        description_text: descriptionText.trim(),
        company_email: companyEmail.trim(),
        document_format: documentFormat,
        resume_template_name: templateName,
        create_application_record: createApplicationRecord,
      });
      setPipelineResult(response);
      setWarnings(response.warnings ?? []);
      setWorkflowState('success');
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'The manual pipeline could not be completed.');
      setWorkflowState('pipeline_failed');
    }
  }

  async function handleDownload() {
    if (!pipelineResult) {
      return;
    }

    setIsDownloading(true);
    setErrorMessage('');
    try {
      await downloadGeneratedDocument(pipelineResult.generated_document_id);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'The resume download failed.');
    } finally {
      setIsDownloading(false);
    }
  }

  function switchMode(nextMode: ImportMode) {
    setMode(nextMode);
    setWorkflowState('idle');
    setPipelineResult(null);
    setWarnings([]);
    setErrorMessage('');
  }

  return (
    <section className="border-y border-border/50 bg-card/40 px-6 py-20 md:py-24" id="analyze-job">
      <div className="mx-auto grid max-w-5xl gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.75fr)] lg:gap-14">
        <div>
          <span className="mb-3 inline-block text-xs font-semibold uppercase tracking-widest text-brand-amber">
            Analyze a Job
          </span>
          <h2 className="max-w-2xl font-serif text-3xl font-medium leading-tight text-foreground sm:text-4xl">
            Turn a job posting into a tailored resume.
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Use a public job URL first. If extraction is blocked, paste the job description manually and run the same pipeline.
          </p>

          <div className="mt-7 inline-flex rounded-full border border-border bg-background p-1">
            <ModeButton active={mode === 'url'} icon={<Link2 className="size-4" />} label="Use URL" onClick={() => switchMode('url')} />
            <ModeButton active={mode === 'manual'} icon={<FileText className="size-4" />} label="Paste job manually" onClick={() => switchMode('manual')} />
          </div>

          {mode === 'url' ? (
            <UrlImportForm
              candidateProfileId={candidateProfileId}
              jobUrl={jobUrl}
              sourcePlatform={sourcePlatform}
              isLoading={workflowState === 'loading'}
              onCandidateProfileIdChange={setCandidateProfileId}
              onJobUrlChange={setJobUrl}
              onSourcePlatformChange={setSourcePlatform}
              onSubmit={handleUrlSubmit}
            />
          ) : (
            <ManualImportForm
              candidateProfileId={candidateProfileId}
              rawTitle={rawTitle}
              companyName={companyName}
              location={location}
              sourcePlatform={sourcePlatform}
              jobUrl={jobUrl}
              descriptionText={descriptionText}
              companyEmail={companyEmail}
              documentFormat={documentFormat}
              templateName={templateName}
              createApplicationRecord={createApplicationRecord}
              isLoading={workflowState === 'loading'}
              onCandidateProfileIdChange={setCandidateProfileId}
              onRawTitleChange={setRawTitle}
              onCompanyNameChange={setCompanyName}
              onLocationChange={setLocation}
              onSourcePlatformChange={setSourcePlatform}
              onJobUrlChange={setJobUrl}
              onDescriptionTextChange={setDescriptionText}
              onCompanyEmailChange={setCompanyEmail}
              onDocumentFormatChange={setDocumentFormat}
              onTemplateNameChange={setTemplateName}
              onCreateApplicationRecordChange={setCreateApplicationRecord}
              onSubmit={handleManualSubmit}
            />
          )}
        </div>

        <WorkflowResult
          state={workflowState}
          mode={mode}
          result={pipelineResult}
          warnings={warnings}
          errorMessage={errorMessage}
          isDownloading={isDownloading}
          onDownload={handleDownload}
          onUseManualImport={() => switchMode('manual')}
        />
      </div>
    </section>
  );
}

interface ModeButtonProps {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}

function ModeButton({active, icon, label, onClick}: ModeButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition ${
        active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

interface UrlImportFormProps {
  candidateProfileId: string;
  jobUrl: string;
  sourcePlatform: ManualPlatform;
  isLoading: boolean;
  onCandidateProfileIdChange: (value: string) => void;
  onJobUrlChange: (value: string) => void;
  onSourcePlatformChange: (value: ManualPlatform) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function UrlImportForm({
  candidateProfileId,
  jobUrl,
  sourcePlatform,
  isLoading,
  onCandidateProfileIdChange,
  onJobUrlChange,
  onSourcePlatformChange,
  onSubmit,
}: UrlImportFormProps) {
  return (
    <form className="mt-8 space-y-5" onSubmit={onSubmit}>
      <CandidateProfileField value={candidateProfileId} onChange={onCandidateProfileIdChange} />

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
            onChange={(event) => onJobUrlChange(event.target.value)}
            placeholder="https://www.linkedin.com/jobs/view/..."
            className="min-w-0 flex-1 bg-transparent py-3 text-sm text-foreground outline-none"
          />
        </div>
      </label>

      <PlatformField value={sourcePlatform} onChange={onSourcePlatformChange} includeAutoDetect />

      <PrimaryButton isLoading={isLoading} idleIcon={<Link2 className="size-4" />} idleLabel="Analyze job" loadingLabel="Analyzing job" />
    </form>
  );
}

interface ManualImportFormProps {
  candidateProfileId: string;
  rawTitle: string;
  companyName: string;
  location: string;
  sourcePlatform: ManualPlatform;
  jobUrl: string;
  descriptionText: string;
  companyEmail: string;
  documentFormat: DocumentFormat;
  templateName: ResumeTemplateName;
  createApplicationRecord: boolean;
  isLoading: boolean;
  onCandidateProfileIdChange: (value: string) => void;
  onRawTitleChange: (value: string) => void;
  onCompanyNameChange: (value: string) => void;
  onLocationChange: (value: string) => void;
  onSourcePlatformChange: (value: ManualPlatform) => void;
  onJobUrlChange: (value: string) => void;
  onDescriptionTextChange: (value: string) => void;
  onCompanyEmailChange: (value: string) => void;
  onDocumentFormatChange: (value: DocumentFormat) => void;
  onTemplateNameChange: (value: ResumeTemplateName) => void;
  onCreateApplicationRecordChange: (value: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function ManualImportForm({
  candidateProfileId,
  rawTitle,
  companyName,
  location,
  sourcePlatform,
  jobUrl,
  descriptionText,
  companyEmail,
  documentFormat,
  templateName,
  createApplicationRecord,
  isLoading,
  onCandidateProfileIdChange,
  onRawTitleChange,
  onCompanyNameChange,
  onLocationChange,
  onSourcePlatformChange,
  onJobUrlChange,
  onDescriptionTextChange,
  onCompanyEmailChange,
  onDocumentFormatChange,
  onTemplateNameChange,
  onCreateApplicationRecordChange,
  onSubmit,
}: ManualImportFormProps) {
  return (
    <form className="mt-8 space-y-5" onSubmit={onSubmit}>
      <CandidateProfileField value={candidateProfileId} onChange={onCandidateProfileIdChange} />

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label="Job title" value={rawTitle} onChange={onRawTitleChange} placeholder="AI Automation Developer" required />
        <TextField label="Company" value={companyName} onChange={onCompanyNameChange} placeholder="Example Labs" required />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label="Location" value={location} onChange={onLocationChange} placeholder="Remote, US" />
        <TextField label="Company email" value={companyEmail} onChange={onCompanyEmailChange} placeholder="careers@example.com" type="email" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <PlatformField value={sourcePlatform} onChange={onSourcePlatformChange} />
        <TextField label="Job URL" value={jobUrl} onChange={onJobUrlChange} placeholder="https://company.com/jobs/123" type="url" />
      </div>

      <label className="block">
        <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Job description
        </span>
        <textarea
          required
          value={descriptionText}
          onChange={(event) => onDescriptionTextChange(event.target.value)}
          placeholder="Paste the full job description, requirements, responsibilities, and qualifications."
          rows={9}
          className="w-full resize-y rounded-lg border border-border bg-background px-4 py-3 text-sm leading-relaxed text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label="Document format"
          value={documentFormat}
          onChange={(value) => onDocumentFormatChange(value as DocumentFormat)}
          options={[
            {label: 'PDF', value: 'pdf'},
            {label: 'DOCX', value: 'docx'},
            {label: 'Markdown', value: 'markdown'},
          ]}
        />
        <SelectField
          label="Resume template"
          value={templateName}
          onChange={(value) => onTemplateNameChange(value as ResumeTemplateName)}
          options={[
            {label: 'Clean ATS', value: 'clean_ats'},
            {label: 'Modern Professional', value: 'modern_professional'},
          ]}
        />
      </div>

      <label className="flex items-start gap-3 rounded-lg border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
        <input
          checked={createApplicationRecord}
          onChange={(event) => onCreateApplicationRecordChange(event.target.checked)}
          type="checkbox"
          className="mt-1 size-4 accent-primary"
        />
        <span>Create a not-applied application record for this job.</span>
      </label>

      <PrimaryButton isLoading={isLoading} idleIcon={<FileText className="size-4" />} idleLabel="Run manual import" loadingLabel="Generating resume" />
    </form>
  );
}

function CandidateProfileField({value, onChange}: {value: string; onChange: (value: string) => void}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Candidate profile ID
      </span>
      <input
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Paste your candidate_profile_id"
        className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
      <span className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
        <SlidersHorizontal className="size-3.5 text-brand-amber" />
        Temporary advanced field until candidate accounts are available.
      </span>
    </label>
  );
}

function PlatformField({
  value,
  onChange,
  includeAutoDetect = false,
}: {
  value: ManualPlatform;
  onChange: (value: ManualPlatform) => void;
  includeAutoDetect?: boolean;
}) {
  return (
    <SelectField
      label="Source platform"
      value={value}
      onChange={(selected) => onChange(selected as ManualPlatform)}
      options={[
        ...(includeAutoDetect ? [{label: 'Detect automatically', value: 'unknown'}] : []),
        ...PLATFORM_OPTIONS,
      ]}
    />
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <input
        required={required}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: {label: string; value: string}[];
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
      >
        {options.map((option, index) => (
          <option key={`${label}-${option.value}-${index}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function PrimaryButton({
  isLoading,
  idleIcon,
  idleLabel,
  loadingLabel,
}: {
  isLoading: boolean;
  idleIcon: ReactNode;
  idleLabel: string;
  loadingLabel: string;
}) {
  return (
    <motion.button
      type="submit"
      disabled={isLoading}
      whileHover={isLoading ? undefined : {scale: 1.01}}
      whileTap={isLoading ? undefined : {scale: 0.99}}
      className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground shadow-md shadow-primary/10 transition hover:brightness-110 disabled:cursor-wait disabled:opacity-70"
    >
      {isLoading ? <LoaderCircle className="size-4 animate-spin" /> : idleIcon}
      {isLoading ? loadingLabel : idleLabel}
    </motion.button>
  );
}

interface WorkflowResultProps {
  state: WorkflowState;
  mode: ImportMode;
  result: ManualJobPipelineResult | null;
  warnings: string[];
  errorMessage: string;
  isDownloading: boolean;
  onDownload: () => void;
  onUseManualImport: () => void;
}

function WorkflowResult({
  state,
  mode,
  result,
  warnings,
  errorMessage,
  isDownloading,
  onDownload,
  onUseManualImport,
}: WorkflowResultProps) {
  if (state === 'loading') {
    return (
      <ResultPanel>
        <LoaderCircle className="size-7 animate-spin text-primary" />
        <p className="mt-5 text-sm leading-relaxed text-foreground">
          {mode === 'url' ? 'Reading job page and preparing your resume...' : 'Preparing your resume from the pasted job description...'}
        </p>
      </ResultPanel>
    );
  }

  if (state === 'extraction_failed') {
    return (
      <ResultPanel>
        <AlertCircle className="size-7 text-brand-amber" />
        <h3 className="mt-5 font-serif text-xl text-foreground">We need the job text.</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          URL extraction did not return enough detail. Paste the job description manually instead.
        </p>
        <Warnings warnings={warnings} />
        <button
          type="button"
          onClick={onUseManualImport}
          className="mt-6 inline-flex rounded-full border border-brand-amber/50 px-5 py-2.5 text-sm font-medium text-brand-amber transition hover:bg-brand-amber/10"
        >
          Use Manual Import
        </button>
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

  if (state === 'success' && result) {
    return (
      <ResultPanel>
        <CheckCircle2 className="size-7 text-primary" />
        <h3 className="mt-5 font-serif text-2xl text-foreground">{result.role_title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{result.company_name}</p>
        <SectionHeading label="Match Summary" />
        <div className="mt-6 grid grid-cols-2 gap-3">
          <ResultMetric label="Match score" value={`${result.match_score}%`} />
          <ResultMetric label="Status" value={result.status} />
        </div>
        <ResultId label="Document ID" value={result.generated_document_id} />
        {result.application_record_id && <ResultId label="Application ID" value={result.application_record_id} />}
        <SectionHeading label="Resume Review" />
        <ReviewList label="Matched Skills" values={result.matched_skills ?? []} />
        <ReviewList label="Missing Skills" values={result.missing_skills ?? []} emptyLabel="No required skill gaps found." />
        <ReviewList label="Matched Technologies" values={result.matched_technologies ?? []} />
        <ReviewList
          label="Missing Technologies"
          values={result.missing_technologies ?? []}
          emptyLabel="No required technology gaps found."
        />
        <ProjectReviewList
          label="Selected Projects"
          projects={result.selected_projects ?? []}
          emptyLabel="No selected project review available yet."
        />
        <ProjectReviewList
          label="Excluded Projects"
          projects={result.excluded_projects ?? []}
          hideWhenEmpty
        />
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
      {mode === 'url' ? <Link2 className="size-7 text-brand-amber" /> : <FileText className="size-7 text-brand-amber" />}
      <h3 className="mt-5 font-serif text-xl text-foreground">Your tailored result will appear here.</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        {mode === 'url'
          ? 'Paste a public posting URL. If extraction fails, switch to manual import.'
          : 'Paste the job details manually to run the same resume pipeline without URL extraction.'}
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

function SectionHeading({label}: {label: string}) {
  return (
    <div className="mt-6 border-t border-border/60 pt-4">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-amber">{label}</span>
    </div>
  );
}

function ReviewList({
  label,
  values,
  emptyLabel = 'No matches found.',
}: {
  label: string;
  values: string[];
  emptyLabel?: string;
}) {
  const hasValues = values.length > 0;
  return (
    <div className="mt-4">
      <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {hasValues ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {values.map((value) => (
            <span
              key={`${label}-${value}`}
              className="rounded-full border border-border bg-secondary/50 px-2.5 py-1 text-xs text-foreground/90"
            >
              {value}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{emptyLabel}</p>
      )}
    </div>
  );
}

function ProjectReviewList({
  label,
  projects = [],
  emptyLabel,
  hideWhenEmpty = false,
}: {
  label: string;
  projects?: {title: string; score: number; reason: string}[];
  emptyLabel?: string;
  hideWhenEmpty?: boolean;
}) {
  const projectItems = projects ?? [];
  if (!projectItems.length && hideWhenEmpty) {
    return null;
  }
  return (
    <div className="mt-4">
      <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {projectItems.length ? (
        <ul className="mt-2 space-y-2 text-xs leading-relaxed text-muted-foreground">
          {projectItems.map((project) => (
            <li key={`${label}-${project.title}`}>
              <span className="text-foreground">{project.title}</span>
              <span className="block">{project.reason}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {emptyLabel ?? 'No project review available yet.'}
        </p>
      )}
    </div>
  );
}

function Warnings({warnings}: {warnings: string[]}) {
  if (!warnings.length) {
    return null;
  }
  return (
    <div className="mt-5 border-t border-border/60 pt-4">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-amber">Warnings</span>
      <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-muted-foreground">
        {warnings.map((warning) => <li key={warning}>{warning}</li>)}
      </ul>
    </div>
  );
}

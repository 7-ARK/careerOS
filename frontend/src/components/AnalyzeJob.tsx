import {FormEvent, ReactNode, useState} from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileText,
  Link2,
  LoaderCircle,
} from 'lucide-react';
import {motion} from 'motion/react';
import {
  ApiError,
  DocumentFormat,
  downloadGeneratedDocument,
  extractJobUrl,
  ManualJobPipelineResult,
  ResumeTemplateName,
  runManualPipeline,
  SourcePlatform,
} from '../lib/api';
import {CandidateProfiles} from './CandidateProfiles';

type ImportMode = 'url' | 'manual';
type WorkflowState =
  | 'idle'
  | 'loading'
  | 'extracted'
  | 'success'
  | 'extraction_failed'
  | 'pipeline_failed';
type ManualPlatform =
  | 'linkedin'
  | 'indeed'
  | 'glassdoor'
  | 'greenhouse'
  | 'lever'
  | 'company'
  | 'other'
  | 'unknown';

const PLATFORM_OPTIONS: {label: string; value: ManualPlatform}[] = [
  {label: 'LinkedIn', value: 'linkedin'},
  {label: 'Indeed', value: 'indeed'},
  {label: 'Glassdoor', value: 'glassdoor'},
  {label: 'Greenhouse', value: 'greenhouse'},
  {label: 'Lever', value: 'lever'},
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
  company: 'company_site',
  other: 'other',
  unknown: 'unknown',
};

function platformFromExtraction(
  platform: SourcePlatform,
  jobUrl: string,
): ManualPlatform {
  if (platform !== 'company_site') {
    return platform;
  }
  const hostname = new URL(jobUrl).hostname.toLowerCase();
  if (hostname === 'greenhouse.io' || hostname.endsWith('.greenhouse.io')) {
    return 'greenhouse';
  }
  if (hostname === 'lever.co' || hostname.endsWith('.lever.co')) {
    return 'lever';
  }
  return 'company';
}

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
  const [workflowState, setWorkflowState] = useState<WorkflowState>('idle');
  const [pipelineResult, setPipelineResult] = useState<ManualJobPipelineResult | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState('');
  const [isDownloading, setIsDownloading] = useState(false);

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidateProfileId) {
      setErrorMessage('Select a candidate before extracting a job.');
      setWorkflowState('pipeline_failed');
      return;
    }
    setWorkflowState('loading');
    setPipelineResult(null);
    setWarnings([]);
    setErrorMessage('');
    setRawTitle('');
    setCompanyName('');
    setLocation('');
    setDescriptionText('');
    setCompanyEmail('');
    setSourcePlatform('unknown');

    try {
      const response = await extractJobUrl({
        candidate_profile_id: candidateProfileId.trim(),
        job_url: jobUrl.trim(),
        create_application_record: false,
        resume_template_name: 'clean_ats',
        document_format: 'pdf',
        headless: true,
        timeout_seconds: 30,
      });
      setWarnings(response.extraction_warnings ?? []);
      if (!response.pipeline_ready) {
        setMode('manual');
        setErrorMessage(
          response.detected_platform === 'unknown'
            ? 'Unsupported job platform. Please paste the job description manually.'
            : 'Could not extract this job posting automatically. Please paste the job description manually.',
        );
        setWorkflowState('extraction_failed');
        return;
      }

      setRawTitle(response.raw_title ?? '');
      setCompanyName(response.company_name ?? '');
      setLocation(response.location ?? '');
      setDescriptionText(response.description_text);
      setSourcePlatform(platformFromExtraction(response.detected_platform, response.job_url));
      setMode('manual');
      setWorkflowState('extracted');
    } catch (error) {
      setMode('manual');
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : 'Could not extract this job posting automatically. Please paste the job description manually.',
      );
      setWorkflowState('extraction_failed');
    }
  }

  async function handleManualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidateProfileId) {
      setErrorMessage('Select a candidate before running the pipeline.');
      setWorkflowState('pipeline_failed');
      return;
    }
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
        create_application_record: false,
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
    <section className="px-4 pb-16 pt-8 sm:px-6 md:pb-20" id="analyze-job">
      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-10">
        <motion.div
          initial={{opacity: 0, y: 18}}
          animate={{opacity: 1, y: 0}}
          transition={{duration: 0.55, ease: [0.22, 1, 0.36, 1]}}
        >
          <span className="cozy-label mb-3 block">
            Resume workspace
          </span>
          <h2 className="max-w-2xl text-2xl font-semibold leading-tight text-foreground sm:text-3xl">
            Tailor a resume for one job posting.
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Select a candidate, add a job posting, review the details, and generate the resume file.
          </p>

          <CandidateProfiles
            selectedCandidateId={candidateProfileId}
            onSelectionChange={setCandidateProfileId}
          />

          <div className="cozy-panel-soft mt-7 inline-flex rounded-xl p-1">
            <ModeButton active={mode === 'url'} icon={<Link2 className="size-4" />} label="Use URL" onClick={() => switchMode('url')} />
            <ModeButton
              active={mode === 'manual'}
              icon={<FileText className="size-4" />}
              label={workflowState === 'extracted' ? 'Review job details' : 'Paste job manually'}
              onClick={() => switchMode('manual')}
            />
          </div>

          {mode === 'url' ? (
            <UrlImportForm
              jobUrl={jobUrl}
              isLoading={workflowState === 'loading'}
              onJobUrlChange={setJobUrl}
              onSubmit={handleUrlSubmit}
            />
          ) : (
            <ManualImportForm
              rawTitle={rawTitle}
              companyName={companyName}
              location={location}
              sourcePlatform={sourcePlatform}
              jobUrl={jobUrl}
              descriptionText={descriptionText}
              companyEmail={companyEmail}
              documentFormat={documentFormat}
              templateName={templateName}
              isExtracted={workflowState === 'extracted'}
              isLoading={workflowState === 'loading'}
              onRawTitleChange={setRawTitle}
              onCompanyNameChange={setCompanyName}
              onLocationChange={setLocation}
              onSourcePlatformChange={setSourcePlatform}
              onJobUrlChange={setJobUrl}
              onDescriptionTextChange={setDescriptionText}
              onCompanyEmailChange={setCompanyEmail}
              onDocumentFormatChange={setDocumentFormat}
              onTemplateNameChange={setTemplateName}
              onSubmit={handleManualSubmit}
            />
          )}
        </motion.div>

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
      className={`inline-flex min-h-10 items-center gap-2 rounded-lg px-4 py-2 text-sm transition ${
        active ? 'cozy-button font-semibold' : 'text-muted-foreground hover:bg-secondary/70 hover:text-foreground'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

interface UrlImportFormProps {
  jobUrl: string;
  isLoading: boolean;
  onJobUrlChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function UrlImportForm({
  jobUrl,
  isLoading,
  onJobUrlChange,
  onSubmit,
}: UrlImportFormProps) {
  return (
    <form className="mt-8 space-y-5" onSubmit={onSubmit}>
      <div>
        <h3 className="text-lg font-semibold text-foreground">Import job from URL</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          LinkedIn, Indeed, Glassdoor, Greenhouse, or Lever
        </p>
      </div>

      <label className="block">
        <span className="cozy-label mb-2 block">
          Job posting URL
        </span>
        <div className="cozy-field flex items-center rounded-lg px-4 transition">
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

      <PrimaryButton isLoading={isLoading} idleIcon={<Link2 className="size-4" />} idleLabel="Extract job" loadingLabel="Extracting job" />
    </form>
  );
}

interface ManualImportFormProps {
  rawTitle: string;
  companyName: string;
  location: string;
  sourcePlatform: ManualPlatform;
  jobUrl: string;
  descriptionText: string;
  companyEmail: string;
  documentFormat: DocumentFormat;
  templateName: ResumeTemplateName;
  isExtracted: boolean;
  isLoading: boolean;
  onRawTitleChange: (value: string) => void;
  onCompanyNameChange: (value: string) => void;
  onLocationChange: (value: string) => void;
  onSourcePlatformChange: (value: ManualPlatform) => void;
  onJobUrlChange: (value: string) => void;
  onDescriptionTextChange: (value: string) => void;
  onCompanyEmailChange: (value: string) => void;
  onDocumentFormatChange: (value: DocumentFormat) => void;
  onTemplateNameChange: (value: ResumeTemplateName) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function ManualImportForm({
  rawTitle,
  companyName,
  location,
  sourcePlatform,
  jobUrl,
  descriptionText,
  companyEmail,
  documentFormat,
  templateName,
  isExtracted,
  isLoading,
  onRawTitleChange,
  onCompanyNameChange,
  onLocationChange,
  onSourcePlatformChange,
  onJobUrlChange,
  onDescriptionTextChange,
  onCompanyEmailChange,
  onDocumentFormatChange,
  onTemplateNameChange,
  onSubmit,
}: ManualImportFormProps) {
  return (
    <form className="mt-8 space-y-5" onSubmit={onSubmit}>
      {isExtracted && (
        <div>
          <h3 className="text-lg font-semibold text-foreground">Review extracted job details</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Check and edit these fields before generating the resume.
          </p>
        </div>
      )}
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
        <span className="cozy-label mb-2 block">
          Job description
        </span>
        <textarea
          required
          value={descriptionText}
          onChange={(event) => onDescriptionTextChange(event.target.value)}
          placeholder="Paste the full job description, requirements, responsibilities, and qualifications."
          rows={9}
          className="cozy-field w-full resize-y rounded-lg px-4 py-3 text-sm leading-relaxed text-foreground outline-none transition"
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

      <PrimaryButton isLoading={isLoading} idleIcon={<FileText className="size-4" />} idleLabel="Generate resume" loadingLabel="Writing resume" />
    </form>
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
      <span className="cozy-label mb-2 block">
        {label}
      </span>
      <input
        required={required}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="cozy-field w-full rounded-lg px-4 py-3 text-sm text-foreground outline-none transition"
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
      <span className="cozy-label mb-2 block">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="cozy-field w-full rounded-lg px-4 py-3 text-sm text-foreground outline-none transition"
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
      className="cozy-button inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-5 py-3 text-sm font-semibold transition disabled:cursor-wait disabled:opacity-70"
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
          {mode === 'url' ? 'Reading the job page...' : 'Preparing your resume from the reviewed job description...'}
        </p>
      </ResultPanel>
    );
  }

  if (state === 'extracted') {
    return (
      <ResultPanel>
        <CheckCircle2 className="size-7 text-primary" />
        <h3 className="mt-5 text-lg font-semibold text-foreground">Job details are ready to review.</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Make any tweaks you want, then generate the resume.
        </p>
        <Warnings warnings={warnings} />
      </ResultPanel>
    );
  }

  if (state === 'extraction_failed') {
    return (
      <ResultPanel>
        <AlertCircle className="size-7 text-brand-amber" />
        <h3 className="mt-5 text-lg font-semibold text-foreground">We need the job text.</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {errorMessage || 'Could not extract this job posting automatically. Please paste the job description manually.'}
        </p>
        <Warnings warnings={warnings.filter((warning) => warning !== errorMessage)} />
        <button
          type="button"
          onClick={onUseManualImport}
          className="cozy-button-secondary mt-6 inline-flex rounded-lg px-5 py-2.5 text-sm font-medium transition"
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
        <h3 className="mt-5 text-lg font-semibold text-foreground">The pipeline could not finish.</h3>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{errorMessage}</p>
      </ResultPanel>
    );
  }

  if (state === 'success' && result) {
    return (
      <ResultPanel>
        <CheckCircle2 className="size-7 text-primary" />
        <h3 className="mt-5 text-xl font-semibold text-foreground">{result.role_title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{result.company_name}</p>
        <SectionHeading label="Match Summary" />
        <div className="mt-6 grid grid-cols-2 gap-3">
          <ResultMetric label="Match score" value={`${result.match_score}%`} />
          <ResultMetric label="Status" value={result.status} />
        </div>
        <ResultId label="Document ID" value={result.generated_document_id} />
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
          className="cozy-button mt-6 inline-flex min-h-11 items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold transition disabled:cursor-wait disabled:opacity-70"
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
      <h3 className="mt-5 text-lg font-semibold text-foreground">Resume output</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        {mode === 'url'
          ? 'Paste a public posting URL. If extraction fails, switch to manual import.'
          : 'Paste the job details manually to run the same resume pipeline without URL extraction.'}
      </p>
    </ResultPanel>
  );
}

function ResultPanel({children}: {children: ReactNode}) {
  return <aside className="cozy-panel self-start rounded-xl p-5 lg:mt-8">{children}</aside>;
}

function ResultMetric({label, value}: {label: string; value: string}) {
  return (
    <div className="cozy-panel-soft rounded-lg p-3">
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
              className="rounded-full border border-border/70 bg-secondary/50 px-2.5 py-1 text-xs text-foreground/90"
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

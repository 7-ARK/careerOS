const DEFAULT_API_BASE_URL = '/api';
const TOKEN_STORAGE_KEY = 'careeros_access_token';
const ACTIVE_CANDIDATE_STORAGE_KEY = 'careeros_active_candidate_id';
export const AUTH_EXPIRED_EVENT = 'careeros:auth-expired';

export interface User {
  id: string;
  email: string;
  full_name: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  user: User;
}

export type SourcePlatform = 'linkedin' | 'indeed' | 'glassdoor' | 'company_site' | 'other' | 'unknown';
export type DocumentFormat = 'markdown' | 'docx' | 'pdf';
export type ResumeTemplateName = 'clean_ats' | 'modern_professional';

export interface CandidateSummary {
  id: string;
  full_name: string;
  email: string | null;
  headline: string | null;
}

export interface CandidateEducation {
  id: string;
  institution: string;
  degree: string;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

export interface CandidateSkill {
  id: string;
  name: string;
  category: string;
  self_rating: number;
  years_of_experience: string;
}

export interface CandidateProject {
  id: string;
  title: string;
  description: string;
  technologies: string[];
  outcomes: string[];
}

export interface CandidateCertification {
  id: string;
  name: string;
  issuing_organization: string;
  issue_date: string | null;
  expiration_date: string | null;
}

export interface CandidateExperience {
  id: string;
  company: string;
  job_title: string;
  employment_type: string | null;
  location: string | null;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  description: string | null;
  achievements: string[];
}

export interface CandidateProfile extends CandidateSummary {
  user_id: string;
  phone: string | null;
  summary: string | null;
  location: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  education: CandidateEducation[];
  skills: CandidateSkill[];
  projects: CandidateProject[];
  certifications: CandidateCertification[];
  work_experiences: CandidateExperience[];
}

export interface CandidateProfileInput {
  full_name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  headline: string | null;
  summary: string | null;
  education: CandidateEducationInput[];
  skills: CandidateSkillInput[];
  projects: CandidateProjectInput[];
  certifications: CandidateCertificationInput[];
  work_experiences: CandidateExperienceInput[];
}

export interface CandidateEducationInput {
  institution: string;
  degree: string;
  end_date?: string;
}

export interface CandidateSkillInput {
  name: string;
  category: string;
  self_rating: number;
  years_of_experience: number;
}

export interface CandidateProjectInput {
  title: string;
  description: string;
  technologies: string[];
}

export interface CandidateCertificationInput {
  name: string;
  issuing_organization: string;
  issue_date?: string;
}

export interface CandidateExperienceInput {
  job_title: string;
  company: string;
  start_date: string;
  end_date?: string;
  is_current: boolean;
  description?: string | null;
}

export interface ResumeImportPreview {
  file_name: string;
  profile: CandidateProfileInput;
  extracted_sections: string[];
  warnings: string[];
  requires_review: true;
}

export interface JobUrlPipelineRequest {
  candidate_profile_id: string;
  job_url: string;
  source_platform?: SourcePlatform;
  create_application_record?: boolean;
  resume_template_name?: ResumeTemplateName;
  document_format?: DocumentFormat;
  headless?: boolean;
  timeout_seconds?: number;
}

export interface ManualJobPipelineRequest {
  candidate_profile_id: string;
  raw_title: string;
  company_name: string;
  location?: string;
  source_platform?: SourcePlatform;
  job_url?: string;
  description_text: string;
  company_email?: string;
  document_format?: DocumentFormat;
  resume_template_name?: ResumeTemplateName;
  create_application_record?: boolean;
}

export interface JobUrlExtractionResult {
  job_url: string;
  detected_platform: SourcePlatform;
  raw_title: string | null;
  company_name: string | null;
  location: string | null;
  description_text: string;
  extraction_confidence: string;
  extraction_warnings: string[];
  pipeline_ready: boolean;
}

export interface ManualJobPipelineResult {
  generated_document_id: string;
  application_record_id: string | null;
  company_name: string;
  role_title: string;
  match_score: string;
  document_format: DocumentFormat;
  template_name: ResumeTemplateName;
  status: string;
  matched_skills?: string[];
  missing_skills?: string[];
  matched_technologies?: string[];
  missing_technologies?: string[];
  selected_projects?: ProjectSelectionReview[];
  excluded_projects?: ProjectSelectionReview[];
  warnings?: string[];
  next_actions: string[];
}

export interface ProjectSelectionReview {
  title: string;
  score: number;
  reason: string;
}

export interface JobUrlPipelineResult {
  extraction: JobUrlExtractionResult;
  pipeline: ManualJobPipelineResult | null;
}

export type ApplicationStatus =
  | 'not_applied'
  | 'saved'
  | 'applied'
  | 'interviewing'
  | 'offer'
  | 'accepted'
  | 'rejected'
  | 'withdrawn'
  | 'archived';
export type RequirementMatchStatus = 'matched' | 'partially_matched' | 'not_evidenced' | 'not_applicable';
export type CareerAnalysisStatus = 'running' | 'awaiting_review' | 'completed' | 'rejected' | 'failed';

export interface ApplicationRecord {
  id: string;
  candidate_profile_id: string;
  job_description_id: string | null;
  job_analysis_id: string | null;
  generated_document_id: string | null;
  company_name: string;
  role_title: string;
  company_email: string | null;
  job_url: string | null;
  status: ApplicationStatus;
  notes: string | null;
  evidence_coverage_score: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateEvidence {
  evidence_id: string;
  source_id: string;
  category: string;
  source: 'candidate_profile';
  text: string;
  verified: true;
  retrieval_score: string;
  why_retrieved: string;
}

export interface JobRequirement {
  requirement_id: string;
  text: string;
  kind: 'skill' | 'technology' | 'responsibility' | 'experience' | 'education';
  priority: 'required' | 'preferred' | 'context';
  logic: 'all' | 'any';
  alternatives: string[];
}

export interface RequirementEvidenceMatch {
  requirement: JobRequirement;
  status: RequirementMatchStatus;
  supporting_evidence: CandidateEvidence[];
  explanation: string;
  recommendation: string | null;
}

export interface MatchExplanation {
  requirements: {
    job_title: string;
    company: string | null;
    location: string | null;
    seniority: string;
  };
  requirement_matches: RequirementEvidenceMatch[];
  evidence_coverage: {
    score: string;
    formula: string;
    matched_count: number;
    partially_matched_count: number;
    not_evidenced_count: number;
    not_applicable_count: number;
  };
  overall_fit_summary: string;
  strongest_matches: string[];
  partial_matches: string[];
  missing_requirements: string[];
  supported_ats_keywords: string[];
  unsupported_ats_keywords: string[];
  learning_priorities: string[];
  interview_preparation_topics: string[];
  retrieval_provider: string;
  embedding_model: string;
}

export interface ResumeDraft {
  id: string;
  title: string;
  target_role: string;
  summary: string;
  skills_section: Record<string, unknown>[];
  experience_section: Record<string, unknown>[];
  projects_section: Record<string, unknown>[];
  education_section: Record<string, unknown>[];
  certifications_section: Record<string, unknown>[];
  ats_keywords_used: string[];
  omitted_keywords: string[];
  truthfulness_notes: string[];
  grounding_manifest: {claim_type: string; text: string; evidence_ids: string[]}[];
  status: string;
}

export interface GeneratedDocument {
  id: string;
  output_format: DocumentFormat;
  file_name: string;
  file_size_bytes: number | null;
  generation_status: string;
}

export interface CareerAnalysisStage {
  stage: string;
  status: 'completed' | 'failed' | 'awaiting_review';
  latency_ms: number | null;
  provider: string;
  model: string | null;
  summary: string | null;
  error: string | null;
}

export interface GoldenCareerAnalysis {
  id: string;
  candidate_profile_id: string;
  job_description_id: string | null;
  application_record_id: string | null;
  status: CareerAnalysisStatus;
  current_stage: string;
  provider: string;
  model_name: string | null;
  token_usage: Record<string, number>;
  estimated_cost_usd: string;
  started_at: string;
  finished_at: string | null;
  structured_requirements: MatchExplanation['requirements'] | null;
  evidence_coverage_score: string | null;
  stages: CareerAnalysisStage[];
  match_explanation: MatchExplanation | null;
  resume_draft: ResumeDraft | null;
  application_record: ApplicationRecord | null;
  generated_documents: GeneratedDocument[];
  grounding_validation: {
    valid: boolean;
    checked_claims: number;
    cited_claims: number;
    citation_coverage: string;
    unsupported_claims: string[];
  } | null;
  review_notes: string | null;
}

export interface GoldenCareerAnalysisRequest {
  candidate_profile_id: string;
  raw_title: string;
  company_name: string;
  location?: string;
  source_platform?: SourcePlatform;
  job_url?: string;
  description_text: string;
  resume_template_name?: ResumeTemplateName;
  top_k?: number;
  mode?: 'mock' | 'live';
}

interface ApiErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly details?: unknown;

  constructor(message: string, options: {code: string; status?: number; details?: unknown}) {
    super(message);
    this.name = 'ApiError';
    this.code = options.code;
    this.status = options.status;
    this.details = options.details;
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function getActiveCandidateId(): string {
  return localStorage.getItem(ACTIVE_CANDIDATE_STORAGE_KEY) ?? '';
}

export function setActiveCandidateId(candidateId: string): void {
  if (candidateId) {
    localStorage.setItem(ACTIVE_CANDIDATE_STORAGE_KEY, candidateId);
  } else {
    localStorage.removeItem(ACTIVE_CANDIDATE_STORAGE_KEY);
  }
}

export async function registerUser(request: {
  email: string;
  password: string;
  full_name?: string;
}): Promise<AuthResponse> {
  const response = await requestJson<AuthResponse>('/api/v1/auth/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(request),
  });
  localStorage.setItem(TOKEN_STORAGE_KEY, response.access_token);
  return response;
}

export async function loginUser(request: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  const response = await requestJson<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(request),
  });
  localStorage.setItem(TOKEN_STORAGE_KEY, response.access_token);
  return response;
}

export async function getCurrentUser(): Promise<User> {
  return requestJson<User>('/api/v1/auth/me');
}

export function getApiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/+$/, '');
}

export async function runUrlPipeline(request: JobUrlPipelineRequest): Promise<JobUrlPipelineResult> {
  return requestJson<JobUrlPipelineResult>('/api/v1/pipeline/url', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(request),
  });
}

export async function extractJobUrl(
  request: JobUrlPipelineRequest,
): Promise<JobUrlExtractionResult> {
  return requestJson<JobUrlExtractionResult>('/api/v1/pipeline/extract', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(request),
  });
}

export async function listCandidates(): Promise<CandidateSummary[]> {
  return requestJson<CandidateSummary[]>('/api/v1/candidates');
}

export async function getCandidateProfile(candidateId: string): Promise<CandidateProfile> {
  return requestJson<CandidateProfile>(`/api/v1/candidates/${encodeURIComponent(candidateId)}`);
}

export async function createCandidateProfile(
  profile: CandidateProfileInput,
): Promise<CandidateProfile> {
  return requestJson<CandidateProfile>('/api/v1/candidates', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(profile),
  });
}

export async function updateCandidateProfile(
  candidateId: string,
  profile: CandidateProfileInput,
): Promise<CandidateProfile> {
  return requestJson<CandidateProfile>(`/api/v1/candidates/${encodeURIComponent(candidateId)}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(profile),
  });
}

export async function deleteCandidateProfile(candidateId: string): Promise<void> {
  await apiFetch(`/api/v1/candidates/${encodeURIComponent(candidateId)}`, {method: 'DELETE'});
}

export async function importResumePreview(file: File): Promise<ResumeImportPreview> {
  const form = new FormData();
  form.append('resume', file);
  return requestJson<ResumeImportPreview>('/api/v1/candidates/import-preview', {
    method: 'POST',
    body: form,
  });
}

export async function runManualPipeline(request: ManualJobPipelineRequest): Promise<ManualJobPipelineResult> {
  return requestJson<ManualJobPipelineResult>('/api/v1/pipeline/manual', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(removeEmptyValues(request)),
  });
}

export async function startGoldenCareerAnalysis(
  request: GoldenCareerAnalysisRequest,
): Promise<GoldenCareerAnalysis> {
  return requestJson<GoldenCareerAnalysis>('/api/v1/career-analyses', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(removeEmptyValues(request)),
  });
}

export async function reviewGoldenCareerAnalysis(
  runId: string,
  decision: 'approve' | 'reject',
  reviewNotes: string,
): Promise<GoldenCareerAnalysis> {
  return requestJson<GoldenCareerAnalysis>(`/api/v1/career-analyses/${encodeURIComponent(runId)}/review`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      decision,
      review_notes: reviewNotes || undefined,
      export_formats: ['docx', 'pdf'],
    }),
  });
}

export async function listCandidateCareerAnalyses(
  candidateId: string,
): Promise<GoldenCareerAnalysis[]> {
  return requestJson<GoldenCareerAnalysis[]>(
    `/api/v1/career-analyses/candidate/${encodeURIComponent(candidateId)}`,
  );
}

export async function getGoldenCareerAnalysis(runId: string): Promise<GoldenCareerAnalysis> {
  return requestJson<GoldenCareerAnalysis>(
    `/api/v1/career-analyses/${encodeURIComponent(runId)}`,
  );
}

export async function listCandidateApplications(candidateId: string): Promise<ApplicationRecord[]> {
  return requestJson<ApplicationRecord[]>(`/api/v1/applications/${encodeURIComponent(candidateId)}`);
}

export async function updateApplicationStatus(
  applicationId: string,
  status: ApplicationStatus,
): Promise<ApplicationRecord> {
  return requestJson<ApplicationRecord>(`/api/v1/applications/${encodeURIComponent(applicationId)}/status`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status}),
  });
}

export async function downloadGeneratedDocument(documentId: string): Promise<void> {
  const response = await apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}/download`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = getDownloadFilename(response.headers.get('content-disposition'));
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  return response.json() as Promise<T>;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  const headers = new Headers(init?.headers);
  const token = getAccessToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  try {
    response = await fetch(resolveApiUrl(path), {...init, headers});
  } catch {
    throw new ApiError('Unable to reach the careerOS API. Confirm that the backend is running.', {
      code: 'network_error',
    });
  }

  if (response.ok) {
    return response;
  }

  if (response.status === 401 && token) {
    clearAccessToken();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }

  let payload: ApiErrorEnvelope = {};
  try {
    payload = (await response.json()) as ApiErrorEnvelope;
  } catch {
    // The fallback below covers non-JSON server responses.
  }

  throw new ApiError(payload.error?.message || `Request failed with status ${response.status}.`, {
    code: payload.error?.code || 'request_failed',
    status: response.status,
    details: payload.error?.details,
  });
}

function resolveApiUrl(path: string): string {
  const baseUrl = getApiBaseUrl();
  if (baseUrl === '/api' && path.startsWith('/api/')) {
    return `${baseUrl}${path.slice('/api'.length)}`;
  }
  return `${baseUrl}${path}`;
}

function getDownloadFilename(contentDisposition: string | null): string {
  const match = contentDisposition?.match(/filename="?([^";]+)"?/i);
  return match?.[1] || 'careerOS-resume.pdf';
}

function removeEmptyValues<T extends object>(request: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(request).filter(([, value]) => value !== '' && value !== undefined),
  ) as Partial<T>;
}

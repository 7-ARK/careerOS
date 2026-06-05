const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

export type SourcePlatform = 'linkedin' | 'indeed' | 'glassdoor' | 'company_site' | 'other' | 'unknown';
export type DocumentFormat = 'markdown' | 'docx' | 'pdf';
export type ResumeTemplateName = 'clean_ats' | 'modern_professional';

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

export async function runManualPipeline(request: ManualJobPipelineRequest): Promise<ManualJobPipelineResult> {
  return requestJson<ManualJobPipelineResult>('/api/v1/pipeline/manual', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(removeEmptyValues(request)),
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
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, init);
  } catch {
    throw new ApiError('Unable to reach the careerOS API. Confirm that the backend is running.', {
      code: 'network_error',
    });
  }

  if (response.ok) {
    return response;
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

function getDownloadFilename(contentDisposition: string | null): string {
  const match = contentDisposition?.match(/filename="?([^";]+)"?/i);
  return match?.[1] || 'careerOS-resume.pdf';
}

function removeEmptyValues<T extends object>(request: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(request).filter(([, value]) => value !== '' && value !== undefined),
  ) as Partial<T>;
}

import {useEffect, useState} from 'react';
import {
  AlertCircle,
  BriefcaseBusiness,
  ExternalLink,
  FileSearch,
  LoaderCircle,
  RefreshCw,
} from 'lucide-react';
import {
  ApiError,
  ApplicationRecord,
  ApplicationStatus,
  CandidateSummary,
  getActiveCandidateId,
  GoldenCareerAnalysis,
  listCandidateApplications,
  listCandidateCareerAnalyses,
  listCandidates,
  setActiveCandidateId,
  updateApplicationStatus,
} from '../lib/api';

const STATUS_OPTIONS: {value: ApplicationStatus; label: string}[] = [
  {value: 'saved', label: 'Saved'},
  {value: 'applied', label: 'Applied'},
  {value: 'interviewing', label: 'Interviewing'},
  {value: 'offer', label: 'Offer'},
  {value: 'accepted', label: 'Accepted'},
  {value: 'rejected', label: 'Rejected'},
  {value: 'withdrawn', label: 'Withdrawn'},
  {value: 'archived', label: 'Archived'},
];
const IS_EXTERNAL_PREVIEW = import.meta.env.VITE_PREVIEW_MODE === 'true';

interface ApplicationDashboardProps {
  onViewAnalysis: (selection: {analysisId: string; candidateProfileId: string}) => void;
}

export function ApplicationDashboard({onViewAnalysis}: ApplicationDashboardProps) {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [candidateId, setCandidateId] = useState(getActiveCandidateId);
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [analyses, setAnalyses] = useState<GoldenCareerAnalysis[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let active = true;
    async function loadCandidates() {
      try {
        const result = await listCandidates();
        if (!active) return;
        setCandidates(result);
        const selectedExists = result.some((candidate) => candidate.id === candidateId);
        const nextCandidateId = selectedExists ? candidateId : result[0]?.id ?? '';
        setCandidateId(nextCandidateId);
        setActiveCandidateId(nextCandidateId);
      } catch (error) {
        if (active) setErrorMessage(getErrorMessage(error, 'Candidate profiles could not be loaded.'));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadCandidates();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!candidateId) {
      setApplications([]);
      setAnalyses([]);
      return;
    }
    void refresh(candidateId);
  }, [candidateId]);

  async function refresh(selectedCandidateId = candidateId) {
    if (!selectedCandidateId) return;
    setIsLoading(true);
    setErrorMessage('');
    try {
      const [applicationItems, analysisItems] = await Promise.all([
        listCandidateApplications(selectedCandidateId),
        listCandidateCareerAnalyses(selectedCandidateId),
      ]);
      setApplications(applicationItems);
      setAnalyses(analysisItems);
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'Application records could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }

  async function changeStatus(application: ApplicationRecord, status: ApplicationStatus) {
    setUpdatingId(application.id);
    setErrorMessage('');
    try {
      const updated = await updateApplicationStatus(application.id, status);
      setApplications((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'Application status could not be updated.'));
    } finally {
      setUpdatingId('');
    }
  }

  const analysisByApplicationId = new Map<string, GoldenCareerAnalysis>(
    analyses.flatMap((analysis) =>
      analysis.application_record_id ? [[analysis.application_record_id, analysis]] : [],
    ),
  );

  return (
    <section className="px-4 pb-16 pt-8 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="cozy-label mb-3 block">Application tracker</span>
            <h2 className="text-2xl font-semibold sm:text-3xl">Follow every reviewed opportunity.</h2>
            <p className="mt-3 text-sm text-muted-foreground">
              {IS_EXTERNAL_PREVIEW ? 'Coverage is evidence-based. Tracker status is read-only in this shared demo.' : 'Coverage is evidence-based and status changes are saved immediately.'}
            </p>
          </div>
          <div className="flex items-end gap-2">
            <label><span className="cozy-label mb-2 block">Candidate</span><select className="cozy-field min-w-56 rounded-lg px-3 py-2.5 text-sm outline-none" value={candidateId} onChange={(event) => { setCandidateId(event.target.value); setActiveCandidateId(event.target.value); }}>{candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.full_name} · {candidate.email ?? 'Candidate profile'}</option>)}</select></label>
            <button aria-label="Refresh applications" className="cozy-button-secondary inline-flex size-10 items-center justify-center rounded-lg" onClick={() => void refresh()} type="button"><RefreshCw className={`size-4 ${isLoading ? 'animate-spin' : ''}`} /></button>
          </div>
        </div>

        {errorMessage && <div className="mt-5 flex items-start gap-2 rounded-lg border border-destructive/35 bg-destructive/5 px-4 py-3 text-sm text-destructive" role="alert"><AlertCircle className="mt-0.5 size-4" />{errorMessage}</div>}

        <div className="cozy-panel mt-7 overflow-hidden rounded-lg">
          {isLoading ? (
            <div className="flex min-h-52 items-center justify-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading applications</div>
          ) : !candidateId ? (
            <EmptyState message="Create a candidate profile in Analysis before tracking applications." />
          ) : applications.length === 0 ? (
            <EmptyState message="No applications yet. Complete an evidence analysis to save the first one." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] border-collapse text-left text-sm">
                <thead className="border-b border-border bg-secondary/55 text-xs text-muted-foreground"><tr><th className="px-5 py-3 font-medium">Role</th><th className="px-5 py-3 font-medium">Company</th><th className="px-5 py-3 font-medium">Saved / applied</th><th className="px-5 py-3 font-medium">Evidence coverage</th><th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Actions</th></tr></thead>
                <tbody className="divide-y divide-border">{applications.map((application) => (
                  <tr className="bg-card/75" key={application.id}>
                    <td className="px-5 py-4 font-medium">{application.role_title}</td>
                    <td className="px-5 py-4 text-muted-foreground">{application.company_name}</td>
                    <td className="px-5 py-4 text-muted-foreground">{formatDate(application.applied_at ?? application.created_at)}</td>
                    <td className="px-5 py-4"><span className="font-semibold text-primary">{application.evidence_coverage_score === null ? 'Not scored' : `${Number(application.evidence_coverage_score).toFixed(1)}%`}</span></td>
                    <td className="px-5 py-4"><div className="flex items-center gap-2"><select aria-label={`Status for ${application.role_title} at ${application.company_name}`} className="cozy-field rounded-md px-2.5 py-2 text-sm outline-none" disabled={IS_EXTERNAL_PREVIEW || updatingId === application.id} title={IS_EXTERNAL_PREVIEW ? 'Status updates are disabled in the shared demo.' : undefined} value={application.status === 'not_applied' ? 'saved' : application.status} onChange={(event) => void changeStatus(application, event.target.value as ApplicationStatus)}>{STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>{updatingId === application.id && <LoaderCircle className="size-4 animate-spin text-primary" />}</div></td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1">
                        {application.job_url && (
                          <a aria-label={`Open job posting for ${application.role_title}`} className="cozy-button-secondary inline-flex size-9 items-center justify-center rounded-md" href={application.job_url} rel="noreferrer" target="_blank"><ExternalLink className="size-4" /></a>
                        )}
                        <button
                          aria-label={`View analysis for ${application.role_title} at ${application.company_name}`}
                          className="cozy-button-secondary inline-flex size-9 items-center justify-center rounded-md"
                          onClick={() => {
                            const analysis = analysisByApplicationId.get(application.id);
                            if (!analysis) {
                              setErrorMessage('The complete analysis is not available for this older application record.');
                              return;
                            }
                            setErrorMessage('');
                            setActiveCandidateId(analysis.candidate_profile_id);
                            onViewAnalysis({
                              analysisId: analysis.id,
                              candidateProfileId: analysis.candidate_profile_id,
                            });
                          }}
                          type="button"
                        ><FileSearch className="size-4" /></button>
                      </div>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </section>
  );
}

function EmptyState({message}: {message: string}) {
  return <div className="flex min-h-52 flex-col items-center justify-center px-6 text-center"><BriefcaseBusiness className="size-7 text-primary" /><p className="mt-3 max-w-md text-sm text-muted-foreground">{message}</p></div>;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {dateStyle: 'medium'}).format(new Date(value));
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

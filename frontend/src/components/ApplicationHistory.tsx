import {useEffect, useState} from 'react';
import {Download, FileText, LoaderCircle} from 'lucide-react';

import {DataState} from './DataState';
import {
  ApiError,
  downloadGeneratedDocument,
  listResumeHistory,
  ResumeHistoryEntry,
} from '../lib/api';

export function ApplicationHistory({
  candidateProfileId,
  refreshToken,
}: {
  candidateProfileId: string;
  refreshToken?: string;
}) {
  const [entries, setEntries] = useState<ResumeHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let active = true;
    async function loadHistory() {
      if (!candidateProfileId) {
        setEntries([]);
        return;
      }
      setIsLoading(true);
      setErrorMessage('');
      try {
        const history = await listResumeHistory(candidateProfileId);
        if (active) setEntries(history);
      } catch (error) {
        if (active) {
          setErrorMessage(
            error instanceof ApiError ? error.message : 'Resume history could not be loaded.',
          );
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadHistory();
    return () => {
      active = false;
    };
  }, [candidateProfileId, refreshToken]);

  async function handleDownload(documentId: string) {
    setDownloadingId(documentId);
    setErrorMessage('');
    try {
      await downloadGeneratedDocument(documentId);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'The resume download failed.');
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <section className="mt-8 border-t border-border/45 pt-6" aria-labelledby="resume-history-heading">
      <div className="flex items-center gap-2">
        <FileText className="size-4 text-brand-amber" />
        <h3 id="resume-history-heading" className="text-lg font-semibold text-foreground">
          Resume history
        </h3>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        Previously generated resumes are kept here for download.
      </p>
      {errorMessage && <DataState state="error" message={errorMessage} />}
      {isLoading ? (
        <DataState state="loading" message="Loading resume history..." />
      ) : entries.length ? (
        <ol className="mt-4 space-y-3">
          {entries.map((entry) => (
            <li
              key={entry.id}
              aria-label={`${entry.role_title} at ${entry.company_name || 'Unknown company'}`}
              className="cozy-panel-soft flex flex-wrap items-center justify-between gap-4 rounded-lg p-4"
            >
              <div>
                <p className="text-sm font-semibold text-foreground">{entry.role_title}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {entry.company_name || 'Unknown company'} · {entry.output_format.toUpperCase()}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleDownload(entry.id)}
                disabled={downloadingId === entry.id}
                className="cozy-button-secondary inline-flex min-h-10 items-center gap-2 rounded-lg px-4 text-sm font-medium transition disabled:opacity-60"
              >
                {downloadingId === entry.id ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
                {downloadingId === entry.id ? 'Preparing download' : 'Download historical resume'}
              </button>
            </li>
          ))}
        </ol>
      ) : candidateProfileId ? (
        <DataState state="empty" message="No generated resumes yet." />
      ) : (
        <DataState state="empty" message="No profile selected yet, so there is no resume history to show." />
      )}
    </section>
  );
}

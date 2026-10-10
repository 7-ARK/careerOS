/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import {ReactNode, useEffect, useState} from 'react';
import {BriefcaseBusiness, FileSearch, LoaderCircle} from 'lucide-react';
import { Header } from './components/Header';
import { AnalyzeJob } from './components/AnalyzeJob';
import {ApplicationDashboard} from './components/ApplicationDashboard';
import {AuthScreen} from './components/AuthScreen';
import {
  AUTH_EXPIRED_EVENT,
  ApiError,
  User,
  clearAccessToken,
  getAccessToken,
  getCurrentUser,
} from './lib/api';

interface AnalysisSelection {
  analysisId: string;
  candidateProfileId: string;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [authMessage, setAuthMessage] = useState('');
  const [workspace, setWorkspace] = useState<'analysis' | 'applications'>('analysis');
  const [analysisSelection, setAnalysisSelection] = useState<AnalysisSelection | null>(null);

  useEffect(() => {
    async function restoreSession() {
      if (!getAccessToken()) {
        setIsCheckingAuth(false);
        return;
      }
      try {
        setUser(await getCurrentUser());
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          setAuthMessage('Your session expired. Please log in again.');
        }
      } finally {
        setIsCheckingAuth(false);
      }
    }
    void restoreSession();
  }, []);

  useEffect(() => {
    function handleExpiredSession() {
      setUser(null);
      setAuthMessage('Your session expired. Please log in again.');
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpiredSession);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpiredSession);
  }, []);

  if (isCheckingAuth) {
    return <main className="flex min-h-screen items-center justify-center bg-background text-primary"><LoaderCircle className="size-6 animate-spin" /></main>;
  }

  if (!user) {
    return (
      <AuthScreen
        message={authMessage}
        onAuthenticated={(authenticatedUser) => {
          setAuthMessage('');
          setUser(authenticatedUser);
        }}
      />
    );
  }

  function logout() {
    clearAccessToken();
    setUser(null);
  }

  return (
    <div className="cozy-shell relative min-h-screen overflow-hidden bg-background text-foreground font-sans antialiased selection:bg-primary/25 selection:text-foreground">
      <Header user={user} onLogout={logout} />
      <main className="relative" id="main-content-layout">
        <nav aria-label="Workspace views" className="border-b border-border/70 bg-card/55 px-4 sm:px-6">
          <div className="mx-auto flex max-w-6xl gap-1 py-2">
            <WorkspaceTab active={workspace === 'analysis'} icon={<FileSearch className="size-4" />} label="Analysis" onClick={() => setWorkspace('analysis')} />
            <WorkspaceTab active={workspace === 'applications'} icon={<BriefcaseBusiness className="size-4" />} label="Applications" onClick={() => setWorkspace('applications')} />
          </div>
        </nav>
        {workspace === 'analysis' ? (
          <AnalyzeJob analysisSelection={analysisSelection} />
        ) : (
          <ApplicationDashboard
            onViewAnalysis={(selection) => {
              setAnalysisSelection(selection);
              setWorkspace('analysis');
            }}
          />
        )}
      </main>
    </div>
  );
}

function WorkspaceTab({active, icon, label, onClick}: {active: boolean; icon: ReactNode; label: string; onClick: () => void}) {
  return <button aria-current={active ? 'page' : undefined} className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'}`} onClick={onClick} type="button">{icon}{label}</button>;
}

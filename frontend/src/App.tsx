/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import {useEffect, useState} from 'react';
import {LoaderCircle} from 'lucide-react';
import { Header } from './components/Header';
import { AnalyzeJob } from './components/AnalyzeJob';
import {AuthScreen} from './components/AuthScreen';
import {
  AUTH_EXPIRED_EVENT,
  ApiError,
  User,
  clearAccessToken,
  getAccessToken,
  getCurrentUser,
} from './lib/api';

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [authMessage, setAuthMessage] = useState('');

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
        <AnalyzeJob />
      </main>
    </div>
  );
}

import {FormEvent, useState} from 'react';
import {LoaderCircle, LogIn, UserPlus} from 'lucide-react';
import {ApiError, User, loginUser, registerUser} from '../lib/api';

const IS_EXTERNAL_PREVIEW = import.meta.env.VITE_PREVIEW_MODE === 'true';

export function AuthScreen({
  message = '',
  onAuthenticated,
}: {
  message?: string;
  onAuthenticated: (user: User) => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState(IS_EXTERNAL_PREVIEW ? 'demo@careeros.local' : '');
  const [password, setPassword] = useState(IS_EXTERNAL_PREVIEW ? 'password123' : '');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setErrorMessage('');
    try {
      const response = mode === 'login'
        ? await loginUser({email: email.trim(), password})
        : await registerUser({
            email: email.trim(),
            password,
            ...(fullName.trim() ? {full_name: fullName.trim()} : {}),
          });
      onAuthenticated(response.user);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'Authentication failed.');
    } finally {
      setIsLoading(false);
    }
  }

  function switchMode(nextMode: 'login' | 'register') {
    setMode(nextMode);
    setErrorMessage('');
  }

  return (
    <main className="cozy-shell flex min-h-screen items-center justify-center bg-background px-6 py-16 text-foreground">
      <section className="cozy-panel w-full max-w-md rounded-xl p-7 sm:p-8">
        <a href="/" className="text-2xl font-semibold">career<span className="text-primary">OS</span></a>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Sign in to manage candidate profiles and resume runs.
        </p>
        {message && <p className="mt-4 text-sm text-brand-amber">{message}</p>}

        <div className="cozy-panel-soft mt-8 inline-flex rounded-xl p-1">
          <ModeButton active={mode === 'login'} label="Login" onClick={() => switchMode('login')} />
          {!IS_EXTERNAL_PREVIEW && (
            <ModeButton active={mode === 'register'} label="Register" onClick={() => switchMode('register')} />
          )}
        </div>

        <form className="mt-7 space-y-5" onSubmit={handleSubmit}>
          {mode === 'register' && (
            <AuthField label="Full name" value={fullName} onChange={setFullName} autoComplete="name" />
          )}
          <AuthField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" required />
          <AuthField label="Password" type="password" value={password} onChange={setPassword} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : 1} required />
          {mode === 'register' && <p className="text-xs text-muted-foreground">Use at least 8 characters.</p>}
          {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
          <button type="submit" disabled={isLoading} className="cozy-button inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-6 text-sm font-semibold transition disabled:opacity-60">
            {isLoading ? <LoaderCircle className="size-4 animate-spin" /> : mode === 'login' ? <LogIn className="size-4" /> : <UserPlus className="size-4" />}
            {isLoading ? 'Please wait' : mode === 'login' ? 'Login' : 'Create account'}
          </button>
        </form>
      </section>
    </main>
  );
}

function ModeButton({active, label, onClick}: {active: boolean; label: string; onClick: () => void}) {
  return <button type="button" onClick={onClick} className={`rounded-lg px-5 py-2 text-sm transition ${active ? 'cozy-button font-semibold' : 'text-muted-foreground hover:bg-secondary/70 hover:text-foreground'}`}>{label}</button>;
}

function AuthField({label, value, onChange, type = 'text', autoComplete, minLength, required = false}: {label: string; value: string; onChange: (value: string) => void; type?: string; autoComplete: string; minLength?: number; required?: boolean}) {
  return <label className="block"><span className="cozy-label mb-2 block">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} autoComplete={autoComplete} minLength={minLength} required={required} className="cozy-field w-full rounded-lg px-4 py-3 text-sm text-foreground outline-none transition" /></label>;
}

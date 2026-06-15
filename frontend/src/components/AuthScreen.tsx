import {FormEvent, useState} from 'react';
import {LoaderCircle, LogIn, UserPlus} from 'lucide-react';
import {ApiError, User, loginUser, registerUser} from '../lib/api';

export function AuthScreen({
  message = '',
  onAuthenticated,
}: {
  message?: string;
  onAuthenticated: (user: User) => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-16 text-foreground">
      <section className="w-full max-w-md">
        <a href="/" className="font-serif text-2xl font-semibold">career<span className="text-primary">OS</span></a>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Sign in to manage your private candidate profile and tailor resumes.
        </p>
        {message && <p className="mt-4 text-sm text-brand-amber">{message}</p>}

        <div className="mt-8 inline-flex rounded-full border border-border bg-card p-1">
          <ModeButton active={mode === 'login'} label="Login" onClick={() => switchMode('login')} />
          <ModeButton active={mode === 'register'} label="Register" onClick={() => switchMode('register')} />
        </div>

        <form className="mt-7 space-y-5" onSubmit={handleSubmit}>
          {mode === 'register' && (
            <AuthField label="Full name" value={fullName} onChange={setFullName} autoComplete="name" />
          )}
          <AuthField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" required />
          <AuthField label="Password" type="password" value={password} onChange={setPassword} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : 1} required />
          {mode === 'register' && <p className="text-xs text-muted-foreground">Use at least 8 characters.</p>}
          {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
          <button type="submit" disabled={isLoading} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground transition hover:brightness-110 disabled:opacity-60">
            {isLoading ? <LoaderCircle className="size-4 animate-spin" /> : mode === 'login' ? <LogIn className="size-4" /> : <UserPlus className="size-4" />}
            {isLoading ? 'Please wait' : mode === 'login' ? 'Login' : 'Create account'}
          </button>
        </form>
      </section>
    </main>
  );
}

function ModeButton({active, label, onClick}: {active: boolean; label: string; onClick: () => void}) {
  return <button type="button" onClick={onClick} className={`rounded-full px-5 py-2 text-sm transition ${active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>{label}</button>;
}

function AuthField({label, value, onChange, type = 'text', autoComplete, minLength, required = false}: {label: string; value: string; onChange: (value: string) => void; type?: string; autoComplete: string; minLength?: number; required?: boolean}) {
  return <label className="block"><span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} autoComplete={autoComplete} minLength={minLength} required={required} className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20" /></label>;
}

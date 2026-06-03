import { useState, type FormEvent } from 'react';
import { PanelHeader } from '../ui';

type Props = {
  alias: string;
  onAliasChange: (value: string) => void;
  onRegister: (alias: string, password: string, adminCode?: string) => Promise<void>;
  onLogin: (alias: string, password: string, adminCode?: string) => Promise<void>;
  loading: boolean;
  error: string;
};

type AuthMode = 'login' | 'register';

export default function AuthView({ alias, onAliasChange, onRegister, onLogin, loading, error }: Props) {
  const [mode, setMode] = useState<AuthMode>('login');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [adminCode, setAdminCode] = useState('');
  const [wantsAdminAccess, setWantsAdminAccess] = useState(false);
  const [localError, setLocalError] = useState('');

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLocalError('');
    if (!alias.trim()) {
      setLocalError('Alias is required.');
      return;
    }
    if (!password) {
      setLocalError('Password is required.');
      return;
    }
    if (mode === 'register' && password !== confirmPassword) {
      setLocalError('Passwords do not match.');
      return;
    }
    try {
      if (mode === 'register') {
        await onRegister(alias.trim(), password, wantsAdminAccess ? adminCode : undefined);
      } else {
        await onLogin(alias.trim(), password, wantsAdminAccess ? adminCode : undefined);
      }
    } catch {
      return;
    }
    setPassword('');
    setConfirmPassword('');
    setAdminCode('');
  }

  return (
    <main className="auth-shell">
      <section className="auth-card rail-panel">
        <PanelHeader
          eyebrow="Authentication"
          title="Register or sign in"
          subtitle="Create a player account with an alias and password. Reserved admin aliases also require the configured secret code."
        />

        <div className="auth-mode-row">
          <button
            type="button"
            className={mode === 'login' ? 'dossier-button dossier-button-accent' : 'dossier-button dossier-button-ghost'}
            onClick={() => setMode('login')}
          >
            Login
          </button>
          <button
            type="button"
            className={mode === 'register' ? 'dossier-button dossier-button-accent' : 'dossier-button dossier-button-ghost'}
            onClick={() => setMode('register')}
          >
            Register
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Alias
            <input value={alias} onChange={(event) => onAliasChange(event.target.value)} placeholder="Detective alias" />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 6 characters" />
          </label>
          {mode === 'register' ? (
            <label>
              Confirm Password
              <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Repeat password" />
            </label>
          ) : null}

          <label className="auth-toggle">
            <input
              type="checkbox"
              checked={wantsAdminAccess}
              onChange={(event) => setWantsAdminAccess(event.target.checked)}
            />
            Request admin access
          </label>

          {wantsAdminAccess ? (
            <label>
              Admin Secret Code
              <input
                type="password"
                value={adminCode}
                onChange={(event) => setAdminCode(event.target.value)}
                placeholder="Configured on the backend"
              />
            </label>
          ) : null}

          {(localError || error) ? <div className="error-banner">{localError || error}</div> : null}

          <button className="dossier-button dossier-button-accent" type="submit" disabled={loading}>
            {loading ? 'Working...' : mode === 'register' ? 'Create Account' : 'Sign In'}
          </button>
        </form>
      </section>
    </main>
  );
}

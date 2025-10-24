/**
 * AuthModal Component
 * Handles user authentication via workspace codes
 * Users can either enter an existing code or generate a new one
 */

import { FormEvent, useState } from 'react';

type AuthModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onAuthenticated: (token: string, profileId: string) => void;
  apiBaseUrl: string;
  authError: string | null;
  setAuthError: (error: string | null) => void;
};

export const AuthModal = ({
  isOpen,
  onAuthenticated,
  apiBaseUrl,
  authError,
  setAuthError,
}: AuthModalProps) => {
  const [codeInput, setCodeInput] = useState('');
  const [profileId, setProfileId] = useState<string | null>(null);
  const [isRequestingCode, setIsRequestingCode] = useState(false);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);

  if (!isOpen) return null;

  /**
   * Requests a new workspace code from the server
   */
  const handleRequestCode = async () => {
    if (isRequestingCode) return;

    setIsRequestingCode(true);
    setAuthError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/request-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profileId }),
      });

      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Unable to generate code');
      }

      const data: { code: string; profileId: string; expiresAt: number } = await response.json();
      setProfileId(data.profileId);
      setCodeInput(data.code);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error requesting code';
      setAuthError(message);
    } finally {
      setIsRequestingCode(false);
    }
  };

  /**
   * Verifies the entered workspace code and authenticates the user
   */
  const handleVerifyCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmed = codeInput.trim();
    if (!trimmed) {
      setAuthError('Enter the one-time code you received.');
      return;
    }

    setIsVerifyingCode(true);
    setAuthError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: trimmed }),
      });

      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Unable to verify code');
      }

      const data: { token: string; profileId: string; expiresAt: number } = await response.json();
      onAuthenticated(data.token, data.profileId);
      setCodeInput('');
      setAuthError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown verification error';
      setAuthError(message);
    } finally {
      setIsVerifyingCode(false);
    }
  };

  return (
    <section className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4">
      <div className="w-full max-w-md rounded-3xl border border-slate-800/80 bg-slate-900/90 p-6 shadow-2xl shadow-emerald-500/20">
        <header className="mb-4 flex flex-col gap-1">
          <h2 className="text-xl font-semibold text-emerald-300">Access your workspace</h2>
          <p className="text-sm text-slate-400">
            Enter your 6-character workspace code to access your conversations and files. Don't have one? Generate a
            new code to create your workspace.
          </p>
        </header>

        <form className="flex flex-col gap-4" onSubmit={handleVerifyCode}>
          <label className="text-xs font-medium uppercase tracking-[0.3em] text-slate-500" htmlFor="access-code">
            Workspace Code
          </label>
          <input
            id="access-code"
            type="text"
            inputMode="text"
            autoComplete="off"
            maxLength={6}
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm tracking-[0.4em] text-slate-100 placeholder:text-slate-500 focus:border-emerald-400 focus:outline-none uppercase"
            placeholder="ABC123"
            value={codeInput}
            onChange={(event) => setCodeInput(event.target.value.toUpperCase())}
          />

          <button
            type="submit"
            disabled={isVerifyingCode}
            className="flex h-11 items-center justify-center rounded-xl bg-emerald-500 font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
          >
            {isVerifyingCode ? 'Accessing workspace…' : 'Access workspace'}
          </button>

          <button
            type="button"
            onClick={handleRequestCode}
            disabled={isRequestingCode}
            className="h-11 rounded-xl border border-emerald-400/60 text-sm font-semibold text-emerald-200 transition hover:border-emerald-300 hover:text-emerald-100 disabled:opacity-60"
          >
            {isRequestingCode ? 'Creating workspace…' : 'Create new workspace'}
          </button>

          {authError && (
            <p className="rounded-xl border border-rose-600/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">
              {authError}
            </p>
          )}

          <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-3">
            <p className="text-xs text-slate-400">
              💡 <strong className="text-slate-300">Tip:</strong> Your workspace code is like a password. Save it
              somewhere safe! You'll need it to access this workspace from another device.
            </p>
          </div>
        </form>
      </div>
    </section>
  );
};

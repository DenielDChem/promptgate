// Pre-desktop auth surface: a centered terminal "panel" hosting Login,
// Request-Invite, and Register-by-Invite forms. Chooses the initial form from
// the URL (?invite= / #/register).

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { PixelButton } from '@/components/PixelButton';
import { PixelField, PixelTextArea } from '@/components/PixelField';
import { readInviteToken, isRegisterRoute, clearAuthUrl } from '@/lib/route';

type Mode = 'login' | 'invite' | 'register';

export function AuthGate() {
  const inviteToken = readInviteToken();
  const initialMode: Mode = inviteToken || isRegisterRoute() ? 'register' : 'login';
  const [mode, setMode] = useState<Mode>(initialMode);

  const clearError = useAuthStore((s) => s.clearError);
  useEffect(() => {
    clearError();
  }, [mode, clearError]);

  return (
    <div className="scanlines noise desktop-grid flex h-full w-full items-center justify-center bg-bg p-4">
      <div className="pixel-raised w-full max-w-sm rounded-pixel-lg border border-border bg-card">
        {/* Title bar */}
        <div className="flex items-center gap-2 rounded-t-pixel-lg bg-gradient-to-r from-violet to-violet-deep px-3 py-1.5">
          <span className="text-neon">▣</span>
          <span className="font-mono text-xs font-bold uppercase tracking-widest text-white">
            PromptGate
          </span>
          <span className="caret ml-auto font-mono text-xs text-white/70" />
        </div>

        <div className="p-5">
          <h1 className="mb-4 font-mono text-sm uppercase tracking-widest text-neon-dim terminal-print">
            {mode === 'login' && '> authenticate'}
            {mode === 'invite' && '> request_invite'}
            {mode === 'register' && '> register'}
          </h1>

          {mode === 'login' && <LoginForm />}
          {mode === 'invite' && <InviteForm />}
          {mode === 'register' && <RegisterForm inviteToken={inviteToken} />}

          <ModeSwitch mode={mode} setMode={setMode} hasInvite={!!inviteToken} />
        </div>
      </div>
    </div>
  );
}

function ErrorLine() {
  const error = useAuthStore((s) => s.error);
  if (!error) return null;
  return (
    <p
      role="alert"
      className="mt-3 rounded-pixel border border-red bg-red/10 px-2 py-1 font-mono text-xs text-red"
    >
      ! {error}
    </p>
  );
}

function LoginForm() {
  const login = useAuthStore((s) => s.login);
  const busy = useAuthStore((s) => s.busy);
  const error = useAuthStore((s) => s.error);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        const ok = await login({ username, password });
        if (ok) clearAuthUrl();
      }}
    >
      <PixelField
        label="Username"
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        aria-invalid={!!error || undefined}
        required
        autoFocus
      />
      <PixelField
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        aria-invalid={!!error || undefined}
        required
      />
      <ErrorLine />
      <PixelButton type="submit" variant="primary" disabled={busy}>
        {busy ? 'Authenticating…' : 'Log in'}
      </PixelButton>
    </form>
  );
}

function InviteForm() {
  const requestInvite = useAuthStore((s) => s.requestInvite);
  const busy = useAuthStore((s) => s.busy);
  const [email, setEmail] = useState('');
  const [reason, setReason] = useState('');
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <div className="rounded-pixel border border-neon-dim bg-neon/10 p-3 text-center font-mono text-sm text-neon terminal-print">
        ✓ Request submitted.
        <span className="mt-1 block text-xs text-ink-dim">
          Pending admin approval.
        </span>
      </div>
    );
  }

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        const ok = await requestInvite({ email, reason });
        if (ok) setSent(true);
      }}
    >
      <PixelField
        label="Email"
        type="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoFocus
      />
      <PixelTextArea
        label="Reason"
        rows={3}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Why do you need access?"
        required
      />
      <ErrorLine />
      <PixelButton type="submit" variant="action" disabled={busy}>
        {busy ? 'Sending…' : 'Request invite'}
      </PixelButton>
    </form>
  );
}

function RegisterForm({ inviteToken }: { inviteToken: string | null }) {
  const register = useAuthStore((s) => s.register);
  const busy = useAuthStore((s) => s.busy);
  const [token, setToken] = useState(inviteToken ?? '');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        const ok = await register({
          invite_token: token,
          username,
          email,
          password,
        });
        if (ok) clearAuthUrl();
      }}
    >
      <PixelField
        label="Invite token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        required
        readOnly={!!inviteToken}
        autoFocus={!inviteToken}
      />
      <PixelField
        label="Username"
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
        autoFocus={!!inviteToken}
      />
      <PixelField
        label="Email"
        type="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <PixelField
        label="Password"
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <ErrorLine />
      <PixelButton type="submit" variant="primary" disabled={busy}>
        {busy ? 'Creating…' : 'Create account'}
      </PixelButton>
    </form>
  );
}

function ModeSwitch({
  mode,
  setMode,
  hasInvite,
}: {
  mode: Mode;
  setMode: (m: Mode) => void;
  hasInvite: boolean;
}) {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-t border-border pt-3 font-mono text-[11px] text-ink-dim">
      {mode !== 'login' && (
        <button className="hover:text-neon" onClick={() => setMode('login')}>
          → log in
        </button>
      )}
      {mode !== 'invite' && (
        <button className="hover:text-neon" onClick={() => setMode('invite')}>
          → request invite
        </button>
      )}
      {mode !== 'register' && (
        <button className="hover:text-neon" onClick={() => setMode('register')}>
          → {hasInvite ? 'register' : 'have a token?'}
        </button>
      )}
    </div>
  );
}

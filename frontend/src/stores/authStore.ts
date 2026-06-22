// Auth store — holds JWT + user, persists the token in localStorage.
// Boot flow: if a token exists, hydrate() calls /api/auth/me to validate it.

import { create } from 'zustand';
import { authApi, ApiError } from '@/api/client';
import type {
  LoginPayload,
  RegisterPayload,
  RequestInvitePayload,
} from '@/api/client';
import type { User } from '@/lib/types';

const TOKEN_KEY = 'pg.token';

type AuthStatus = 'booting' | 'anonymous' | 'authenticated';

interface AuthState {
  status: AuthStatus;
  token: string | null;
  user: User | null;
  error: string | null;
  busy: boolean;

  hydrate: () => Promise<void>;
  login: (payload: LoginPayload) => Promise<boolean>;
  register: (payload: RegisterPayload) => Promise<boolean>;
  requestInvite: (payload: RequestInvitePayload) => Promise<boolean>;
  logout: () => Promise<void>;
  clearError: () => void;
}

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage may be unavailable (private mode) — auth still works in-memory */
  }
}

function messageOf(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return 'Unexpected error';
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: 'booting',
  token: readToken(),
  user: null,
  error: null,
  busy: false,

  hydrate: async () => {
    const token = get().token;
    if (!token) {
      set({ status: 'anonymous' });
      return;
    }
    try {
      const user = await authApi.me(token);
      set({ user, status: 'authenticated', error: null });
    } catch {
      writeToken(null);
      set({ token: null, user: null, status: 'anonymous' });
    }
  },

  login: async (payload) => {
    set({ busy: true, error: null });
    try {
      const { access_token, user } = await authApi.login(payload);
      writeToken(access_token);
      set({ token: access_token, user, status: 'authenticated', busy: false });
      return true;
    } catch (err) {
      set({ error: messageOf(err), busy: false });
      return false;
    }
  },

  register: async (payload) => {
    set({ busy: true, error: null });
    try {
      const { access_token, user } = await authApi.register(payload);
      writeToken(access_token);
      set({ token: access_token, user, status: 'authenticated', busy: false });
      return true;
    } catch (err) {
      set({ error: messageOf(err), busy: false });
      return false;
    }
  },

  requestInvite: async (payload) => {
    set({ busy: true, error: null });
    try {
      await authApi.requestInvite(payload);
      set({ busy: false });
      return true;
    } catch (err) {
      set({ error: messageOf(err), busy: false });
      return false;
    }
  },

  logout: async () => {
    const token = get().token;
    if (token) {
      // Best-effort; clear local state regardless of server response.
      try {
        await authApi.logout(token);
      } catch {
        /* ignore */
      }
    }
    writeToken(null);
    set({ token: null, user: null, status: 'anonymous', error: null });
  },

  clearError: () => set({ error: null }),
}));

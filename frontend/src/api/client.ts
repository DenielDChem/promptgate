// Thin fetch wrapper around the PromptGate backend auth contract.
// VITE_API_BASE defaults to '' so requests hit same-origin /api (FastAPI serves dist/).

import type { AuthSuccess, User } from '@/lib/types';

const API_BASE: string = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string | null;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.token) headers['Authorization'] = `Bearer ${opts.token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api${path}`, {
      method: opts.method ?? 'GET',
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Network error — backend unreachable');
  }

  if (!res.ok) {
    const detail = await extractError(res);
    throw new ApiError(res.status, detail);
  }

  // 204 / empty bodies
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

async function extractError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string; message?: string };
    return data.detail ?? data.message ?? `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface RegisterPayload {
  invite_token: string;
  username: string;
  email: string;
  password: string;
}

export interface RequestInvitePayload {
  email: string;
  reason: string;
}

export const authApi = {
  login: (payload: LoginPayload) =>
    request<AuthSuccess>('/auth/login', { method: 'POST', body: payload }),

  register: (payload: RegisterPayload) =>
    request<AuthSuccess>('/auth/register', { method: 'POST', body: payload }),

  requestInvite: (payload: RequestInvitePayload) =>
    request<{ status: string }>('/auth/request-invite', {
      method: 'POST',
      body: payload,
    }),

  me: (token: string) => request<User>('/auth/me', { token }),

  logout: (token: string) =>
    request<{ ok: boolean }>('/auth/logout', { method: 'POST', token }),
};

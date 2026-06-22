// Thin fetch wrapper around the PromptGate backend auth contract.
// VITE_API_BASE defaults to '' so requests hit same-origin /api (FastAPI serves dist/).

import type {
  AuthSuccess,
  JobCreatePayload,
  JobDetail,
  JobStatus,
  JobSummary,
  JobSummaryCounts,
  LintResult,
  PromptConfig,
  PromptSavePayload,
  PromptSummary,
  PromptVersion,
  QualityRow,
  QualityScore,
  User,
  ValidatePayload,
  ValidationRun,
  ValidationRunSummary,
} from '@/lib/types';

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

// ─── Prompts + versioning (P2) ───────────────────────────────────────────────

export interface SaveResult {
  ok: boolean;
  id: string;
  version: number;
}

export interface RollbackResult {
  ok: boolean;
  version: number;
}

export const promptsApi = {
  list: (token: string) => request<PromptSummary[]>('/prompts', { token }),

  get: (id: string, token: string) =>
    request<PromptConfig>(`/prompts/${encodeURIComponent(id)}`, { token }),

  save: (payload: PromptSavePayload, token: string) =>
    request<SaveResult>('/prompts', { method: 'POST', body: payload, token }),

  remove: (id: string, token: string) =>
    request<{ ok: boolean }>(`/prompts/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      token,
    }),

  versions: (id: string, token: string) =>
    request<PromptVersion[]>(`/prompts/${encodeURIComponent(id)}/versions`, {
      token,
    }),

  version: (id: string, n: number, token: string) =>
    request<PromptConfig>(
      `/prompts/${encodeURIComponent(id)}/versions/${n}`,
      { token },
    ),

  rollback: (id: string, version_no: number, token: string) =>
    request<RollbackResult>(`/prompts/${encodeURIComponent(id)}/rollback`, {
      method: 'POST',
      body: { version_no },
      token,
    }),
};

// ─── Live validation (P2 §4) ──────────────────────────────────────────────────

export const lintApi = {
  check: (template: string, token: string) =>
    request<LintResult>('/lint', { method: 'POST', body: { template }, token }),
};

// ─── Deep validation + quality (P3 §4, §8) ───────────────────────────────────

export const validationApi = {
  /** Available models for the picker. */
  models: (token: string) => request<string[]>('/models', { token }),

  /** Kick off a deep validation run for a prompt. May take a while. */
  run: (id: string, payload: ValidatePayload, token: string) =>
    request<ValidationRun>(`/prompts/${encodeURIComponent(id)}/validate`, {
      method: 'POST',
      body: payload,
      token,
    }),

  /** Aggregate quality for one prompt (404 → never validated). */
  quality: (id: string, token: string) =>
    request<QualityScore>(`/prompts/${encodeURIComponent(id)}/quality`, { token }),

  /** Past validation runs for one prompt (newest first). */
  runs: (id: string, token: string) =>
    request<ValidationRunSummary[]>(
      `/prompts/${encodeURIComponent(id)}/validations`,
      { token },
    ),

  /** Full run incl. graded cases. */
  runDetail: (runId: string, token: string) =>
    request<ValidationRun>(`/validations/${encodeURIComponent(runId)}`, { token }),

  /** Quality dashboard across the caller's prompts. */
  dashboard: (token: string) => request<QualityRow[]>('/quality', { token }),
};

// ─── Task queue (P4 §6, §9) — admin-only; non-admins get 403 ─────────────────

export interface CancelResult {
  ok: boolean;
  status: JobStatus;
}

export const jobsApi = {
  /** Enqueue a job. Returns the freshly-created summary (status: queued). */
  create: (payload: JobCreatePayload, token: string) =>
    request<JobSummary>('/jobs', { method: 'POST', body: payload, token }),

  /** All jobs (newest first); optional status filter. */
  list: (token: string, status?: JobStatus) =>
    request<JobSummary[]>(`/jobs${status ? `?status=${encodeURIComponent(status)}` : ''}`, {
      token,
    }),

  /** Full job incl. result / error. */
  get: (id: string, token: string) =>
    request<JobDetail>(`/jobs/${encodeURIComponent(id)}`, { token }),

  /** Cancel a queued/running job; no-op (may 409) once terminal. */
  cancel: (id: string, token: string) =>
    request<CancelResult>(`/jobs/${encodeURIComponent(id)}/cancel`, {
      method: 'POST',
      token,
    }),

  /** Per-status counts for the status bar. */
  summary: (token: string) => request<JobSummaryCounts>('/jobs/summary', { token }),
};

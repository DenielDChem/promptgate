// Task-queue store (P4) — owns the live jobs table, the per-status summary
// counts, the create-job form lookups, and a single selected job's detail.
//
// Mirrors validatorStore conventions: the JWT is pulled from the auth store at
// call time and auto-attached by the api client; all failures surface as a
// string in an `*Error` field rather than throwing into React.
//
// Polling lifecycle: `startPolling` refreshes the list + summary immediately,
// then on an interval; `stopPolling` clears it. The Queue window mounts/unmounts
// these so we never poll while the window is closed (spec §9.3).

import { createContext, useContext } from 'react';
import { createStore } from 'zustand/vanilla';
import { useStore } from 'zustand';
import { ApiError, jobsApi, promptsApi, validationApi } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import type {
  JobCreatePayload,
  JobDetail,
  JobPriority,
  JobSummary,
  JobSummaryCounts,
  JobType,
  PromptSummary,
} from '@/lib/types';

/** How often the open Queue window re-fetches jobs + summary (spec: ~2s). */
const POLL_MS = 2000;

const EMPTY_COUNTS: JobSummaryCounts = {
  queued: 0,
  running: 0,
  completed: 0,
  failed: 0,
  cancelled: 0,
  total: 0,
};

interface JobsState {
  // ── jobs table + summary ──
  jobs: JobSummary[];
  summary: JobSummaryCounts;
  loading: boolean;
  listError: string | null;

  // ── create-job form lookups ──
  prompts: PromptSummary[];
  models: string[];
  lookupsLoading: boolean;

  // ── create-job submission ──
  creating: boolean;
  createError: string | null;

  // ── selected job detail ──
  detail: JobDetail | null;
  detailLoading: boolean;
  detailError: string | null;

  // ── polling internals (not for components) ──
  _timer: ReturnType<typeof setInterval> | null;

  // actions — lifecycle
  startPolling: () => void;
  stopPolling: () => void;
  refresh: () => Promise<void>;

  // actions — create
  loadLookups: () => Promise<void>;
  create: (payload: JobCreatePayload) => Promise<JobSummary | null>;

  // actions — detail
  viewJob: (id: string) => Promise<void>;
  clearDetail: () => void;

  // actions — cancel
  cancelJob: (id: string) => Promise<void>;
}

function token(): string | null {
  return useAuthStore.getState().token;
}

function messageOf(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return 'Unexpected error';
}

/** Per-window store factory — each Queue window owns its own polling loop and
 *  selected-job detail. */
export function createJobsStore() {
  return createStore<JobsState>((set, get) => ({
  jobs: [],
  summary: EMPTY_COUNTS,
  loading: false,
  listError: null,

  prompts: [],
  models: [],
  lookupsLoading: false,

  creating: false,
  createError: null,

  detail: null,
  detailLoading: false,
  detailError: null,

  _timer: null,

  startPolling: () => {
    // Guard against double-mounts (React StrictMode) leaving a stray interval.
    if (get()._timer) return;
    void get().refresh();
    const timer = setInterval(() => {
      void get().refresh();
    }, POLL_MS);
    set({ _timer: timer });
  },

  stopPolling: () => {
    const t = get()._timer;
    if (t) clearInterval(t);
    set({ _timer: null });
  },

  refresh: async () => {
    const t = token();
    if (!t) return;
    set((s) => ({ loading: s.jobs.length === 0 }));
    try {
      const [jobs, summary] = await Promise.all([
        jobsApi.list(t),
        jobsApi.summary(t),
      ]);
      set({ jobs, summary, loading: false, listError: null });
      // Keep an open detail panel fresh while the job is still in flight.
      const open = get().detail;
      if (open && (open.status === 'queued' || open.status === 'running')) {
        void get().viewJob(open.id);
      }
    } catch (err) {
      set({ listError: messageOf(err), loading: false });
    }
  },

  loadLookups: async () => {
    const t = token();
    if (!t) return;
    set({ lookupsLoading: true });
    try {
      const [prompts, models] = await Promise.all([
        promptsApi.list(t),
        validationApi.models(t),
      ]);
      set({ prompts, models, lookupsLoading: false });
    } catch {
      // Lookups are best-effort; the form still submits with manual defaults.
      set({ lookupsLoading: false });
    }
  },

  create: async (payload) => {
    const t = token();
    if (!t) return null;
    set({ creating: true, createError: null });
    try {
      const job = await jobsApi.create(payload, t);
      set({ creating: false });
      toast.success(`Job ${job.id} queued.`);
      void get().refresh();
      return job;
    } catch (err) {
      set({ createError: messageOf(err), creating: false });
      return null;
    }
  },

  viewJob: async (id) => {
    const t = token();
    if (!t) return;
    set((s) => ({ detailLoading: s.detail?.id !== id, detailError: null }));
    try {
      const detail = await jobsApi.get(id, t);
      set({ detail, detailLoading: false });
    } catch (err) {
      set({ detailError: messageOf(err), detailLoading: false });
    }
  },

  clearDetail: () => set({ detail: null, detailError: null }),

  cancelJob: async (id) => {
    const t = token();
    if (!t) return;
    try {
      await jobsApi.cancel(id, t);
      toast.info(`Cancel requested for ${id}.`);
    } catch (err) {
      // A 409 just means the job already finished — surface other errors only.
      if (!(err instanceof ApiError) || err.status !== 409) {
        const msg = messageOf(err);
        set({ listError: msg });
        toast.error(`Couldn't cancel ${id}: ${msg}`);
      }
    } finally {
      void get().refresh();
      if (get().detail?.id === id) void get().viewJob(id);
    }
  },
  }));
}

export type JobsStoreApi = ReturnType<typeof createJobsStore>;

const JobsStoreContext = createContext<JobsStoreApi | null>(null);
export const JobsStoreProvider = JobsStoreContext.Provider;

export function useJobsStoreApi(): JobsStoreApi {
  const api = useContext(JobsStoreContext);
  if (!api) throw new Error('useJobsStore used outside a window provider');
  return api;
}

export function useJobsStore<T>(selector: (s: JobsState) => T): T {
  return useStore(useJobsStoreApi(), selector);
}

export const JOB_TYPE_LABELS: Record<JobType, string> = {
  validation: 'Validation',
  generation: 'Template generation',
  mass_test: 'Mass test',
};

export const JOB_PRIORITY_LABELS: Record<JobPriority, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

// Validator + Quality store (P3) — owns the deep-validation form (prompt/model
// pick, test-set draft, repeats), the running/result state for a run, the
// per-prompt run history, and the cross-prompt quality dashboard.
//
// Mirrors promptsStore conventions: the JWT is pulled from the auth store at
// call time and auto-attached by the api client; all failures surface as a
// string in an `*Error` field rather than throwing into React.

import { createContext, useContext } from 'react';
import { createStore } from 'zustand/vanilla';
import { useStore } from 'zustand';
import { ApiError, promptsApi, validationApi } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import type {
  PromptSummary,
  QualityRow,
  TestCase,
  ValidationRun,
  ValidationRunSummary,
} from '@/lib/types';

/** Empty rows the test-set editor starts with (spec: default 5 Qs). */
const DEFAULT_CASE_ROWS = 5;
const DEFAULT_REPEATS = 3;

function emptyCases(n: number): TestCase[] {
  return Array.from({ length: n }, () => ({ question: '', payload: '' }));
}

interface ValidatorState {
  // ── shared lookups ──
  prompts: PromptSummary[];
  models: string[];
  lookupsLoading: boolean;
  lookupError: string | null;

  // ── run form ──
  promptId: string;
  modelId: string;
  cases: TestCase[];
  repeats: number;

  // ── run lifecycle ──
  running: boolean;
  result: ValidationRun | null;
  runError: string | null;

  // ── per-prompt history ──
  runs: ValidationRunSummary[];
  runsLoading: boolean;

  // ── quality dashboard ──
  dashboard: QualityRow[];
  dashboardLoading: boolean;
  dashboardError: string | null;

  // actions — form
  loadLookups: () => Promise<void>;
  setPromptId: (id: string) => void;
  setModelId: (id: string) => void;
  setRepeats: (n: number) => void;
  setCase: (index: number, patch: Partial<TestCase>) => void;
  addCase: () => void;
  removeCase: (index: number) => void;

  // actions — run
  run: () => Promise<void>;
  cancelRun: () => void;
  loadRuns: (promptId: string) => Promise<void>;
  viewRun: (runId: string) => Promise<void>;
  clearResult: () => void;

  // actions — dashboard
  loadDashboard: () => Promise<void>;
}

function token(): string | null {
  return useAuthStore.getState().token;
}

function messageOf(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return 'Unexpected error';
}

/** Per-window store factory — each Validator/Quality window owns its own run
 *  lifecycle (and its own abort controller). */
export function createValidatorStore() {
  // Per-instance controller for the in-flight run, so `cancelRun` aborts only
  // this window's run without threading the controller through React state.
  let runController: AbortController | null = null;
  return createStore<ValidatorState>((set, get) => ({
  prompts: [],
  models: [],
  lookupsLoading: false,
  lookupError: null,

  promptId: '',
  modelId: '',
  cases: emptyCases(DEFAULT_CASE_ROWS),
  repeats: DEFAULT_REPEATS,

  running: false,
  result: null,
  runError: null,

  runs: [],
  runsLoading: false,

  dashboard: [],
  dashboardLoading: false,
  dashboardError: null,

  loadLookups: async () => {
    const t = token();
    if (!t) return;
    set({ lookupsLoading: true, lookupError: null });
    try {
      const [prompts, models] = await Promise.all([
        promptsApi.list(t),
        validationApi.models(t),
      ]);
      set((s) => ({
        prompts,
        models,
        lookupsLoading: false,
        // Default the pickers to the first option when unset.
        promptId: s.promptId || prompts[0]?.id || '',
        modelId: s.modelId || models[0] || '',
      }));
    } catch (err) {
      set({ lookupError: messageOf(err), lookupsLoading: false });
    }
  },

  setPromptId: (id) => {
    set({ promptId: id });
    void get().loadRuns(id);
  },
  setModelId: (id) => set({ modelId: id }),
  setRepeats: (n) => set({ repeats: Math.max(1, Math.min(10, Math.round(n) || 1)) }),

  setCase: (index, patch) =>
    set((s) => ({
      cases: s.cases.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    })),

  addCase: () => set((s) => ({ cases: [...s.cases, { question: '', payload: '' }] })),

  removeCase: (index) =>
    set((s) => {
      const next = s.cases.filter((_, i) => i !== index);
      // Always keep at least one row so the editor never collapses to nothing.
      return { cases: next.length ? next : emptyCases(1) };
    }),

  run: async () => {
    const t = token();
    const { promptId, modelId, cases, repeats } = get();
    if (!t) return;
    if (!promptId) {
      set({ runError: 'Pick a prompt to validate' });
      return;
    }
    if (!modelId) {
      set({ runError: 'Pick a model' });
      return;
    }
    // Only send non-empty questions; omit `cases` entirely so the backend falls
    // back to its own default test-set when the user left every row blank.
    const filled = cases
      .map((c) => ({ question: c.question.trim(), payload: c.payload?.trim() || undefined }))
      .filter((c) => c.question.length > 0);

    runController = new AbortController();
    set({ running: true, runError: null, result: null });
    try {
      const result = await validationApi.run(
        promptId,
        {
          model_id: modelId,
          repeats,
          cases: filled.length ? filled : undefined,
        },
        t,
        runController.signal,
      );
      set({ result, running: false });
      toast.success('Validation complete.');
      void get().loadRuns(promptId);
    } catch (err) {
      // A user-initiated cancel is not an error: just stop, no red banner.
      if (err instanceof DOMException && err.name === 'AbortError') {
        set({ running: false });
        toast.info('Validation cancelled.');
      } else {
        set({ runError: messageOf(err), running: false });
      }
    } finally {
      runController = null;
    }
  },

  cancelRun: () => {
    runController?.abort();
  },

  loadRuns: async (promptId) => {
    const t = token();
    if (!t || !promptId) {
      set({ runs: [] });
      return;
    }
    set({ runsLoading: true });
    try {
      const runs = await validationApi.runs(promptId, t);
      set({ runs, runsLoading: false });
    } catch {
      // History is best-effort; never blocks running.
      set({ runs: [], runsLoading: false });
    }
  },

  viewRun: async (runId) => {
    const t = token();
    if (!t) return;
    set({ running: true, runError: null });
    try {
      const result = await validationApi.runDetail(runId, t);
      set({ result, running: false });
    } catch (err) {
      set({ runError: messageOf(err), running: false });
    }
  },

  clearResult: () => set({ result: null, runError: null }),

  loadDashboard: async () => {
    const t = token();
    if (!t) return;
    set({ dashboardLoading: true, dashboardError: null });
    try {
      const dashboard = await validationApi.dashboard(t);
      set({ dashboard, dashboardLoading: false });
    } catch (err) {
      set({ dashboardError: messageOf(err), dashboardLoading: false });
    }
  },
  }));
}

export type ValidatorStoreApi = ReturnType<typeof createValidatorStore>;

const ValidatorStoreContext = createContext<ValidatorStoreApi | null>(null);
export const ValidatorStoreProvider = ValidatorStoreContext.Provider;

export function useValidatorStoreApi(): ValidatorStoreApi {
  const api = useContext(ValidatorStoreContext);
  if (!api) throw new Error('useValidatorStore used outside a window provider');
  return api;
}

export function useValidatorStore<T>(selector: (s: ValidatorState) => T): T {
  return useStore(useValidatorStoreApi(), selector);
}

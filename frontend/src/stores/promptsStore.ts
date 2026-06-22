// Prompts module store (P2) — owns the list view, the open editor draft, the
// version history, and live-lint findings. The `my-prompts` window swaps
// between a list view and the 3-pane editor based on `view`.
//
// The JWT is pulled from the auth store at call time (it's auto-attached as a
// Bearer header by the api client). All network failures surface as a string
// in `error` / `editorError` rather than throwing into React.

import { create } from 'zustand';
import { ApiError, lintApi, promptsApi } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import type {
  LintFinding,
  PromptConfig,
  PromptStatus,
  PromptSummary,
  PromptVersion,
} from '@/lib/types';

type View = 'list' | 'editor';

/** Mutable editor draft — what the inspector/Monaco bind to. */
interface Draft {
  id: string;
  name: string;
  tags: string[];
  template: string;
  schema: string;
  description: string;
  status: PromptStatus;
  current_version: number;
  /** True for a brand-new prompt that has never been saved. */
  isNew: boolean;
}

interface PromptsState {
  view: View;

  // List
  list: PromptSummary[];
  listLoading: boolean;
  error: string | null;

  // Editor
  draft: Draft | null;
  editorLoading: boolean;
  editorError: string | null;
  saving: boolean;
  dirty: boolean;

  // Versioning
  versions: PromptVersion[];
  versionsLoading: boolean;

  // Live lint
  findings: LintFinding[];
  linting: boolean;

  // ── actions ──
  loadList: () => Promise<void>;
  openEditor: (id: string) => Promise<void>;
  newPrompt: () => void;
  closeEditor: () => void;
  remove: (id: string) => Promise<boolean>;

  patchDraft: (patch: Partial<Draft>) => void;
  setTemplate: (template: string) => void;

  save: (message?: string) => Promise<boolean>;
  publish: () => Promise<boolean>;

  loadVersions: () => Promise<void>;
  viewVersion: (n: number) => Promise<void>;
  rollback: (n: number) => Promise<boolean>;

  lint: (template: string) => Promise<void>;
}

function token(): string | null {
  return useAuthStore.getState().token;
}

function messageOf(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return 'Unexpected error';
}

function configToDraft(cfg: PromptConfig, isNew = false): Draft {
  return {
    id: cfg.id,
    name: cfg.name,
    tags: cfg.tags ?? [],
    template: cfg.template ?? '',
    schema: cfg.schema ?? '',
    description: cfg.description ?? '',
    status: cfg.status,
    current_version: cfg.current_version,
    isNew,
  };
}

const EMPTY_DRAFT: Draft = {
  id: '',
  name: '',
  tags: [],
  template: '',
  schema: '{}',
  description: '',
  status: 'draft',
  current_version: 0,
  isNew: true,
};

export const usePromptsStore = create<PromptsState>((set, get) => ({
  view: 'list',
  list: [],
  listLoading: false,
  error: null,

  draft: null,
  editorLoading: false,
  editorError: null,
  saving: false,
  dirty: false,

  versions: [],
  versionsLoading: false,

  findings: [],
  linting: false,

  loadList: async () => {
    const t = token();
    if (!t) return;
    set({ listLoading: true, error: null });
    try {
      const list = await promptsApi.list(t);
      set({ list, listLoading: false });
    } catch (err) {
      set({ error: messageOf(err), listLoading: false });
    }
  },

  openEditor: async (id) => {
    const t = token();
    if (!t) return;
    set({
      view: 'editor',
      editorLoading: true,
      editorError: null,
      draft: null,
      findings: [],
      versions: [],
      dirty: false,
    });
    try {
      const cfg = await promptsApi.get(id, t);
      set({ draft: configToDraft(cfg), editorLoading: false });
      void get().loadVersions();
      void get().lint(cfg.template);
    } catch (err) {
      set({ editorError: messageOf(err), editorLoading: false });
    }
  },

  newPrompt: () => {
    set({
      view: 'editor',
      draft: { ...EMPTY_DRAFT },
      editorError: null,
      editorLoading: false,
      findings: [],
      versions: [],
      dirty: true,
    });
  },

  closeEditor: () => {
    set({ view: 'list', draft: null, findings: [], versions: [], dirty: false });
  },

  remove: async (id) => {
    const t = token();
    if (!t) return false;
    try {
      await promptsApi.remove(id, t);
      set((s) => ({ list: s.list.filter((p) => p.id !== id) }));
      return true;
    } catch (err) {
      set({ error: messageOf(err) });
      return false;
    }
  },

  patchDraft: (patch) => {
    set((s) => (s.draft ? { draft: { ...s.draft, ...patch }, dirty: true } : s));
  },

  setTemplate: (template) => {
    set((s) => (s.draft ? { draft: { ...s.draft, template }, dirty: true } : s));
  },

  save: async (message) => {
    const t = token();
    const draft = get().draft;
    if (!t || !draft) return false;
    if (!draft.id.trim() || !draft.name.trim()) {
      set({ editorError: 'id and name are required' });
      return false;
    }
    set({ saving: true, editorError: null });
    try {
      const res = await promptsApi.save(
        {
          id: draft.id.trim(),
          name: draft.name.trim(),
          template: draft.template,
          schema: draft.schema,
          tags: draft.tags,
          description: draft.description,
          message,
        },
        t,
      );
      set((s) => ({
        saving: false,
        dirty: false,
        draft: s.draft
          ? { ...s.draft, current_version: res.version, isNew: false }
          : s.draft,
      }));
      void get().loadVersions();
      void get().loadList();
      return true;
    } catch (err) {
      set({ editorError: messageOf(err), saving: false });
      return false;
    }
  },

  publish: async () => {
    const draft = get().draft;
    if (!draft) return false;
    set((s) => (s.draft ? { draft: { ...s.draft, status: 'published' } } : s));
    const ok = await get().save('publish');
    if (!ok) {
      // revert optimistic status flip on failure
      set((s) => (s.draft ? { draft: { ...s.draft, status: 'draft' } } : s));
    }
    return ok;
  },

  loadVersions: async () => {
    const t = token();
    const draft = get().draft;
    if (!t || !draft || draft.isNew) return;
    set({ versionsLoading: true });
    try {
      const versions = await promptsApi.versions(draft.id, t);
      set({ versions, versionsLoading: false });
    } catch {
      set({ versionsLoading: false });
    }
  },

  viewVersion: async (n) => {
    const t = token();
    const draft = get().draft;
    if (!t || !draft) return;
    set({ editorLoading: true, editorError: null });
    try {
      const cfg = await promptsApi.version(draft.id, n, t);
      set((s) => ({
        editorLoading: false,
        // Load the snapshot into the draft but keep it marked dirty so the user
        // must Save (which records a new current version) to persist it.
        draft: s.draft ? { ...configToDraft(cfg), isNew: false } : s.draft,
        dirty: true,
      }));
      void get().lint(cfg.template);
    } catch (err) {
      set({ editorError: messageOf(err), editorLoading: false });
    }
  },

  rollback: async (n) => {
    const t = token();
    const draft = get().draft;
    if (!t || !draft) return false;
    set({ saving: true, editorError: null });
    try {
      const res = await promptsApi.rollback(draft.id, n, t);
      const cfg = await promptsApi.get(draft.id, t);
      set({
        saving: false,
        dirty: false,
        draft: { ...configToDraft(cfg), current_version: res.version },
      });
      void get().loadVersions();
      void get().lint(cfg.template);
      return true;
    } catch (err) {
      set({ editorError: messageOf(err), saving: false });
      return false;
    }
  },

  lint: async (template) => {
    const t = token();
    if (!t) return;
    if (!template.trim()) {
      set({ findings: [], linting: false });
      return;
    }
    set({ linting: true });
    try {
      const res = await lintApi.check(template, t);
      // Drop a stale response: only apply findings if the linted template still
      // matches the current draft (the user may have typed on while we waited).
      if (get().view === 'editor' && get().draft?.template === template) {
        set({ findings: res.findings ?? [], linting: false });
      } else {
        set({ linting: false });
      }
    } catch {
      // Lint is best-effort; never blocks editing.
      set({ linting: false });
    }
  },
}));

// Window manager store — open windows, z-order/focus, minimize/close,
// drag (titlebar) + resize geometry. Geometry mutations are driven by the
// <Window> component; this store is the single source of truth.

import { create } from 'zustand';
import type { ModuleId } from '@/lib/types';

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface WinState {
  id: string;
  module: ModuleId;
  title: string;
  rect: Rect;
  z: number;
  minimized: boolean;
  maximized: boolean;
  /** Geometry stashed before maximize, restored on un-maximize. */
  restoreRect: Rect | null;
}

interface WindowStore {
  windows: WinState[];
  focusedId: string | null;
  topZ: number;

  open: (module: ModuleId, title: string) => void;
  /** Always spawn a fresh window for the module (multi-instance), even if one
   *  is already open. */
  openInstance: (module: ModuleId, title: string) => void;
  close: (id: string) => void;
  focus: (id: string) => void;
  minimize: (id: string) => void;
  toggleMinimize: (id: string) => void;
  toggleMaximize: (id: string) => void;
  move: (id: string, x: number, y: number) => void;
  resize: (id: string, w: number, h: number) => void;
  /** Re-clamp every window into the current viewport (on browser resize). */
  clampIntoView: () => void;
  /** Register a per-window veto run before that window closes (e.g.
   *  unsaved-edits confirm). Returning false aborts the close. Pass null to
   *  unregister. Keyed by window id so each instance guards independently. */
  setCloseGuard: (windowId: string, fn: (() => boolean) | null) => void;
}

const TASKBAR_H = 40;
const TITLEBAR_H = 28;
const MIN_VISIBLE = 120;

// Module-level (non-reactive) close guards, keyed by window id — toggling them
// must not re-render.
const closeGuards = new Map<string, () => boolean>();

function clampRect(r: Rect): Rect {
  const maxX = Math.max(0, window.innerWidth - MIN_VISIBLE);
  const maxY = Math.max(0, window.innerHeight - TASKBAR_H - TITLEBAR_H);
  return {
    x: Math.min(Math.max(0, r.x), maxX),
    y: Math.min(Math.max(0, r.y), maxY),
    w: Math.min(r.w, Math.max(280, window.innerWidth)),
    h: Math.min(r.h, Math.max(160, window.innerHeight - TASKBAR_H)),
  };
}

const DEFAULT_SIZE = { w: 640, h: 440 };
// Some modules need more room than the default (e.g. the 3-pane Monaco editor).
const MODULE_SIZE: Partial<Record<ModuleId, { w: number; h: number }>> = {
  'my-prompts': { w: 1000, h: 620 },
  validator: { w: 960, h: 600 },
  quality: { w: 960, h: 600 },
  queue: { w: 980, h: 620 },
};
let openCount = 0;
// Monotonic sequence guaranteeing unique window ids even for instances of the
// same module opened in the same millisecond.
let winSeq = 0;

function spawnRect(module: ModuleId): Rect {
  // Cascade new windows so they don't stack exactly.
  const offset = (openCount % 8) * 28;
  openCount += 1;
  const base = MODULE_SIZE[module] ?? DEFAULT_SIZE;
  // Clamp to the viewport so big windows still fit on small screens.
  const w = Math.min(base.w, Math.max(320, window.innerWidth - 32));
  const h = Math.min(base.h, Math.max(240, window.innerHeight - 96));
  return { x: 80 + offset, y: 64 + offset, w, h };
}

export const useWindowStore = create<WindowStore>((set, get) => ({
  windows: [],
  focusedId: null,
  topZ: 0,

  open: (module, title) => {
    // Default entry point (icons / start menu / taskbar): focus the existing
    // window for this module, or spawn the first one.
    const existing = get().windows.find((w) => w.module === module);
    if (existing) {
      set((s) => {
        const z = s.topZ + 1;
        return {
          topZ: z,
          focusedId: existing.id,
          windows: s.windows.map((w) =>
            w.id === existing.id ? { ...w, z, minimized: false } : w,
          ),
        };
      });
      return;
    }
    get().openInstance(module, title);
  },

  openInstance: (module, title) => {
    set((s) => {
      const z = s.topZ + 1;
      winSeq += 1;
      const win: WinState = {
        id: `win-${module}-${Date.now()}-${winSeq}`,
        module,
        title,
        rect: spawnRect(module),
        z,
        minimized: false,
        maximized: false,
        restoreRect: null,
      };
      return { windows: [...s.windows, win], focusedId: win.id, topZ: z };
    });
  },

  close: (id) => {
    // The window may veto its own close (e.g. unsaved prompt edits → confirm).
    const guard = closeGuards.get(id);
    if (guard && !guard()) return;
    closeGuards.delete(id);
    set((s) => {
      const windows = s.windows.filter((w) => w.id !== id);
      const focusedId =
        s.focusedId === id
          ? (windows.filter((w) => !w.minimized).sort((a, b) => b.z - a.z)[0]?.id ??
            null)
          : s.focusedId;
      return { windows, focusedId };
    });
  },

  focus: (id) =>
    set((s) => {
      if (s.focusedId === id && !s.windows.find((w) => w.id === id)?.minimized) {
        return s;
      }
      const z = s.topZ + 1;
      return {
        topZ: z,
        focusedId: id,
        windows: s.windows.map((w) =>
          w.id === id ? { ...w, z, minimized: false } : w,
        ),
      };
    }),

  minimize: (id) =>
    set((s) => ({
      windows: s.windows.map((w) => (w.id === id ? { ...w, minimized: true } : w)),
      focusedId: s.focusedId === id ? null : s.focusedId,
    })),

  toggleMinimize: (id) => {
    const win = get().windows.find((w) => w.id === id);
    if (!win) return;
    if (win.minimized || get().focusedId !== id) get().focus(id);
    else get().minimize(id);
  },

  toggleMaximize: (id) =>
    set((s) => ({
      windows: s.windows.map((w) => {
        if (w.id !== id) return w;
        if (w.maximized) {
          return {
            ...w,
            maximized: false,
            rect: w.restoreRect ?? w.rect,
            restoreRect: null,
          };
        }
        return { ...w, maximized: true, restoreRect: w.rect };
      }),
    })),

  move: (id, x, y) =>
    set((s) => ({
      windows: s.windows.map((w) =>
        w.id === id ? { ...w, rect: { ...w.rect, x, y } } : w,
      ),
    })),

  resize: (id, w, h) =>
    set((s) => ({
      windows: s.windows.map((win) =>
        win.id === id
          ? { ...win, rect: { ...win.rect, w: Math.max(280, w), h: Math.max(160, h) } }
          : win,
      ),
    })),

  clampIntoView: () =>
    set((s) => ({
      windows: s.windows.map((w) => ({ ...w, rect: clampRect(w.rect) })),
    })),

  setCloseGuard: (windowId, fn) => {
    if (fn) closeGuards.set(windowId, fn);
    else closeGuards.delete(windowId);
  },
}));

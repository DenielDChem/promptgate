// First-run guided tour (P3) — a small accessible stepper that walks new users
// through opening tools, working with windows (incl. the multi-instance ⧉
// button), and where notifications appear. Completion is remembered so it never
// nags; it can be replayed from the desktop context menu.

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react';

const TOUR_KEY = 'pg.tour.v1';

export function tourCompleted(): boolean {
  try {
    return localStorage.getItem(TOUR_KEY) === '1';
  } catch {
    return false;
  }
}

function markCompleted(): void {
  try {
    localStorage.setItem(TOUR_KEY, '1');
  } catch {
    /* private mode — tour will simply reappear next session */
  }
}

interface Step {
  glyph: string;
  title: string;
  body: ReactNode;
}

const STEPS: Step[] = [
  {
    glyph: '▣',
    title: 'Welcome to PromptGate',
    body: 'Your workspace for authoring, validating, and shipping prompts. Here is a 20-second tour of how to get around.',
  },
  {
    glyph: '◰',
    title: 'Open your tools',
    body: (
      <>
        Launch a tool from the <b className="text-violet-bright">desktop icons</b> (top-left) or
        the <b className="text-violet-bright">Start menu</b> (bottom-left). What you see depends on
        your role.
      </>
    ),
  },
  {
    glyph: '⧉',
    title: 'Work in windows',
    body: (
      <>
        Drag a window by its titlebar, resize from the corner, and use the{' '}
        <b className="text-violet-bright">⧉ button</b> to open a second copy of a tool — handy for
        comparing two prompts side by side.
      </>
    ),
  },
  {
    glyph: '✓',
    title: 'Stay informed',
    body: (
      <>
        Actions confirm with <b className="text-neon">toasts</b> in the bottom-right. Your session
        keeps you signed in; if it expires you’ll be asked to log in again.
      </>
    ),
  },
];

export function OnboardingTour({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const prevFocus = useRef<HTMLElement | null>(null);

  const last = step === STEPS.length - 1;

  const finish = useCallback(() => {
    markCompleted();
    onClose();
  }, [onClose]);

  // Focus into the dialog on open; restore focus to the trigger on close.
  useEffect(() => {
    prevFocus.current = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>('button')?.focus();
    return () => prevFocus.current?.focus?.();
  }, []);

  // Esc dismisses (and marks done so it doesn't nag).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') finish();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [finish]);

  // Trap Tab inside the dialog.
  const onPanelKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'Tab') return;
    const items = panelRef.current?.querySelectorAll<HTMLElement>('button');
    if (!items || items.length === 0) return;
    const first = items[0];
    const lastEl = items[items.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      lastEl.focus();
    } else if (!e.shiftKey && active === lastEl) {
      e.preventDefault();
      first.focus();
    }
  };

  const s = STEPS[step];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-[var(--z-toast)] flex items-center justify-center bg-bg/70 p-4"
      onClick={finish}
    >
      <div
        ref={panelRef}
        onKeyDown={onPanelKeyDown}
        onClick={(e) => e.stopPropagation()}
        className="pixel-raised rounded-pixel-lg w-full max-w-sm border border-border bg-card terminal-print"
      >
        {/* Titlebar */}
        <div className="flex items-center gap-2 rounded-t-pixel-lg bg-gradient-to-r from-violet to-violet-deep px-3 py-1.5">
          <span aria-hidden className="text-neon">
            {s.glyph}
          </span>
          <span className="font-mono text-xs font-bold uppercase tracking-widest text-white">
            Tour · {step + 1}/{STEPS.length}
          </span>
          <button
            onClick={finish}
            aria-label="Close tour"
            className="ml-auto rounded-pixel px-1.5 font-mono text-xs text-white/80 hover:text-white"
          >
            ✕
          </button>
        </div>

        <div className="flex flex-col gap-3 p-5">
          <h2 id={titleId} className="font-mono text-sm uppercase tracking-widest text-neon-dim">
            {s.title}
          </h2>
          <p className="text-sm leading-relaxed text-ink">{s.body}</p>

          {/* Progress dots */}
          <div className="flex items-center gap-1.5" aria-hidden>
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={[
                  'h-1.5 w-1.5 rounded-full',
                  i === step ? 'bg-neon' : 'bg-border',
                ].join(' ')}
              />
            ))}
          </div>

          {/* Controls */}
          <div className="mt-1 flex items-center gap-2">
            <button
              onClick={finish}
              className="rounded-pixel px-2 py-1 font-mono text-[11px] uppercase tracking-wide text-ink-dim hover:text-ink"
            >
              Skip
            </button>
            <div className="ml-auto flex items-center gap-2">
              {step > 0 && (
                <button
                  onClick={() => setStep((n) => n - 1)}
                  className="pixel-raised active:pixel-inset rounded-pixel bg-card px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-ink hover:brightness-125"
                >
                  ← Back
                </button>
              )}
              <button
                onClick={() => (last ? finish() : setStep((n) => n + 1))}
                className="pixel-raised active:pixel-inset rounded-pixel bg-neon-dim px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-wide text-bg hover:brightness-110"
              >
                {last ? 'Get started' : 'Next →'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

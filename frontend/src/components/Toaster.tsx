// Toast viewport (P2) — bottom-right stack above the taskbar. Each toast is its
// own polite live region so screen readers announce it; a non-color glyph backs
// up the colour so meaning never rides on hue alone.

import { useToastStore, type ToastKind } from '@/stores/toastStore';

const KIND_CLASS: Record<ToastKind, string> = {
  success: 'border-neon-dim',
  error: 'border-red',
  info: 'border-violet-bright',
};

const KIND_GLYPH: Record<ToastKind, string> = {
  success: '✓',
  error: '!',
  info: 'ℹ',
};

const KIND_GLYPH_CLASS: Record<ToastKind, string> = {
  success: 'text-neon',
  error: 'text-red',
  info: 'text-violet-bright',
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div
      role="region"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-12 right-3 z-[var(--z-toast)] flex max-w-xs flex-col gap-2"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          aria-live="polite"
          className={[
            'pixel-raised terminal-print pointer-events-auto flex items-start gap-2',
            'rounded-pixel border bg-card px-3 py-2 font-mono text-xs',
            KIND_CLASS[t.kind],
          ].join(' ')}
        >
          <span aria-hidden className={['shrink-0 font-bold', KIND_GLYPH_CLASS[t.kind]].join(' ')}>
            {KIND_GLYPH[t.kind]}
          </span>
          <span className="min-w-0 flex-1 text-ink">{t.message}</span>
          <button
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss notification"
            className="shrink-0 rounded-pixel px-1 text-ink-dim hover:text-ink"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

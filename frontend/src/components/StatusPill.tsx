// Base lifecycle pill — the shared pixel chip behind StatusBadge (prompt
// draft/published) and JobStatusBadge (queue lifecycle). Callers pass the
// colour class for the given state; the bevel + typography live here so every
// pill in the app stays identical.

import type { ReactNode } from 'react';

export function StatusPill({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={[
        'pixel-raised rounded-pixel px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide',
        className,
      ].join(' ')}
    >
      {children}
    </span>
  );
}

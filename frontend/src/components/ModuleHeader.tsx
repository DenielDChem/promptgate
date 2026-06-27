// Standard window-body header: an uppercase neon title, an optional count chip
// or subtitle, and a slot for trailing actions (which position themselves with
// `ml-auto`). Shared by the Prompts / Quality / Queue module bodies.

import type { ReactNode } from 'react';

interface ModuleHeaderProps {
  title: string;
  /** A parenthesised count chip, e.g. `(12)`. */
  count?: number;
  /** A plain subtitle next to the title (mutually exclusive with `count`). */
  subtitle?: string;
  /** Trailing actions — give them `ml-auto` (or wrap them) to push right. */
  children?: ReactNode;
}

export function ModuleHeader({ title, count, subtitle, children }: ModuleHeaderProps) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      <h2 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
        {title}
      </h2>
      {count !== undefined && (
        <span className="font-mono text-[11px] text-ink-dim">({count})</span>
      )}
      {subtitle && <span className="font-mono text-[11px] text-ink-dim">{subtitle}</span>}
      {children}
    </div>
  );
}

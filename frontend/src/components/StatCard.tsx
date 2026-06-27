// Pixel stat tile — label + big tabular value, with an optional leading dot
// (e.g. a grade ColorDot) and an optional hint line. Shared by the Validator
// metric cards and the Quality dashboard widgets so every figure tile matches.

import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: string;
  /** Leading badge before the label (e.g. a grade <ColorDot />). */
  dot?: ReactNode;
  /** Override the value colour (defaults to primary ink). */
  valueClassName?: string;
  hint?: ReactNode;
  /** Override the hint colour (defaults to dimmed ink). */
  hintClassName?: string;
}

export function StatCard({
  label,
  value,
  dot,
  valueClassName = 'text-ink',
  hint,
  hintClassName = 'text-ink-dim/70',
}: StatCardProps) {
  return (
    <div className="pixel-raised rounded-pixel flex flex-col gap-1 bg-card px-3 py-2">
      <div className="flex items-center gap-1.5">
        {dot}
        <span className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">
          {label}
        </span>
      </div>
      <span className={['font-mono text-xl tabular-nums', valueClassName].join(' ')}>
        {value}
      </span>
      {hint && (
        <span className={['font-mono text-[10px]', hintClassName].join(' ')}>{hint}</span>
      )}
    </div>
  );
}

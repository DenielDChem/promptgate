// Small presentational pieces shared by the jobs table + job detail (P4):
// the status pill and the terminal-style progress bar.

import type { JobStatus } from '@/lib/types';
import { JOB_STATUS_CLASS, fractionOf, isActive, progressBar } from './jobStatus';

/** Pixel-styled lifecycle pill, mirroring StatusBadge for draft/published. */
export function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={[
        'pixel-raised rounded-pixel px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide',
        JOB_STATUS_CLASS[status],
      ].join(' ')}
    >
      {status}
    </span>
  );
}

interface ProgressProps {
  status: JobStatus;
  progress: number;
  total: number;
}

/** Terminal bar `████████░░ 80%`, coloured by liveness. */
export function JobProgressBar({ status, progress, total }: ProgressProps) {
  const fraction = fractionOf(progress, total);
  const pct = Math.round(fraction * 100);
  const tint =
    status === 'failed'
      ? 'text-red'
      : status === 'cancelled'
        ? 'text-ink-dim'
        : isActive(status)
          ? 'text-violet'
          : 'text-neon';
  return (
    <span
      className={['font-mono text-xs', tint].join(' ')}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${status} — ${pct}%`}
      title={total > 0 ? `${progress}/${total}` : `${pct}%`}
    >
      {progressBar(fraction)} {pct}%
    </span>
  );
}

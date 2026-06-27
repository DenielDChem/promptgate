// Small presentational pieces shared by the jobs table + job detail (P4):
// the status pill and the terminal-style progress bar.

import { StatusPill } from '@/components/StatusPill';
import type { JobStatus } from '@/lib/types';
import { JOB_STATUS_CLASS, fractionOf, isActive, progressBar } from './jobStatus';

/** Pixel-styled lifecycle pill, mirroring StatusBadge for draft/published. */
export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <StatusPill className={JOB_STATUS_CLASS[status]}>{status}</StatusPill>;
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
          ? 'text-violet-bright'
          : 'text-neon';
  return (
    <span
      className={['font-mono text-xs tabular-nums', tint].join(' ')}
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

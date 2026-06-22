// Shared presentation helpers for queue job status (P4) — colour token per
// lifecycle state + the terminal-style progress-bar renderer.

import type { JobStatus } from '@/lib/types';

/** Tailwind class for the status pill background per lifecycle state. */
export const JOB_STATUS_CLASS: Record<JobStatus, string> = {
  queued: 'bg-card text-ink-dim',
  running: 'bg-violet text-white',
  completed: 'bg-neon-dim text-bg',
  failed: 'bg-red text-white',
  cancelled: 'bg-card text-orange',
};

/** queued/running are still in flight → cancellable. */
export function isActive(status: JobStatus): boolean {
  return status === 'queued' || status === 'running';
}

const BAR_WIDTH = 10;
const FILLED = '█';
const EMPTY = '░';

/** Fraction done in 0..1, guarding against total=0 / overshoot. */
export function fractionOf(progress: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min(1, progress / total));
}

/** A 10-cell terminal bar, e.g. `████████░░`. */
export function progressBar(fraction: number): string {
  const filled = Math.round(fraction * BAR_WIDTH);
  return FILLED.repeat(filled) + EMPTY.repeat(BAR_WIDTH - filled);
}

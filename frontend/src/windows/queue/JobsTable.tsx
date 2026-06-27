// The jobs table (P4 §9.3): id, task (type + prompt), status badge, terminal
// progress bar, and row actions (Cancel while in flight; Report when terminal).
// Rows are clickable → open the job detail. Polling is owned by the store.

import { JOB_TYPE_LABELS } from '@/stores/jobsStore';
import { Th, interactiveRowProps } from '@/components/DataTable';
import { JobStatusBadge, JobProgressBar } from './JobBits';
import { isActive } from './jobStatus';
import type { JobSummary } from '@/lib/types';

interface JobsTableProps {
  jobs: JobSummary[];
  onSelect: (id: string) => void;
  onCancel: (id: string) => void;
}

export function JobsTable({ jobs, onSelect, onCancel }: JobsTableProps) {
  return (
    <table className="w-full border-collapse font-mono text-xs">
      <thead className="sticky top-0 z-10 bg-card text-[10px] uppercase tracking-wide text-ink-dim">
        <tr>
          <Th>Job</Th>
          <Th>Task</Th>
          <Th>Status</Th>
          <Th>Progress</Th>
          <Th className="text-right">Actions</Th>
        </tr>
      </thead>
      <tbody>
        {jobs.map((j) => (
          <tr key={j.id} {...interactiveRowProps(`Open job ${j.id}`, () => onSelect(j.id))}>
            <td className="px-2 py-1.5 text-ink-dim">{j.id}</td>
            <td className="px-2 py-1.5">
              <span className="text-violet-bright">{JOB_TYPE_LABELS[j.type]}</span>
              {j.prompt_id && (
                <span className="ml-1 text-ink-dim">· {j.prompt_id}</span>
              )}
            </td>
            <td className="px-2 py-1.5">
              <JobStatusBadge status={j.status} />
            </td>
            <td className="px-2 py-1.5">
              <JobProgressBar status={j.status} progress={j.progress} total={j.total} />
            </td>
            <td className="px-2 py-1.5 text-right">
              {isActive(j.status) ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCancel(j.id);
                  }}
                  aria-label={`Cancel job ${j.id}`}
                  className="rounded-pixel px-1.5 py-0.5 font-mono text-[11px] text-ink-dim hover:bg-red hover:text-white"
                >
                  Cancel
                </button>
              ) : (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect(j.id);
                  }}
                  aria-label={`Open report for job ${j.id}`}
                  className="rounded-pixel px-1.5 py-0.5 font-mono text-[11px] text-ink-dim hover:bg-violet/30 hover:text-ink"
                >
                  Report
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}


// `queue` window body — the Task Queue admin module (P4 §9). Admin-only via
// RBAC (the icon/window are hidden for every other role). Owns the polling
// lifecycle: starts on mount, stops on unmount so we never poll while closed.
//
// View-swap inside the window (like Validator/Quality): the jobs table + status
// bar by default; the job detail when a row/Report is clicked.

import { useEffect, useState } from 'react';
import { useJobsStore } from '@/stores/jobsStore';
import { PixelButton } from '@/components/PixelButton';
import { JobsTable } from './queue/JobsTable';
import { CreateJobModal } from './queue/CreateJobModal';
import { JobDetailPanel } from './queue/JobDetailPanel';
import type { JobSummaryCounts } from '@/lib/types';

export function QueueModule() {
  const jobs = useJobsStore((s) => s.jobs);
  const summary = useJobsStore((s) => s.summary);
  const loading = useJobsStore((s) => s.loading);
  const listError = useJobsStore((s) => s.listError);
  const startPolling = useJobsStore((s) => s.startPolling);
  const stopPolling = useJobsStore((s) => s.stopPolling);
  const viewJob = useJobsStore((s) => s.viewJob);
  const clearDetail = useJobsStore((s) => s.clearDetail);
  const cancelJob = useJobsStore((s) => s.cancelJob);

  const [showCreate, setShowCreate] = useState(false);
  // null = table view; otherwise we're inspecting a selected job.
  const [detailOpen, setDetailOpen] = useState(false);

  // Poll only while the window is open (spec §9.3).
  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, [startPolling, stopPolling]);

  const openDetail = (id: string) => {
    void viewJob(id);
    setDetailOpen(true);
  };
  const backToTable = () => {
    setDetailOpen(false);
    clearDetail();
  };

  if (detailOpen) {
    return <JobDetailPanel onBack={backToTable} />;
  }

  return (
    <div className="relative flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 items-center gap-2">
        <h2 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
          Task Queue
        </h2>
        <span className="font-mono text-[11px] text-ink-dim">async jobs</span>
        <PixelButton
          variant="action"
          className="ml-auto"
          onClick={() => setShowCreate(true)}
        >
          + New job
        </PixelButton>
      </div>

      <StatusBar summary={summary} />

      {listError && (
        <p
          role="alert"
          className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs text-red"
        >
          {listError}
        </p>
      )}

      <div className="pixel-inset rounded-pixel min-h-0 flex-1 overflow-auto bg-bg">
        {loading ? (
          <p className="p-4 text-center font-mono text-xs text-ink-dim">
            <span className="caret">loading queue</span>
          </p>
        ) : jobs.length === 0 ? (
          <EmptyState onCreate={() => setShowCreate(true)} />
        ) : (
          <JobsTable jobs={jobs} onSelect={openDetail} onCancel={cancelJob} />
        )}
      </div>

      {showCreate && <CreateJobModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

/** `Active: N │ Queued: N │ Completed: N` (spec §9.2). */
function StatusBar({ summary }: { summary: JobSummaryCounts }) {
  return (
    <div className="pixel-raised rounded-pixel flex shrink-0 items-center gap-3 bg-card px-3 py-2 font-mono text-xs">
      <Stat label="Active" value={summary.running} className="text-violet" />
      <Sep />
      <Stat label="Queued" value={summary.queued} className="text-ink" />
      <Sep />
      <Stat label="Completed" value={summary.completed} className="text-neon" />
      {summary.failed > 0 && (
        <>
          <Sep />
          <Stat label="Failed" value={summary.failed} className="text-red" />
        </>
      )}
    </div>
  );
}

function Stat({ label, value, className }: { label: string; value: number; className: string }) {
  return (
    <span className="text-ink-dim">
      {label}: <span className={className}>{value}</span>
    </span>
  );
}

function Sep() {
  return <span className="text-border">│</span>;
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="text-4xl text-violet" aria-hidden>
        ⏳
      </span>
      <p className="font-mono text-xs text-ink-dim">
        No jobs yet. Queue a validation, template generation, or mass test.
      </p>
      <PixelButton variant="action" onClick={onCreate}>
        + New job
      </PixelButton>
    </div>
  );
}

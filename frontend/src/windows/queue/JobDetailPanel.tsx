// Job detail view (P4 §9.5): progress, intermediate/partial result, error if
// failed, Cancel (while in flight) + Back. The store keeps `detail` fresh on
// each poll while the job is still queued/running.

import { useJobsStore, JOB_TYPE_LABELS, JOB_PRIORITY_LABELS } from '@/stores/jobsStore';
import { PixelButton } from '@/components/PixelButton';
import { JobStatusBadge, JobProgressBar } from './JobBits';
import { isActive } from './jobStatus';
import type { JobDetail } from '@/lib/types';

export function JobDetailPanel({ onBack }: { onBack: () => void }) {
  const detail = useJobsStore((s) => s.detail);
  const loading = useJobsStore((s) => s.detailLoading);
  const error = useJobsStore((s) => s.detailError);
  const cancelJob = useJobsStore((s) => s.cancelJob);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 items-center gap-2">
        <PixelButton onClick={onBack} aria-label="Back to queue">
          ← Back
        </PixelButton>
        <h2 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
          {detail ? `Job ${detail.id}` : 'Job'}
        </h2>
        {detail && <JobStatusBadge status={detail.status} />}
        {detail && isActive(detail.status) && (
          <PixelButton
            variant="danger"
            className="ml-auto"
            onClick={() => void cancelJob(detail.id)}
          >
            Cancel
          </PixelButton>
        )}
      </div>

      {error && (
        <p
          role="alert"
          className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs text-red"
        >
          {error}
        </p>
      )}

      {!detail ? (
        <p className="p-4 text-center font-mono text-xs text-ink-dim">
          {loading ? (
            <span className="caret">loading job</span>
          ) : (
            'Select a job to inspect.'
          )}
        </p>
      ) : (
        <Body detail={detail} />
      )}
    </div>
  );
}

function Body({ detail }: { detail: JobDetail }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto pr-1">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Field label="Type" value={JOB_TYPE_LABELS[detail.type]} />
        <Field label="Priority" value={JOB_PRIORITY_LABELS[detail.priority]} />
        <Field label="Prompt" value={detail.prompt_id || '—'} />
        <Field label="Model" value={detail.model_id || '—'} />
      </div>

      <div className="pixel-raised rounded-pixel flex flex-col gap-2 bg-card px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">
          Progress
        </span>
        <JobProgressBar
          status={detail.status}
          progress={detail.progress}
          total={detail.total}
        />
        <span className="font-mono text-[10px] text-ink-dim/70">
          created {formatDate(detail.created_at)}
          {detail.updated_at ? ` · updated ${formatDate(detail.updated_at)}` : ''}
        </span>
      </div>

      {detail.error && (
        <div className="pixel-inset rounded-pixel bg-bg p-3">
          <span className="font-mono text-[10px] uppercase tracking-wide text-red">
            Error
          </span>
          <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-red">
            {detail.error}
          </pre>
        </div>
      )}

      <div className="pixel-inset rounded-pixel min-h-0 flex-1 overflow-auto bg-bg p-3">
        <span className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">
          {isActive(detail.status) ? 'Partial result' : 'Result'}
        </span>
        {detail.result ? (
          <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-ink">
            {JSON.stringify(detail.result, null, 2)}
          </pre>
        ) : (
          <p className="mt-1 font-mono text-xs text-ink-dim">
            {isActive(detail.status)
              ? 'No intermediate result yet.'
              : 'No result recorded.'}
          </p>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="pixel-raised rounded-pixel flex flex-col gap-1 bg-card px-3 py-2">
      <span className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">
        {label}
      </span>
      <span className="truncate font-mono text-sm text-ink" title={value}>
        {value}
      </span>
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

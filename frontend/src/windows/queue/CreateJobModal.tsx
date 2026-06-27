// Create-job modal (P4 §9.4): type / target prompt / model / priority pickers.
// Submit → POST /api/jobs via the store, which refreshes the table and closes us.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useJobsStore, JOB_TYPE_LABELS, JOB_PRIORITY_LABELS } from '@/stores/jobsStore';
import { PixelButton } from '@/components/PixelButton';
import { PixelSelect } from '@/components/PixelSelect';
import type { JobPriority, JobType } from '@/lib/types';

const JOB_TYPES: JobType[] = ['validation', 'generation', 'mass_test'];
const PRIORITIES: JobPriority[] = ['high', 'medium', 'low'];

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function CreateJobModal({ onClose }: { onClose: () => void }) {
  const prompts = useJobsStore((s) => s.prompts);
  const models = useJobsStore((s) => s.models);
  const lookupsLoading = useJobsStore((s) => s.lookupsLoading);
  const creating = useJobsStore((s) => s.creating);
  const createError = useJobsStore((s) => s.createError);
  const loadLookups = useJobsStore((s) => s.loadLookups);
  const create = useJobsStore((s) => s.create);

  const [type, setType] = useState<JobType>('validation');
  const [promptId, setPromptId] = useState('');
  const [modelId, setModelId] = useState('');
  const [priority, setPriority] = useState<JobPriority>('medium');
  const [touched, setTouched] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const prevFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    void loadLookups();
  }, [loadLookups]);

  // Default the pickers to the first option once lookups arrive.
  useEffect(() => {
    setPromptId((cur) => cur || prompts[0]?.id || '');
  }, [prompts]);
  useEffect(() => {
    setModelId((cur) => cur || models[0] || '');
  }, [models]);

  // Don't discard a half-filled form on an accidental backdrop/Esc dismiss.
  const attemptClose = useCallback(() => {
    if (touched && !window.confirm('Discard this job?')) return;
    onClose();
  }, [touched, onClose]);

  // Move focus into the dialog on open; restore it to the trigger on close.
  useEffect(() => {
    prevFocus.current = document.activeElement as HTMLElement | null;
    const first = panelRef.current?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panelRef.current)?.focus();
    return () => prevFocus.current?.focus?.();
  }, []);

  // Esc closes (with discard-guard).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') attemptClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [attemptClose]);

  // Trap Tab focus inside the dialog.
  const onPanelKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'Tab') return;
    const items = panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
    if (!items || items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const submit = async () => {
    const job = await create({
      type,
      prompt_id: promptId || undefined,
      model_id: modelId || undefined,
      priority,
    });
    if (job) onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cjm-title"
      className="absolute inset-0 z-30 flex items-center justify-center bg-bg/70 p-4"
      onClick={attemptClose}
    >
      <div
        ref={panelRef}
        onKeyDown={onPanelKeyDown}
        className="pixel-raised rounded-pixel w-full max-w-md bg-card p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center gap-2">
          <h3 id="cjm-title" className="font-mono text-sm uppercase tracking-widest text-neon-dim">
            New job
          </h3>
          <button
            onClick={attemptClose}
            aria-label="Close"
            className="ml-auto rounded-pixel px-1.5 py-0.5 font-mono text-ink-dim hover:bg-red hover:text-white"
          >
            ✕
          </button>
        </div>

        {createError && (
          <p
            role="alert"
            className="pixel-inset rounded-pixel mb-3 bg-bg px-2 py-1 font-mono text-xs text-red"
          >
            {createError}
          </p>
        )}

        <div className="flex flex-col gap-3">
          <PixelSelect
            label="Type"
            value={type}
            onChange={(v) => { setType(v as JobType); setTouched(true); }}
            options={JOB_TYPES.map((t) => ({ value: t, label: JOB_TYPE_LABELS[t] }))}
          />
          <PixelSelect
            label="Target prompt"
            value={promptId}
            disabled={lookupsLoading}
            invalid={!lookupsLoading && !promptId}
            invalidHint="Pick a prompt to run the job against."
            onChange={(v) => { setPromptId(v); setTouched(true); }}
            options={prompts.map((p) => ({ value: p.id, label: `${p.name} (${p.id})` }))}
            placeholder={lookupsLoading ? 'loading…' : 'no prompts'}
          />
          <PixelSelect
            label="Model"
            value={modelId}
            disabled={lookupsLoading}
            invalid={!lookupsLoading && !modelId}
            invalidHint="Pick a model for this job."
            onChange={(v) => { setModelId(v); setTouched(true); }}
            options={models.map((m) => ({ value: m, label: m }))}
            placeholder={lookupsLoading ? 'loading…' : 'no models'}
          />
          <PixelSelect
            label="Priority"
            value={priority}
            onChange={(v) => { setPriority(v as JobPriority); setTouched(true); }}
            options={PRIORITIES.map((p) => ({ value: p, label: JOB_PRIORITY_LABELS[p] }))}
          />
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <PixelButton onClick={attemptClose} disabled={creating}>
            Cancel
          </PixelButton>
          <PixelButton variant="primary" onClick={() => void submit()} disabled={creating}>
            {creating ? 'Queuing…' : '▶ Queue job'}
          </PixelButton>
        </div>
      </div>
    </div>
  );
}


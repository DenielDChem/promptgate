// Create-job modal (P4 §9.4): type / target prompt / model / priority pickers.
// Submit → POST /api/jobs via the store, which refreshes the table and closes us.

import { useEffect, useState } from 'react';
import { useJobsStore, JOB_TYPE_LABELS, JOB_PRIORITY_LABELS } from '@/stores/jobsStore';
import { PixelButton } from '@/components/PixelButton';
import type { JobPriority, JobType } from '@/lib/types';

const JOB_TYPES: JobType[] = ['validation', 'generation', 'mass_test'];
const PRIORITIES: JobPriority[] = ['high', 'medium', 'low'];

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

  // Esc closes the modal.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

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
      aria-label="Create job"
      className="absolute inset-0 z-30 flex items-center justify-center bg-bg/70 p-4"
      onClick={onClose}
    >
      <div
        className="pixel-raised rounded-pixel w-full max-w-md bg-card p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center gap-2">
          <h3 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
            New job
          </h3>
          <button
            onClick={onClose}
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
          <Select
            label="Type"
            value={type}
            onChange={(v) => setType(v as JobType)}
            options={JOB_TYPES.map((t) => ({ value: t, label: JOB_TYPE_LABELS[t] }))}
          />
          <Select
            label="Target prompt"
            value={promptId}
            disabled={lookupsLoading}
            onChange={setPromptId}
            options={prompts.map((p) => ({ value: p.id, label: `${p.name} (${p.id})` }))}
            placeholder={lookupsLoading ? 'loading…' : 'no prompts'}
          />
          <Select
            label="Model"
            value={modelId}
            disabled={lookupsLoading}
            onChange={setModelId}
            options={models.map((m) => ({ value: m, label: m }))}
            placeholder={lookupsLoading ? 'loading…' : 'no models'}
          />
          <Select
            label="Priority"
            value={priority}
            onChange={(v) => setPriority(v as JobPriority)}
            options={PRIORITIES.map((p) => ({ value: p, label: JOB_PRIORITY_LABELS[p] }))}
          />
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <PixelButton onClick={onClose} disabled={creating}>
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

interface SelectProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

function Select({ label, value, options, onChange, disabled, placeholder }: SelectProps) {
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="font-mono text-xs uppercase tracking-wide text-ink-dim">
        {label}
      </span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="pixel-inset rounded-pixel bg-bg px-2.5 py-1.5 font-mono text-sm text-ink focus:outline-none disabled:opacity-50"
      >
        {options.length === 0 && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

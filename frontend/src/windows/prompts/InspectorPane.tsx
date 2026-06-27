// RIGHT pane (~25%): metadata fields, status, version dropdown + history,
// rollback, save/publish. All mutating controls are hidden when read-only.

import { useState } from 'react';
import { usePromptsStore } from '@/stores/promptsStore';
import { PixelButton } from '@/components/PixelButton';
import { PixelField } from '@/components/PixelField';
import { StatusBadge } from '@/components/StatusBadge';
import type { PromptVersion } from '@/lib/types';

interface InspectorProps {
  readOnly: boolean;
  onSave: () => void;
  onPublish: () => void;
}

export function InspectorPane({ readOnly, onSave, onPublish }: InspectorProps) {
  const draft = usePromptsStore((s) => s.draft);
  const dirty = usePromptsStore((s) => s.dirty);
  const saving = usePromptsStore((s) => s.saving);
  const versions = usePromptsStore((s) => s.versions);
  const versionsLoading = usePromptsStore((s) => s.versionsLoading);
  const patchDraft = usePromptsStore((s) => s.patchDraft);
  const viewVersion = usePromptsStore((s) => s.viewVersion);
  const rollback = usePromptsStore((s) => s.rollback);

  const [showHistory, setShowHistory] = useState(false);

  if (!draft) return null;

  const onSelectVersion = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const n = Number(e.target.value);
    if (n && n !== draft.current_version) {
      // Loading another version overwrites the draft — guard unsaved edits.
      if (dirty && !window.confirm('Discard unsaved changes to view another version?')) {
        e.target.value = String(draft.current_version);
        return;
      }
      void viewVersion(n);
    }
  };

  const onRollback = async (n: number) => {
    if (!window.confirm(`Roll back to v${n}? This becomes a new current version.`)) {
      return;
    }
    await rollback(n);
    setShowHistory(false);
  };

  return (
    <aside className="flex h-full flex-col gap-2 overflow-auto pixel-inset rounded-pixel bg-bg p-2">
      <div className="flex items-center gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-ink-dim">
          Inspector
        </h3>
        <div className="ml-auto">
          <StatusBadge status={draft.status} />
        </div>
      </div>

      <PixelField
        label="ID"
        value={draft.id}
        disabled={readOnly || !draft.isNew}
        placeholder="my-prompt-id"
        onChange={(e) => patchDraft({ id: e.target.value })}
      />
      <PixelField
        label="Name"
        value={draft.name}
        disabled={readOnly}
        placeholder="Human-readable name"
        onChange={(e) => patchDraft({ name: e.target.value })}
      />
      <PixelField
        label="Tags (comma-sep)"
        value={draft.tags.join(', ')}
        disabled={readOnly}
        placeholder="rag, summarize"
        onChange={(e) =>
          patchDraft({
            tags: e.target.value
              .split(',')
              .map((t) => t.trim())
              .filter(Boolean),
          })
        }
      />
      <PixelField
        label="Description"
        value={draft.description}
        disabled={readOnly}
        placeholder="What this prompt does"
        onChange={(e) => patchDraft({ description: e.target.value })}
      />

      {/* Version selector */}
      <label className="flex flex-col gap-1">
        <span className="font-mono text-xs uppercase tracking-wide text-ink-dim">
          Version{draft.isNew ? ' (unsaved)' : ` — current v${draft.current_version}`}
        </span>
        <select
          disabled={draft.isNew || versions.length === 0}
          value={draft.current_version}
          onChange={onSelectVersion}
          className="pixel-inset rounded-pixel bg-bg px-2 py-1.5 font-mono text-sm text-ink disabled:opacity-50"
        >
          {versions.length === 0 ? (
            <option value={draft.current_version}>
              v{draft.current_version}
            </option>
          ) : (
            versions.map((v) => (
              <option key={v.version_no} value={v.version_no}>
                v{v.version_no}
                {v.version_no === draft.current_version ? ' (current)' : ''}
                {v.message ? ` — ${v.message}` : ''}
              </option>
            ))
          )}
        </select>
      </label>

      <PixelButton
        onClick={() => setShowHistory((v) => !v)}
        disabled={draft.isNew}
        aria-expanded={showHistory}
      >
        History {showHistory ? '▾' : '▸'}
      </PixelButton>

      {showHistory && (
        <HistoryPanel
          versions={versions}
          loading={versionsLoading}
          current={draft.current_version}
          readOnly={readOnly}
          onView={(n) => void viewVersion(n)}
          onRollback={(n) => void onRollback(n)}
        />
      )}

      {/* Save / Publish */}
      {!readOnly && (
        <div className="mt-auto flex flex-col gap-2 border-t border-border pt-2">
          {dirty && (
            <span className="font-mono text-[10px] uppercase tracking-wide text-orange">
              unsaved changes
            </span>
          )}
          <div className="flex gap-2">
            <PixelButton
              variant="primary"
              className="flex-1"
              disabled={saving}
              onClick={onSave}
            >
              {saving ? '…' : 'Save'}
            </PixelButton>
            <PixelButton
              variant="action"
              className="flex-1"
              disabled={saving || draft.status === 'published'}
              onClick={onPublish}
            >
              Publish
            </PixelButton>
          </div>
          <span className="font-mono text-[10px] text-ink-dim">
            ⌘/Ctrl+S save · ⌘/Ctrl+⇧+V re-lint
          </span>
        </div>
      )}
    </aside>
  );
}

function HistoryPanel({
  versions,
  loading,
  current,
  readOnly,
  onView,
  onRollback,
}: {
  versions: PromptVersion[];
  loading: boolean;
  current: number;
  readOnly: boolean;
  onView: (n: number) => void;
  onRollback: (n: number) => void;
}) {
  if (loading) {
    return (
      <p className="caret px-1 font-mono text-[11px] text-ink-dim">loading history</p>
    );
  }
  if (versions.length === 0) {
    return (
      <p className="px-1 font-mono text-[11px] text-ink-dim">No version history.</p>
    );
  }
  return (
    <ul className="flex flex-col gap-1 pixel-inset rounded-pixel bg-card p-1">
      {versions.map((v) => (
        <li
          key={v.version_no}
          className="flex flex-col gap-0.5 rounded-pixel px-1.5 py-1 hover:bg-violet/15"
        >
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <button
              onClick={() => onView(v.version_no)}
              className="text-neon-dim hover:text-neon"
            >
              v{v.version_no}
            </button>
            {v.version_no === current && (
              <span className="text-[9px] uppercase text-violet-bright">current</span>
            )}
            <time className="ml-auto text-[9px] text-ink-dim" dateTime={v.created_at}>
              {formatTs(v.created_at)}
            </time>
          </div>
          {v.message && (
            <span className="font-mono text-[10px] text-ink-dim">{v.message}</span>
          )}
          {!readOnly && v.version_no !== current && (
            <button
              onClick={() => onRollback(v.version_no)}
              className="self-start rounded-pixel px-1 py-px font-mono text-[10px] uppercase text-orange hover:bg-orange hover:text-bg"
            >
              ↺ rollback
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function formatTs(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

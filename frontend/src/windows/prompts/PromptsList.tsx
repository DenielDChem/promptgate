// Prompts list view (the `my-prompts` window body in 'list' mode).
// Table of the caller's prompts; "+ New" + delete gated by RBAC.

import { useEffect } from 'react';
import { usePromptsStore } from '@/stores/promptsStore';
import { useAuthStore } from '@/stores/authStore';
import { moduleAccess } from '@/lib/rbac';
import { PixelButton } from '@/components/PixelButton';
import { StatusBadge } from '@/components/StatusBadge';

export function PromptsList() {
  const role = useAuthStore((s) => s.user?.role ?? 'guest');
  const readOnly = moduleAccess(role, 'my-prompts').readOnly;

  const list = usePromptsStore((s) => s.list);
  const loading = usePromptsStore((s) => s.listLoading);
  const error = usePromptsStore((s) => s.error);
  const loadList = usePromptsStore((s) => s.loadList);
  const openEditor = usePromptsStore((s) => s.openEditor);
  const newPrompt = usePromptsStore((s) => s.newPrompt);
  const remove = usePromptsStore((s) => s.remove);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const onDelete = async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (!window.confirm(`Delete prompt "${name}" (${id})? This moves it to trash.`)) {
      return;
    }
    await remove(id);
  };

  return (
    <div className="flex h-full flex-col gap-2">
      {/* Toolbar */}
      <div className="flex shrink-0 items-center gap-2">
        <h2 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
          My Prompts
        </h2>
        <span className="font-mono text-[11px] text-ink-dim">({list.length})</span>
        <div className="ml-auto flex items-center gap-2">
          <PixelButton onClick={() => void loadList()} aria-label="Refresh list">
            ↻
          </PixelButton>
          {!readOnly && (
            <PixelButton variant="action" onClick={newPrompt}>
              + New
            </PixelButton>
          )}
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs text-red"
        >
          {error}
        </p>
      )}

      {/* Body */}
      <div className="min-h-0 flex-1 overflow-auto pixel-inset rounded-pixel bg-bg">
        {loading ? (
          <p className="p-4 text-center font-mono text-xs text-ink-dim">
            <span className="caret">loading prompts</span>
          </p>
        ) : list.length === 0 ? (
          <EmptyState readOnly={readOnly} onNew={newPrompt} />
        ) : (
          <table className="w-full border-collapse font-mono text-xs">
            <thead className="sticky top-0 z-10 bg-card text-[10px] uppercase tracking-wide text-ink-dim">
              <tr>
                <Th>ID</Th>
                <Th>Name</Th>
                <Th>Tags</Th>
                <Th>Status</Th>
                <Th>Ver</Th>
                {!readOnly && <Th>—</Th>}
              </tr>
            </thead>
            <tbody>
              {list.map((p) => (
                <tr
                  key={p.id}
                  tabIndex={0}
                  onClick={() => void openEditor(p.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void openEditor(p.id);
                  }}
                  className="cursor-pointer border-b border-border text-ink hover:bg-violet/15 focus:bg-violet/20 focus:outline-none"
                >
                  <td className="px-2 py-1.5">
                    <span className="pixel-inset rounded-pixel bg-bg px-1.5 py-0.5 text-neon-dim">
                      {p.id}
                    </span>
                  </td>
                  <td className="px-2 py-1.5">{p.name}</td>
                  <td className="px-2 py-1.5">
                    <div className="flex flex-wrap gap-1">
                      {p.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-pixel bg-card px-1 py-px text-[10px] text-violet"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-2 py-1.5">
                    <StatusBadge status={p.status} />
                  </td>
                  <td className="px-2 py-1.5 text-ink-dim">v{p.current_version}</td>
                  {!readOnly && (
                    <td className="px-2 py-1.5">
                      <button
                        aria-label={`Delete ${p.name}`}
                        onClick={(e) => void onDelete(e, p.id, p.name)}
                        className="rounded-pixel px-1.5 py-0.5 text-ink-dim hover:bg-red hover:text-white"
                      >
                        ✕
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-2 py-1.5 text-left font-normal">{children}</th>;
}

function EmptyState({
  readOnly,
  onNew,
}: {
  readOnly: boolean;
  onNew: () => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="text-4xl text-violet" aria-hidden>
        ▤
      </span>
      <p className="font-mono text-xs text-ink-dim">
        No prompts yet.
        {readOnly ? ' Nothing has been shared with you.' : ' Create your first one.'}
      </p>
      {!readOnly && (
        <PixelButton variant="action" onClick={onNew}>
          + New Prompt
        </PixelButton>
      )}
    </div>
  );
}

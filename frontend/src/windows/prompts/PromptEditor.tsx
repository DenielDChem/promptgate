// 3-pane prompt editor (the `my-prompts` window body in 'editor' mode).
// LEFT outline (~22%) · CENTER Monaco + problems (~53%) · RIGHT inspector (~25%).
// Hotkeys: Ctrl/Cmd+S = save · Ctrl/Cmd+Shift+V = re-lint (browser default
// prevented for both).

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePromptsStore } from '@/stores/promptsStore';
import { useAuthStore } from '@/stores/authStore';
import { moduleAccess } from '@/lib/rbac';
import { PixelButton } from '@/components/PixelButton';
import { OutlinePane } from './OutlinePane';
import { EditorPane } from './EditorPane';
import { InspectorPane } from './InspectorPane';

export function PromptEditor() {
  const role = useAuthStore((s) => s.user?.role ?? 'guest');
  const readOnly = moduleAccess(role, 'my-prompts').readOnly;

  const draft = usePromptsStore((s) => s.draft);
  const loading = usePromptsStore((s) => s.editorLoading);
  const editorError = usePromptsStore((s) => s.editorError);
  const findings = usePromptsStore((s) => s.findings);
  const linting = usePromptsStore((s) => s.linting);

  const closeEditor = usePromptsStore((s) => s.closeEditor);
  const setTemplate = usePromptsStore((s) => s.setTemplate);
  const lint = usePromptsStore((s) => s.lint);
  const save = usePromptsStore((s) => s.save);
  const publish = usePromptsStore((s) => s.publish);

  const [relintNonce, setRelintNonce] = useState(0);
  const revealRef = useRef<((line: number) => void) | null>(null);

  const registerReveal = useCallback((fn: (line: number) => void) => {
    revealRef.current = fn;
  }, []);

  const doSave = useCallback(() => {
    if (readOnly) return;
    void save();
  }, [readOnly, save]);

  const doRelint = useCallback(() => {
    setRelintNonce((n) => n + 1);
  }, []);

  // Global hotkeys (window-scoped: only meaningful while editor is mounted).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      if (e.key.toLowerCase() === 's' && !e.shiftKey) {
        e.preventDefault();
        doSave();
      } else if (e.key.toLowerCase() === 'v' && e.shiftKey) {
        e.preventDefault();
        doRelint();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [doSave, doRelint]);

  return (
    <div className="flex h-full flex-col gap-2">
      {/* Header bar */}
      <div className="flex shrink-0 items-center gap-2">
        <PixelButton onClick={closeEditor} aria-label="Back to list">
          ← List
        </PixelButton>
        <h2 className="truncate font-mono text-sm uppercase tracking-widest text-neon-dim">
          {draft?.isNew ? 'New Prompt' : (draft?.name ?? 'Prompt')}
        </h2>
        {readOnly && (
          <span className="pixel-raised rounded-pixel bg-card px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-orange">
            read-only
          </span>
        )}
      </div>

      {editorError && (
        <p
          role="alert"
          className="shrink-0 pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs text-red"
        >
          {editorError}
        </p>
      )}

      {loading || !draft ? (
        <div className="flex flex-1 items-center justify-center">
          <span className="caret font-mono text-xs text-neon-dim">
            loading editor
          </span>
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[22%_53%_25%] gap-2">
          <OutlinePane
            template={draft.template}
            onJump={(line) => revealRef.current?.(line)}
          />
          <EditorPane
            template={draft.template}
            readOnly={readOnly}
            findings={findings}
            linting={linting}
            onChange={setTemplate}
            onLint={(v) => void lint(v)}
            registerReveal={registerReveal}
            relintNonce={relintNonce}
          />
          <InspectorPane
            readOnly={readOnly}
            onSave={doSave}
            onPublish={() => void publish()}
          />
        </div>
      )}
    </div>
  );
}

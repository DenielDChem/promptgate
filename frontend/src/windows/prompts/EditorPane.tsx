// CENTER pane (~53%): Monaco editor bound to the template + a debounced lint
// pass that paints findings as markers (squiggles + hover), plus a "Problems"
// strip listing findings (click → jump to line).

import { useCallback, useEffect, useRef } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';
import { setupMonaco, monaco } from '@/lib/monacoSetup';
import { LINT_COLOR, LINT_LABEL, toMarkers } from '@/lib/lintMarkers';
import type { LintFinding } from '@/lib/types';

setupMonaco();

const LINT_DEBOUNCE_MS = 400;
const MARKER_OWNER = 'promptgate-lint';

interface EditorPaneProps {
  template: string;
  readOnly: boolean;
  findings: LintFinding[];
  linting: boolean;
  onChange: (value: string) => void;
  onLint: (value: string) => void;
  /** Exposes a reveal-line fn to the parent (outline pane + problems). */
  registerReveal: (reveal: (line: number) => void) => void;
  /** Re-lint trigger token — bump to force an immediate lint (Ctrl+Shift+V). */
  relintNonce: number;
}

export function EditorPane({
  template,
  readOnly,
  findings,
  linting,
  onChange,
  onLint,
  registerReveal,
  relintNonce,
}: EditorPaneProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const modelRef = useRef<editor.ITextModel | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reveal = useCallback((line: number) => {
    const ed = editorRef.current;
    if (!ed) return;
    ed.revealLineInCenter(line);
    ed.setPosition({ lineNumber: line, column: 1 });
    ed.focus();
  }, []);

  const onMount: OnMount = (ed) => {
    editorRef.current = ed;
    modelRef.current = ed.getModel();
    registerReveal(reveal);
  };

  // Paint markers whenever findings change.
  useEffect(() => {
    const model = modelRef.current;
    if (!model) return;
    monaco.editor.setModelMarkers(
      model,
      MARKER_OWNER,
      toMarkers(findings, monaco.MarkerSeverity),
    );
  }, [findings]);

  // Debounced lint on template change.
  const handleChange = (value: string | undefined) => {
    const next = value ?? '';
    onChange(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => onLint(next), LINT_DEBOUNCE_MS);
  };

  // Force an immediate lint when the re-lint hotkey fires.
  useEffect(() => {
    if (relintNonce > 0) onLint(template);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [relintNonce]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div className="flex h-full min-h-0 flex-col gap-1">
      <div
        role="group"
        aria-label="Prompt template editor"
        className="min-h-0 flex-1 overflow-hidden pixel-inset rounded-pixel"
      >
        <Editor
          height="100%"
          defaultLanguage="handlebars"
          theme="vs-dark"
          value={template}
          onChange={handleChange}
          onMount={onMount}
          loading={
            <span className="caret p-3 font-mono text-xs text-neon-dim">
              loading editor
            </span>
          }
          options={{
            readOnly,
            ariaLabel: 'Prompt template editor',
            fontFamily:
              "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace",
            fontSize: 13,
            lineNumbers: 'on',
            minimap: { enabled: false },
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            renderWhitespace: 'none',
            tabSize: 2,
            automaticLayout: true,
            padding: { top: 8, bottom: 8 },
          }}
        />
      </div>
      <ProblemsStrip findings={findings} linting={linting} onJump={reveal} />
    </div>
  );
}

function ProblemsStrip({
  findings,
  linting,
  onJump,
}: {
  findings: LintFinding[];
  linting: boolean;
  onJump: (line: number) => void;
}) {
  return (
    <div className="shrink-0 pixel-inset rounded-pixel bg-bg">
      <div
        role="status"
        aria-live="polite"
        aria-label={linting ? 'Linting…' : `${findings.length} problems detected`}
        className="flex items-center gap-2 border-b border-border px-2 py-1"
      >
        <span className="font-mono text-[10px] uppercase tracking-widest text-ink-dim">
          Problems
        </span>
        <span className="font-mono text-[10px] text-ink-dim">
          {findings.length}
        </span>
        {linting && (
          <span className="caret font-mono text-[10px] text-neon-dim">linting</span>
        )}
      </div>
      <ul className="max-h-28 overflow-auto">
        {findings.length === 0 ? (
          <li className="px-2 py-1.5 font-mono text-[11px] text-neon-dim">
            No issues detected.
          </li>
        ) : (
          findings.map((f, i) => (
            <li key={`${f.line}-${f.col}-${i}`}>
              <button
                onClick={() => onJump(f.line)}
                className="flex w-full items-start gap-2 px-2 py-1 text-left font-mono text-[11px] text-ink hover:bg-violet/15"
              >
                <span
                  aria-hidden
                  className="mt-0.5 h-2 w-2 shrink-0 rounded-pixel"
                  style={{ background: LINT_COLOR[f.type] }}
                />
                <span className="shrink-0 text-ink-dim">
                  {f.line}:{f.col}
                </span>
                <span
                  className="shrink-0 uppercase"
                  style={{ color: LINT_COLOR[f.type] }}
                >
                  {LINT_LABEL[f.type]}
                </span>
                <span className="min-w-0 flex-1">{f.message}</span>
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

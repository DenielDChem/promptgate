// Map lint findings → Monaco markers, and lint types → the pixel palette.
// Color mapping (team-lead contract, §4):
//   stylistic    → amber/warning  (orange token)
//   determinism  → a blue
//   hallucination→ red
//
// Monaco's MarkerSeverity is used for the squiggle, but every type also carries
// a [type] tag in the hover message so the three kinds stay distinguishable
// even where two share a severity.

import type { editor, MarkerSeverity } from 'monaco-editor';
import type { LintFinding, LintType } from '@/lib/types';

/** Hex colors for problem dots / pills, keyed by lint type. */
export const LINT_COLOR: Record<LintType, string> = {
  stylistic: '#ff6b35', // --color-orange (amber/warning)
  determinism: '#4ea8ff', // blue
  hallucination: '#ff3b3b', // --color-red
};

export const LINT_LABEL: Record<LintType, string> = {
  stylistic: 'stylistic',
  determinism: 'determinism',
  hallucination: 'hallucination',
};

/**
 * Translate findings into Monaco markers. `severityEnum` is monaco's
 * `MarkerSeverity` object, passed in by the caller (the monaco instance is only
 * available at runtime via the editor `onMount` / loader).
 */
export function toMarkers(
  findings: LintFinding[],
  severityEnum: typeof MarkerSeverity,
): editor.IMarkerData[] {
  return findings.map((f) => {
    const tag = `[${LINT_LABEL[f.type]}]`;
    const suggestion = f.suggestion ? `\n→ ${f.suggestion}` : '';
    return {
      severity: monacoSeverity(f, severityEnum),
      startLineNumber: f.line,
      startColumn: f.col,
      endLineNumber: f.line,
      endColumn: f.end_col,
      message: `${tag} ${f.message}${suggestion}`,
      source: 'promptgate',
    };
  });
}

function monacoSeverity(
  f: LintFinding,
  S: typeof MarkerSeverity,
): MarkerSeverity {
  if (f.severity === 'error' || f.type === 'hallucination') return S.Error;
  if (f.severity === 'info') return S.Info;
  return S.Warning;
}

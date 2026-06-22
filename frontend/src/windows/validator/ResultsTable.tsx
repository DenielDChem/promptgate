// Per-case results table for a validation run: question → answer → score, with
// a hallucination grade per row. A flagged block (the slice the judge marked) is
// highlighted beneath the answer so the user can see exactly what tripped it.

import { ColorDot } from '@/components/ColorDot';
import { gradeComprehension, gradeHallucination } from '@/lib/quality';
import type { ValidationCaseResult } from '@/lib/types';

export function ResultsTable({ cases }: { cases: ValidationCaseResult[] }) {
  if (cases.length === 0) {
    return (
      <p className="p-3 text-center font-mono text-xs text-ink-dim">
        No per-case results returned.
      </p>
    );
  }
  return (
    <table className="w-full border-collapse font-mono text-xs">
      <thead className="sticky top-0 z-10 bg-card text-[10px] uppercase tracking-wide text-ink-dim">
        <tr>
          <Th className="w-1/3">Question</Th>
          <Th>Answer</Th>
          <Th className="w-16 text-right">Score</Th>
          <Th className="w-20 text-right">Halluc.</Th>
        </tr>
      </thead>
      <tbody>
        {cases.map((c, i) => (
          <tr key={i} className="border-b border-border align-top text-ink">
            <td className="px-2 py-1.5 text-ink-dim">{c.question}</td>
            <td className="px-2 py-1.5">
              <p className="whitespace-pre-wrap">{c.answer}</p>
              {c.flagged_block && (
                <p
                  className="pixel-inset rounded-pixel mt-1 bg-bg px-1.5 py-1 text-[11px] text-red"
                  title="Flagged by the hallucination judge"
                >
                  ⚑ {c.flagged_block}
                </p>
              )}
            </td>
            <td className="px-2 py-1.5 text-right">
              <span className="inline-flex items-center justify-end gap-1.5">
                <ColorDot color={gradeComprehension(c.score)} metric="score" />
                {c.score.toFixed(1)}
              </span>
            </td>
            <td className="px-2 py-1.5 text-right">
              <span className="inline-flex items-center justify-end gap-1.5">
                <ColorDot
                  color={gradeHallucination(c.hallucination)}
                  metric="hallucination"
                />
                {c.hallucination.toFixed(1)}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Th({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <th className={`px-2 py-1.5 text-left font-normal ${className}`}>{children}</th>;
}

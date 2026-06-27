// `quality` window body — the cross-prompt quality dashboard (P3 §8.2).
// Top widgets (avg score, avg hallucination, prompts checked) + a graded table.
// Clicking a row swaps to that prompt's run history (reusing the validator
// store's history slice + RunHistory + ResultPanel-style detail).

import { useEffect, useState } from 'react';
import { useValidatorStore } from '@/stores/validatorStore';
import { ColorDot } from '@/components/ColorDot';
import { PixelButton } from '@/components/PixelButton';
import { StatCard } from '@/components/StatCard';
import { ModuleHeader } from '@/components/ModuleHeader';
import { Th, interactiveRowProps } from '@/components/DataTable';
import { gradeQuality } from '@/lib/quality';
import { ResultsTable } from './validator/ResultsTable';
import type { QualityRow } from '@/lib/types';

export function QualityModule() {
  const dashboard = useValidatorStore((s) => s.dashboard);
  const loading = useValidatorStore((s) => s.dashboardLoading);
  const error = useValidatorStore((s) => s.dashboardError);
  const loadDashboard = useValidatorStore((s) => s.loadDashboard);

  // null = dashboard view; otherwise the prompt whose history we're inspecting.
  const [selected, setSelected] = useState<QualityRow | null>(null);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  if (selected) {
    return <PromptDetail row={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <ModuleHeader title="Quality" count={dashboard.length}>
        <PixelButton
          onClick={() => void loadDashboard()}
          aria-label="Refresh dashboard"
          className="ml-auto"
        >
          ↻
        </PixelButton>
      </ModuleHeader>

      {error && (
        <p
          role="alert"
          className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs text-red"
        >
          {error}
        </p>
      )}

      <Widgets rows={dashboard} />

      <div className="pixel-inset rounded-pixel min-h-0 flex-1 overflow-auto bg-bg">
        {loading ? (
          <p className="p-4 text-center font-mono text-xs text-ink-dim">
            <span className="caret">loading quality</span>
          </p>
        ) : dashboard.length === 0 ? (
          <EmptyState />
        ) : (
          <QualityTable rows={dashboard} onSelect={setSelected} />
        )}
      </div>
    </div>
  );
}

function Widgets({ rows }: { rows: QualityRow[] }) {
  const checked = rows.length;
  const avgScore = checked ? mean(rows.map((r) => r.avg_score)) : 0;
  const avgHalluc = checked ? mean(rows.map((r) => r.hallucination)) : 0;
  return (
    <div className="grid shrink-0 grid-cols-3 gap-2">
      <Widget label="Avg score" value={checked ? avgScore.toFixed(1) : '—'} />
      <Widget
        label="Avg halluc."
        value={checked ? avgHalluc.toFixed(1) : '—'}
        warn
      />
      <Widget label="Prompts checked" value={String(checked)} />
    </div>
  );
}

function Widget({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <StatCard
      label={label}
      value={value}
      valueClassName={warn ? 'text-orange' : 'text-ink'}
    />
  );
}

function QualityTable({
  rows,
  onSelect,
}: {
  rows: QualityRow[];
  onSelect: (row: QualityRow) => void;
}) {
  return (
    <table className="w-full border-collapse font-mono text-xs tabular-nums">
      <thead className="sticky top-0 z-10 bg-card text-[10px] uppercase tracking-wide text-ink-dim">
        <tr>
          <Th />
          <Th>Name</Th>
          <Th className="text-right">Runs</Th>
          <Th className="text-right">Avg score</Th>
          <Th className="text-right">Halluc.</Th>
          <Th className="text-right">Determ.</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr
            key={r.prompt_id}
            {...interactiveRowProps(`View quality history for ${r.name}`, () => onSelect(r))}
          >
            <td className="px-2 py-1.5">
              <ColorDot color={r.color} metric={r.name} />
            </td>
            <td className="px-2 py-1.5">
              {r.name}
              <span className="ml-1 text-ink-dim">({r.prompt_id})</span>
            </td>
            <td className="px-2 py-1.5 text-right text-ink-dim">{r.n_validations}</td>
            <td className="px-2 py-1.5 text-right">{r.avg_score.toFixed(1)}</td>
            <td className="px-2 py-1.5 text-right">{r.hallucination.toFixed(1)}</td>
            <td className="px-2 py-1.5 text-right text-ink-dim">
              {Math.round(r.determinism)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** A selected prompt's run history + most-recent run detail. */
function PromptDetail({ row, onBack }: { row: QualityRow; onBack: () => void }) {
  const runs = useValidatorStore((s) => s.runs);
  const runsLoading = useValidatorStore((s) => s.runsLoading);
  const result = useValidatorStore((s) => s.result);
  const loadRuns = useValidatorStore((s) => s.loadRuns);
  const viewRun = useValidatorStore((s) => s.viewRun);
  const clearResult = useValidatorStore((s) => s.clearResult);

  useEffect(() => {
    clearResult();
    void loadRuns(row.prompt_id);
  }, [row.prompt_id, loadRuns, clearResult]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 items-center gap-2">
        <PixelButton onClick={onBack} aria-label="Back to dashboard">
          ← Back
        </PixelButton>
        <ColorDot color={row.color} className="h-3 w-3" />
        <h2 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
          {row.name}
        </h2>
        <span className="font-mono text-[11px] text-ink-dim">({row.prompt_id})</span>
      </div>

      <div className="pixel-inset rounded-pixel max-h-44 shrink-0 overflow-auto bg-bg">
        {runsLoading ? (
          <p className="p-3 text-center font-mono text-[11px] text-ink-dim">
            <span className="caret">loading runs</span>
          </p>
        ) : runs.length === 0 ? (
          <p className="p-3 text-center font-mono text-[11px] text-ink-dim">
            No runs recorded for this prompt.
          </p>
        ) : (
          <ul className="divide-y divide-border font-mono text-[11px]">
            {runs.map((r) => (
              <li key={r.run_id}>
                <button
                  onClick={() => void viewRun(r.run_id)}
                  className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-ink hover:bg-violet/15 focus:bg-violet/20"
                >
                  <ColorDot color={gradeQuality(r.comprehension, r.hallucination)} />
                  <span className="text-ink-dim">{formatDate(r.created_at)}</span>
                  <span className="text-violet-bright">{r.model_id}</span>
                  <span className="ml-auto text-ink-dim">
                    {r.comprehension.toFixed(1)}/{r.hallucination.toFixed(1)} ·{' '}
                    {Math.round(r.determinism)}%
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="pixel-inset rounded-pixel min-h-0 flex-1 overflow-auto bg-bg">
        {result ? (
          <ResultsTable cases={result.cases} />
        ) : (
          <p className="p-4 text-center font-mono text-xs text-ink-dim">
            Select a run above to see its graded answers.
          </p>
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="text-4xl text-violet-bright" aria-hidden>
        ▥
      </span>
      <p className="font-mono text-xs text-ink-dim">
        No validated prompts yet. Run a validation to populate the dashboard.
      </p>
    </div>
  );
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

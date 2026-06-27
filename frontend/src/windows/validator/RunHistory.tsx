// Past validation runs for the currently selected prompt. Each row is clickable
// and loads the full run (cases included) into the result panel.

import { useValidatorStore } from '@/stores/validatorStore';
import { ColorDot } from '@/components/ColorDot';
import { gradeQuality } from '@/lib/quality';
import type { ValidationRunSummary } from '@/lib/types';

export function RunHistory() {
  const runs = useValidatorStore((s) => s.runs);
  const loading = useValidatorStore((s) => s.runsLoading);
  const promptId = useValidatorStore((s) => s.promptId);
  const viewRun = useValidatorStore((s) => s.viewRun);

  if (!promptId) return null;

  return (
    <div className="flex min-h-0 flex-col gap-1">
      <h3 className="font-mono text-[11px] uppercase tracking-widest text-ink-dim">
        Past runs ({runs.length})
      </h3>
      <div className="pixel-inset rounded-pixel max-h-40 min-h-0 overflow-auto bg-bg">
        {loading ? (
          <p className="p-3 text-center font-mono text-[11px] text-ink-dim">
            <span className="caret">loading history</span>
          </p>
        ) : runs.length === 0 ? (
          <p className="p-3 text-center font-mono text-[11px] text-ink-dim">
            No runs yet for this prompt.
          </p>
        ) : (
          <ul className="divide-y divide-border font-mono text-[11px]">
            {runs.map((r) => (
              <RunRow key={r.run_id} run={r} onClick={() => void viewRun(r.run_id)} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function RunRow({ run, onClick }: { run: ValidationRunSummary; onClick: () => void }) {
  return (
    <li>
      <button
        onClick={onClick}
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-ink hover:bg-violet/15 focus:bg-violet/20"
      >
        <ColorDot color={gradeQuality(run.comprehension, run.hallucination)} />
        <span className="text-ink-dim">{formatDate(run.created_at)}</span>
        <span className="text-violet-bright">{run.model_id}</span>
        <span className="ml-auto text-ink-dim">
          {run.comprehension.toFixed(1)}/{run.hallucination.toFixed(1)} ·{' '}
          {Math.round(run.determinism)}%
        </span>
      </button>
    </li>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

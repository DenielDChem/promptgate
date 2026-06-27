// Right column of the Validator: a terminal-style running state, the run error,
// or — on success — the overall grade + metric cards + per-case results table.

import { useValidatorStore } from '@/stores/validatorStore';
import { ColorDot } from '@/components/ColorDot';
import { PixelButton } from '@/components/PixelButton';
import { MetricCards } from './MetricCards';
import { ResultsTable } from './ResultsTable';
import { RunHistory } from './RunHistory';

export function ResultPanel() {
  const running = useValidatorStore((s) => s.running);
  const result = useValidatorStore((s) => s.result);
  const runError = useValidatorStore((s) => s.runError);
  const clearResult = useValidatorStore((s) => s.clearResult);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {running ? (
        <RunningState />
      ) : runError ? (
        <p
          role="alert"
          className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs text-red"
        >
          {runError}
        </p>
      ) : result ? (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="flex shrink-0 items-center gap-2">
            <ColorDot color={result.color} className="h-3 w-3" />
            <h2 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
              Result
            </h2>
            <span className="font-mono text-[11px] text-ink-dim">
              {result.model_id} · {result.n_cases} case
              {result.n_cases === 1 ? '' : 's'}
            </span>
            <PixelButton
              onClick={clearResult}
              className="ml-auto px-2 py-0.5 text-[11px]"
            >
              Clear
            </PixelButton>
          </div>
          <MetricCards run={result} />
          <div className="pixel-inset rounded-pixel min-h-0 flex-1 overflow-auto bg-bg">
            <ResultsTable cases={result.cases} />
          </div>
        </div>
      ) : (
        <EmptyResult />
      )}

      <RunHistory />
    </div>
  );
}

function RunningState() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Validation running"
      className="pixel-inset rounded-pixel flex min-h-0 flex-1 flex-col gap-1 overflow-auto bg-bg p-3 font-mono text-xs"
    >
      <p className="text-neon-dim">$ pgate validate --deep</p>
      <p className="text-ink-dim">› spinning up runner…</p>
      <p className="text-ink-dim">› sampling answers across repeats…</p>
      <p className="text-ink-dim">› scoring comprehension &amp; grounding…</p>
      <p className="text-neon">
        <span className="caret">working</span>
      </p>
    </div>
  );
}

function EmptyResult() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <span className="text-5xl text-violet-bright" aria-hidden>
        ◉
      </span>
      <p className="max-w-xs font-mono text-xs text-ink-dim">
        Pick a prompt and model, author a test set, then run a deep validation to
        see determinism, comprehension, hallucination &amp; latency.
      </p>
    </div>
  );
}

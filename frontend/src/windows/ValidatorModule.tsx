// `validator` window body — the deep-validation module (P3 §4).
// Two columns: the run form (left) and the running/result + history (right).
// Mounted by Desktop in place of ModulePlaceholder.

import { ValidatorForm } from './validator/ValidatorForm';
import { ResultPanel } from './validator/ResultPanel';

export function ValidatorModule() {
  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex shrink-0 items-center gap-2">
        <h2 className="font-mono text-sm uppercase tracking-widest text-neon-dim">
          Validator
        </h2>
        <span className="font-mono text-[11px] text-ink-dim">deep validation</span>
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 md:grid-cols-2">
        <section className="pixel-inset rounded-pixel min-h-0 bg-bg p-3">
          <ValidatorForm />
        </section>
        <section className="min-h-0">
          <ResultPanel />
        </section>
      </div>
    </div>
  );
}

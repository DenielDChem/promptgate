// Validator run form: prompt + model pickers, test-set editor, repeats, Run.
// Run is gated by RBAC (`validate.run`) — disabled & explained for guests.

import { useEffect } from 'react';
import { useValidatorStore } from '@/stores/validatorStore';
import { useAuthStore } from '@/stores/authStore';
import { canRunValidation } from '@/lib/rbac';
import { PixelButton } from '@/components/PixelButton';
import { PixelSelect } from '@/components/PixelSelect';

export function ValidatorForm() {
  const role = useAuthStore((s) => s.user?.role ?? 'guest');
  const mayRun = canRunValidation(role);

  const prompts = useValidatorStore((s) => s.prompts);
  const models = useValidatorStore((s) => s.models);
  const lookupsLoading = useValidatorStore((s) => s.lookupsLoading);
  const lookupError = useValidatorStore((s) => s.lookupError);
  const promptId = useValidatorStore((s) => s.promptId);
  const modelId = useValidatorStore((s) => s.modelId);
  const cases = useValidatorStore((s) => s.cases);
  const repeats = useValidatorStore((s) => s.repeats);
  const running = useValidatorStore((s) => s.running);

  const loadLookups = useValidatorStore((s) => s.loadLookups);
  const setPromptId = useValidatorStore((s) => s.setPromptId);
  const setModelId = useValidatorStore((s) => s.setModelId);
  const setRepeats = useValidatorStore((s) => s.setRepeats);
  const setCase = useValidatorStore((s) => s.setCase);
  const addCase = useValidatorStore((s) => s.addCase);
  const removeCase = useValidatorStore((s) => s.removeCase);
  const run = useValidatorStore((s) => s.run);
  const cancelRun = useValidatorStore((s) => s.cancelRun);

  useEffect(() => {
    void loadLookups();
  }, [loadLookups]);

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto pr-1">
      {lookupError && (
        <p
          role="alert"
          className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs text-red"
        >
          {lookupError}
        </p>
      )}

      {/* Pickers */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <PixelSelect
          label="Prompt"
          value={promptId}
          disabled={lookupsLoading}
          onChange={setPromptId}
          options={prompts.map((p) => ({ value: p.id, label: `${p.name} (${p.id})` }))}
          placeholder={lookupsLoading ? 'loading…' : 'no prompts'}
        />
        <PixelSelect
          label="Model"
          value={modelId}
          disabled={lookupsLoading}
          onChange={setModelId}
          options={models.map((m) => ({ value: m, label: m }))}
          placeholder={lookupsLoading ? 'loading…' : 'no models'}
        />
      </div>

      {/* Test-set editor */}
      <fieldset className="flex min-h-0 flex-col gap-1.5">
        <legend className="flex w-full items-center gap-2 font-mono text-xs uppercase tracking-wide text-ink-dim">
          Test set
          <span className="text-[10px] normal-case text-ink-dim/70">
            (leave all blank to use the default set)
          </span>
          <PixelButton
            type="button"
            onClick={addCase}
            className="ml-auto px-2 py-0.5 text-[11px]"
            aria-label="Add test case"
          >
            + Case
          </PixelButton>
        </legend>
        <div className="flex flex-col gap-1.5">
          {cases.map((c, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <span className="mt-2 w-5 shrink-0 text-right font-mono text-[11px] text-ink-dim">
                {i + 1}.
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <input
                  value={c.question}
                  onChange={(e) => setCase(i, { question: e.target.value })}
                  placeholder="Question to ask the prompt…"
                  aria-label={`Test case ${i + 1} question`}
                  className="pixel-inset rounded-pixel w-full bg-bg px-2.5 py-1.5 font-mono text-sm text-ink placeholder:text-ink-dim/60"
                />
                <input
                  value={c.payload ?? ''}
                  onChange={(e) => setCase(i, { payload: e.target.value })}
                  placeholder="Optional payload / context…"
                  aria-label={`Test case ${i + 1} payload`}
                  className="pixel-inset rounded-pixel w-full bg-bg px-2.5 py-1 font-mono text-xs text-ink-dim placeholder:text-ink-dim/50"
                />
              </div>
              <button
                type="button"
                onClick={() => removeCase(i)}
                aria-label={`Remove test case ${i + 1}`}
                className="mt-1 rounded-pixel px-1.5 py-0.5 font-mono text-ink-dim hover:bg-red hover:text-white"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </fieldset>

      {/* Run row */}
      <div className="mt-auto flex shrink-0 items-end gap-3 pt-1">
        <label className="flex flex-col gap-1">
          <span className="font-mono text-xs uppercase tracking-wide text-ink-dim">
            Repeats
          </span>
          <input
            type="number"
            min={1}
            max={10}
            value={repeats}
            onChange={(e) => setRepeats(Number(e.target.value))}
            aria-label="Repeats per case"
            className="pixel-inset rounded-pixel w-20 bg-bg px-2.5 py-1.5 font-mono text-sm text-ink"
          />
        </label>
        <div className="ml-auto flex flex-col items-end gap-1">
          {!mayRun && (
            <span className="font-mono text-[10px] text-orange">
              {role} cannot run validations
            </span>
          )}
          {running ? (
            <PixelButton variant="danger" onClick={cancelRun}>
              ■ Cancel
            </PixelButton>
          ) : (
            <PixelButton
              variant="primary"
              onClick={() => void run()}
              disabled={!mayRun || !promptId || !modelId}
            >
              ▶ Run validation
            </PixelButton>
          )}
        </div>
      </div>
    </div>
  );
}


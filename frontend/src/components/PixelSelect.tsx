// Labelled, inset (recessed) <select> — the shared pixel form primitive used by
// the Validator run form and the Create-job modal. Supports a disabled state, a
// placeholder option when there are no choices, and an invalid state that wires
// up aria-invalid + an aria-describedby hint (orange ring for sighted users).

import { useId } from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

interface PixelSelectProps {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  invalid?: boolean;
  invalidHint?: string;
}

export function PixelSelect({
  label,
  value,
  options,
  onChange,
  disabled,
  placeholder,
  invalid,
  invalidHint,
}: PixelSelectProps) {
  const hintId = useId();
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="font-mono text-xs uppercase tracking-wide text-ink-dim">
        {label}
      </span>
      <select
        value={value}
        disabled={disabled || options.length === 0}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid && invalidHint ? hintId : undefined}
        onChange={(e) => onChange(e.target.value)}
        className={[
          'pixel-inset rounded-pixel bg-bg px-2.5 py-1.5 font-mono text-sm text-ink disabled:opacity-50',
          invalid ? 'ring-1 ring-orange' : '',
        ].join(' ')}
      >
        {options.length === 0 && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {invalid && invalidHint && (
        <span id={hintId} className="font-mono text-[10px] text-orange">
          {invalidHint}
        </span>
      )}
    </label>
  );
}

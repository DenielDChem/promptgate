import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { useId } from 'react';

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

/** Labelled, inset (recessed) text input — accessible label association. */
export function PixelField({ label, className = '', ...rest }: FieldProps) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex flex-col gap-1">
      <span className="font-mono text-xs uppercase tracking-wide text-ink-dim">
        {label}
      </span>
      <input
        id={id}
        {...rest}
        className={[
          'pixel-inset rounded-pixel bg-bg px-2.5 py-1.5 font-mono text-sm text-ink',
          'placeholder:text-ink-dim/60',
          className,
        ].join(' ')}
      />
    </label>
  );
}

interface AreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
}

export function PixelTextArea({ label, className = '', ...rest }: AreaProps) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex flex-col gap-1">
      <span className="font-mono text-xs uppercase tracking-wide text-ink-dim">
        {label}
      </span>
      <textarea
        id={id}
        {...rest}
        className={[
          'pixel-inset rounded-pixel resize-none bg-bg px-2.5 py-1.5 font-mono text-sm text-ink',
          'placeholder:text-ink-dim/60',
          className,
        ].join(' ')}
      />
    </label>
  );
}

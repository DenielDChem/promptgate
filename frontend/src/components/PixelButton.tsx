import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'default' | 'primary' | 'action' | 'danger';

interface PixelButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  children: ReactNode;
}

const VARIANT_CLASS: Record<Variant, string> = {
  default: 'bg-card text-ink hover:brightness-125',
  primary: 'bg-neon-dim text-bg font-semibold hover:brightness-110',
  action: 'bg-violet text-white font-semibold hover:brightness-110',
  danger: 'bg-red text-white font-semibold hover:brightness-110',
};

/** Win95-style raised button with hard bevels; presses to inset on :active. */
export function PixelButton({
  variant = 'default',
  className = '',
  children,
  ...rest
}: PixelButtonProps) {
  return (
    <button
      {...rest}
      className={[
        'pixel-raised active:pixel-inset active:translate-y-px',
        'rounded-pixel px-3 py-1.5 text-sm transition-[filter,box-shadow]',
        'disabled:cursor-not-allowed disabled:opacity-50 disabled:active:translate-y-0',
        'font-mono uppercase tracking-wide',
        VARIANT_CLASS[variant],
        className,
      ].join(' ')}
    >
      {children}
    </button>
  );
}

// Traffic-light grade dot shared by the Validator metric cards and the Quality
// dashboard. Maps a ValidationColor to a theme token + an accessible label.

import type { ValidationColor } from '@/lib/types';

const COLOR_CLASS: Record<ValidationColor, string> = {
  green: 'bg-neon',
  yellow: 'bg-orange',
  red: 'bg-red',
};

const COLOR_LABEL: Record<ValidationColor, string> = {
  green: 'good',
  yellow: 'fair',
  red: 'poor',
};

interface ColorDotProps {
  color: ValidationColor;
  /** Extra context for the screen-reader label, e.g. "comprehension". */
  metric?: string;
  className?: string;
}

export function ColorDot({ color, metric, className = '' }: ColorDotProps) {
  const label = metric ? `${metric}: ${COLOR_LABEL[color]}` : COLOR_LABEL[color];
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={[
        'inline-block h-2.5 w-2.5 shrink-0 rounded-full',
        COLOR_CLASS[color],
        className,
      ].join(' ')}
    />
  );
}

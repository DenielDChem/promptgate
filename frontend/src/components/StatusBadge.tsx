// Draft / published pill — pixel-styled, used in the prompts list + inspector.

import type { PromptStatus } from '@/lib/types';

const STYLE: Record<PromptStatus, string> = {
  draft: 'bg-card text-ink-dim',
  published: 'bg-neon-dim text-bg',
};

export function StatusBadge({ status }: { status: PromptStatus }) {
  return (
    <span
      className={[
        'pixel-raised rounded-pixel px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide',
        STYLE[status],
      ].join(' ')}
    >
      {status}
    </span>
  );
}

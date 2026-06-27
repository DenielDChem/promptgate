// Draft / published pill — pixel-styled, used in the prompts list + inspector.

import { StatusPill } from '@/components/StatusPill';
import type { PromptStatus } from '@/lib/types';

const STYLE: Record<PromptStatus, string> = {
  draft: 'bg-card text-ink-dim',
  published: 'bg-neon-dim text-bg',
};

export function StatusBadge({ status }: { status: PromptStatus }) {
  return <StatusPill className={STYLE[status]}>{status}</StatusPill>;
}

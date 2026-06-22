// `my-prompts` window body. Swaps between the list and the 3-pane editor based
// on the prompts store view. Mounted by Desktop in place of ModulePlaceholder.
//
// The editor (which pulls in Monaco — a large chunk) is lazy-loaded so opening
// the desktop / browsing the list never downloads the editor bundle.

import { lazy, Suspense } from 'react';
import { usePromptsStore } from '@/stores/promptsStore';
import { PromptsList } from './prompts/PromptsList';

const PromptEditor = lazy(() =>
  import('./prompts/PromptEditor').then((m) => ({ default: m.PromptEditor })),
);

export function PromptsModule() {
  const view = usePromptsStore((s) => s.view);
  if (view !== 'editor') return <PromptsList />;
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center">
          <span className="caret font-mono text-xs text-neon-dim">
            loading editor
          </span>
        </div>
      }
    >
      <PromptEditor />
    </Suspense>
  );
}

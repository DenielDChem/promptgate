// Per-window store scope. Every open window mounts one of these, giving it its
// own isolated prompts / validator / jobs store instance — so two prompt
// editors (or two queues) can run side by side without sharing draft, run, or
// polling state. Global stores (auth, windows, toasts) stay singletons.
//
// Also exposes the window's id via context so window-scoped concerns (e.g. the
// unsaved-edits close guard) can register themselves per instance.

import { createContext, useContext, useState, type ReactNode } from 'react';
import { createPromptsStore, PromptsStoreProvider } from './promptsStore';
import { createValidatorStore, ValidatorStoreProvider } from './validatorStore';
import { createJobsStore, JobsStoreProvider } from './jobsStore';

const WindowInstanceContext = createContext<string | null>(null);

/** The current window's id (throws outside a window body). */
export function useWindowId(): string {
  const id = useContext(WindowInstanceContext);
  if (!id) throw new Error('useWindowId used outside a window');
  return id;
}

export function ModuleStoresProvider({
  windowId,
  children,
}: {
  windowId: string;
  children: ReactNode;
}) {
  // Lazy-init once per window mount — the factory runs a single time.
  const [prompts] = useState(createPromptsStore);
  const [validator] = useState(createValidatorStore);
  const [jobs] = useState(createJobsStore);

  return (
    <WindowInstanceContext.Provider value={windowId}>
      <PromptsStoreProvider value={prompts}>
        <ValidatorStoreProvider value={validator}>
          <JobsStoreProvider value={jobs}>{children}</JobsStoreProvider>
        </ValidatorStoreProvider>
      </PromptsStoreProvider>
    </WindowInstanceContext.Provider>
  );
}

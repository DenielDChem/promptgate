// Desktop shell: 24px grid + scanline/noise overlay, RBAC-filtered icons,
// right-click context menu, rendered windows, and the taskbar.

import { useEffect, useState } from 'react';
import { useWindowStore } from '@/stores/windowStore';
import { useAuthStore } from '@/stores/authStore';
import { visibleModules } from '@/lib/rbac';
import { DesktopIcon } from './DesktopIcon';
import { ContextMenu, type MenuPos } from './ContextMenu';
import { Taskbar } from './Taskbar';
import { Toaster } from '@/components/Toaster';
import { OnboardingTour, tourCompleted } from '@/components/OnboardingTour';
import { Window } from '@/components/Window';
import { ModulePlaceholder } from '@/windows/ModulePlaceholder';
import { PromptsModule } from '@/windows/PromptsModule';
import { ValidatorModule } from '@/windows/ValidatorModule';
import { QualityModule } from '@/windows/QualityModule';
import { QueueModule } from '@/windows/QueueModule';
import type { ModuleId } from '@/lib/types';

/** Body renderer per module — built modules get their window, the rest fall
 * back to the P2+ placeholder. */
function ModuleBody({ module }: { module: ModuleId }) {
  if (module === 'my-prompts') return <PromptsModule />;
  if (module === 'validator') return <ValidatorModule />;
  if (module === 'quality') return <QualityModule />;
  if (module === 'queue') return <QueueModule />;
  return <ModulePlaceholder module={module} />;
}

export function Desktop() {
  const windows = useWindowStore((s) => s.windows);
  const clampIntoView = useWindowStore((s) => s.clampIntoView);
  const role = useAuthStore((s) => s.user?.role ?? 'guest');
  const modules = visibleModules(role);

  // Keep windows reachable when the viewport shrinks (resize / device rotate).
  useEffect(() => {
    const onResize = () => clampIntoView();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [clampIntoView]);

  const [menu, setMenu] = useState<MenuPos | null>(null);
  // Forces the grid overlay to "blink" on Refresh — purely cosmetic.
  const [refreshKey, setRefreshKey] = useState(0);

  // Guided tour: auto-run on first visit; replayable from the context menu.
  const [tourOpen, setTourOpen] = useState(() => !tourCompleted());

  // First-run nudge: shown until the user opens their first window, then
  // remembered so it never reappears.
  const [showHint, setShowHint] = useState(() => {
    try {
      return !localStorage.getItem('pg.onboarded');
    } catch {
      return true;
    }
  });
  useEffect(() => {
    if (windows.length > 0 && showHint) {
      setShowHint(false);
      try {
        localStorage.setItem('pg.onboarded', '1');
      } catch {
        /* private mode — hint just won't persist */
      }
    }
  }, [windows.length, showHint]);

  return (
    <div className="flex h-full w-full flex-col">
      <h1 className="sr-only">PromptGate desktop</h1>
      <main
        key={refreshKey}
        className="scanlines noise desktop-grid relative min-h-0 flex-1 overflow-hidden bg-bg"
        onContextMenu={(e) => {
          e.preventDefault();
          setMenu({ x: e.clientX, y: e.clientY });
        }}
        onClick={() => setMenu(null)}
      >
        {/* Icon column */}
        <div className="absolute left-3 top-3 z-10 flex flex-col flex-wrap gap-1">
          {modules.map((m) => (
            <DesktopIcon key={m} module={m} />
          ))}
        </div>

        {/* First-run hint (suppressed while the tour is up) */}
        {!tourOpen && showHint && windows.length === 0 && (
          <div className="pointer-events-none absolute inset-0 z-[6] flex items-center justify-center p-4">
            <div className="pixel-raised rounded-pixel max-w-xs bg-card/90 px-4 py-3 text-center font-mono text-xs text-ink-dim terminal-print">
              <p className="mb-1 text-neon-dim">▣ Welcome to PromptGate</p>
              <p>
                Open a tool from the <span className="text-violet-bright">desktop icons</span> on the
                left or the <span className="text-violet-bright">Start menu</span> below.
              </p>
            </div>
          </div>
        )}

        {/* Windows */}
        {windows.map((w) => (
          <Window key={w.id} win={w}>
            <ModuleBody module={w.module} />
          </Window>
        ))}

        {/* Context menu */}
        {menu && (
          <ContextMenu
            pos={menu}
            onClose={() => setMenu(null)}
            onRefresh={() => {
              setRefreshKey((k) => k + 1);
              setMenu(null);
            }}
            onTour={() => {
              setTourOpen(true);
              setMenu(null);
            }}
          />
        )}
      </main>

      <Taskbar />
      <Toaster />
      {tourOpen && <OnboardingTour onClose={() => setTourOpen(false)} />}
    </div>
  );
}

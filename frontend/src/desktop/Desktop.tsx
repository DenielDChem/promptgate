// Desktop shell: 24px grid + scanline/noise overlay, RBAC-filtered icons,
// right-click context menu, rendered windows, and the taskbar.

import { useState } from 'react';
import { useWindowStore } from '@/stores/windowStore';
import { useAuthStore } from '@/stores/authStore';
import { visibleModules } from '@/lib/rbac';
import { DesktopIcon } from './DesktopIcon';
import { ContextMenu, type MenuPos } from './ContextMenu';
import { Taskbar } from './Taskbar';
import { Window } from '@/components/Window';
import { ModulePlaceholder } from '@/windows/ModulePlaceholder';
import { PromptsModule } from '@/windows/PromptsModule';
import type { ModuleId } from '@/lib/types';

/** Body renderer per module — built modules get their window, the rest fall
 * back to the P2+ placeholder. */
function ModuleBody({ module }: { module: ModuleId }) {
  if (module === 'my-prompts') return <PromptsModule />;
  return <ModulePlaceholder module={module} />;
}

export function Desktop() {
  const windows = useWindowStore((s) => s.windows);
  const role = useAuthStore((s) => s.user?.role ?? 'guest');
  const modules = visibleModules(role);

  const [menu, setMenu] = useState<MenuPos | null>(null);
  // Forces the grid overlay to "blink" on Refresh — purely cosmetic.
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="flex h-full w-full flex-col">
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
          />
        )}
      </main>

      <Taskbar />
    </div>
  );
}

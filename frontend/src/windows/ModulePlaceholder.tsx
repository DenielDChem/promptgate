// Placeholder body for modules not yet built (P2+). Keeps the desktop navigable.

import { MODULE_META } from '@/lib/modules';
import type { ModuleId } from '@/lib/types';
import { moduleAccess } from '@/lib/rbac';
import { useAuthStore } from '@/stores/authStore';

export function ModulePlaceholder({ module }: { module: ModuleId }) {
  const meta = MODULE_META[module];
  const role = useAuthStore((s) => s.user?.role ?? 'guest');
  const access = moduleAccess(role, module);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <span className="text-5xl text-violet" aria-hidden>
        {meta.glyph}
      </span>
      <h2 className="font-mono text-lg uppercase tracking-widest text-neon-dim">
        {meta.title}
      </h2>
      <p className="max-w-xs font-mono text-sm text-ink-dim">
        Coming in <span className="text-orange">P2+</span>. This module is
        scaffolded; functionality lands in a later phase.
      </p>
      {access.readOnly && (
        <span className="pixel-raised rounded-pixel bg-card px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-orange">
          read-only for {role}
        </span>
      )}
    </div>
  );
}

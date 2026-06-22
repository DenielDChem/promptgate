// A single desktop icon. Double-click opens the module window; single-click
// selects (keyboard: Enter opens, focusable). Disabled when access is denied.

import { useState } from 'react';
import { MODULE_META } from '@/lib/modules';
import type { ModuleId } from '@/lib/types';
import { useWindowStore } from '@/stores/windowStore';

export function DesktopIcon({ module }: { module: ModuleId }) {
  const meta = MODULE_META[module];
  const open = useWindowStore((s) => s.open);
  const [selected, setSelected] = useState(false);

  const launch = () => open(module, meta.title);

  return (
    <button
      onClick={() => setSelected(true)}
      onDoubleClick={launch}
      onBlur={() => setSelected(false)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') launch();
      }}
      aria-label={`Open ${meta.title}`}
      className={[
        'group flex w-20 flex-col items-center gap-1 rounded-pixel p-2 transition-colors',
        selected ? 'bg-violet/25 outline outline-1 outline-violet' : 'hover:bg-white/5',
      ].join(' ')}
    >
      <span
        aria-hidden
        className="pixel-raised flex h-8 w-8 items-center justify-center rounded-pixel bg-card text-xl text-neon-dim group-hover:text-neon"
      >
        {meta.glyph}
      </span>
      <span className="font-mono text-[11px] leading-tight text-ink drop-shadow-[1px_1px_0_rgba(0,0,0,0.8)]">
        {meta.title}
      </span>
    </button>
  );
}

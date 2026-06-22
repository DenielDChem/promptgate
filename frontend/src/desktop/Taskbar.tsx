// Bottom taskbar: Start button (PG logo) + start menu, open-window buttons,
// clock, current-user chip with logout.

import { useState } from 'react';
import { useWindowStore } from '@/stores/windowStore';
import { useAuthStore } from '@/stores/authStore';
import { visibleModules } from '@/lib/rbac';
import { MODULE_META } from '@/lib/modules';
import { Clock } from './Clock';
import { PixelButton } from '@/components/PixelButton';

export function Taskbar() {
  const windows = useWindowStore((s) => s.windows);
  const focusedId = useWindowStore((s) => s.focusedId);
  const toggleMinimize = useWindowStore((s) => s.toggleMinimize);
  const open = useWindowStore((s) => s.open);

  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [menuOpen, setMenuOpen] = useState(false);

  const modules = visibleModules(user?.role ?? 'guest');

  return (
    <footer className="pixel-raised relative z-[8000] flex h-10 shrink-0 items-center gap-2 border-t border-border bg-card px-2">
      {/* Start button */}
      <div className="relative">
        <button
          onClick={() => setMenuOpen((v) => !v)}
          aria-expanded={menuOpen}
          aria-label="Start menu"
          className="pixel-raised flex items-center gap-1.5 rounded-pixel bg-violet px-3 py-1 font-mono text-sm font-bold text-white active:pixel-inset"
        >
          <span className="text-neon">▣</span> PG
        </button>

        {menuOpen && (
          <ul
            role="menu"
            className="pixel-raised absolute bottom-11 left-0 min-w-48 rounded-pixel border border-border bg-card py-1 font-mono text-xs"
            onMouseLeave={() => setMenuOpen(false)}
          >
            <li className="border-b border-border px-3 py-1.5 text-[10px] uppercase tracking-widest text-ink-dim">
              PromptGate
            </li>
            {modules.map((m) => (
              <li key={m} role="menuitem">
                <button
                  onClick={() => {
                    open(m, MODULE_META[m].title);
                    setMenuOpen(false);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1 text-left uppercase tracking-wide text-ink hover:bg-violet hover:text-white"
                >
                  <span aria-hidden className="text-neon-dim">
                    {MODULE_META[m].glyph}
                  </span>
                  {MODULE_META[m].title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="h-6 w-px bg-border" aria-hidden />

      {/* Open windows */}
      <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        {windows.map((w) => (
          <button
            key={w.id}
            onClick={() => toggleMinimize(w.id)}
            className={[
              'max-w-44 shrink-0 truncate rounded-pixel px-3 py-1 font-mono text-xs uppercase tracking-wide',
              w.id === focusedId && !w.minimized
                ? 'pixel-inset bg-bg text-neon'
                : 'pixel-raised bg-card text-ink hover:brightness-125',
            ].join(' ')}
          >
            {MODULE_META[w.module].glyph} {w.title}
          </button>
        ))}
      </div>

      <Clock />

      {/* User chip */}
      {user && (
        <div className="flex items-center gap-2">
          <span className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs">
            <span className="text-ink-dim">{user.username}</span>
            <span className="ml-1.5 text-[10px] uppercase text-violet">
              [{user.role}]
            </span>
          </span>
          <PixelButton variant="danger" onClick={() => void logout()}>
            Exit
          </PixelButton>
        </div>
      )}
    </footer>
  );
}

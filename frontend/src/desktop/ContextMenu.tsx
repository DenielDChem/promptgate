// Right-click desktop context menu (Refresh / Properties placeholders).

import { useEffect, useRef } from 'react';

export interface MenuPos {
  x: number;
  y: number;
}

interface ContextMenuProps {
  pos: MenuPos;
  onClose: () => void;
  onRefresh: () => void;
  onTour: () => void;
}

export function ContextMenu({ pos, onClose, onRefresh, onTour }: ContextMenuProps) {
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    // Named handlers so BOTH listeners are removed on cleanup (the keydown one
    // used to leak, accumulating on every right-click).
    const onClick = () => onClose();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('click', onClick);
    window.addEventListener('keydown', onKey);
    // Move focus into the menu so Esc / Enter work without a prior mouse hover.
    listRef.current?.querySelector<HTMLElement>('button:not([disabled])')?.focus();
    return () => {
      window.removeEventListener('click', onClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  return (
    <ul
      ref={listRef}
      role="menu"
      style={{ left: pos.x, top: pos.y, zIndex: 'var(--z-context-menu)' }}
      className="pixel-raised absolute min-w-40 rounded-pixel border border-border bg-card py-1 font-mono text-xs"
      onClick={(e) => e.stopPropagation()}
    >
      <MenuItem onClick={onRefresh}>Refresh</MenuItem>
      <MenuItem onClick={onTour}>Take the tour</MenuItem>
      <li role="separator" className="my-1 border-t border-border" />
      <MenuItem onClick={onClose} disabled>
        Properties…
      </MenuItem>
    </ul>
  );
}

function MenuItem({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <li role="menuitem">
      <button
        disabled={disabled}
        onClick={onClick}
        className="w-full px-3 py-1 text-left uppercase tracking-wide text-ink hover:bg-violet hover:text-white disabled:cursor-default disabled:text-ink-dim disabled:hover:bg-transparent"
      >
        {children}
      </button>
    </li>
  );
}

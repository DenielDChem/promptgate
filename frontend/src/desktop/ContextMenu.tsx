// Right-click desktop context menu (Refresh / Properties placeholders).

import { useEffect } from 'react';

export interface MenuPos {
  x: number;
  y: number;
}

interface ContextMenuProps {
  pos: MenuPos;
  onClose: () => void;
  onRefresh: () => void;
}

export function ContextMenu({ pos, onClose, onRefresh }: ContextMenuProps) {
  useEffect(() => {
    const close = () => onClose();
    window.addEventListener('click', close);
    window.addEventListener('keydown', (e) => e.key === 'Escape' && onClose());
    return () => {
      window.removeEventListener('click', close);
    };
  }, [onClose]);

  return (
    <ul
      role="menu"
      style={{ left: pos.x, top: pos.y, zIndex: 9999 }}
      className="pixel-raised absolute min-w-40 rounded-pixel border border-border bg-card py-1 font-mono text-xs"
      onClick={(e) => e.stopPropagation()}
    >
      <MenuItem onClick={onRefresh}>Refresh</MenuItem>
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

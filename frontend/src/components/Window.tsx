// Win95-style draggable + resizable window. Drag handled on the titlebar,
// resize on the bottom-right grip. Geometry is committed to the windowStore on
// pointer up (cheap) and tracked locally during the gesture for smoothness.

import { useCallback, useRef, useState, type ReactNode } from 'react';
import { useWindowStore, type WinState } from '@/stores/windowStore';

interface WindowProps {
  win: WinState;
  children: ReactNode;
}

const TASKBAR_H = 40;

export function Window({ win, children }: WindowProps) {
  const { focus, close, toggleMinimize, toggleMaximize, move, resize } =
    useWindowStore();
  const focused = useWindowStore((s) => s.focusedId === win.id);

  // Live geometry during a drag/resize gesture (avoids store churn per frame).
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const gesture = useRef<{ startX: number; startY: number; base: number; base2: number } | null>(
    null,
  );

  const rect = win.maximized
    ? { x: 0, y: 0, w: window.innerWidth, h: window.innerHeight - TASKBAR_H }
    : {
        x: drag?.x ?? win.rect.x,
        y: drag?.y ?? win.rect.y,
        w: size?.w ?? win.rect.w,
        h: size?.h ?? win.rect.h,
      };

  const onTitlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (win.maximized) return;
      focus(win.id);
      const target = e.currentTarget as HTMLElement;
      target.setPointerCapture(e.pointerId);
      gesture.current = {
        startX: e.clientX,
        startY: e.clientY,
        base: win.rect.x,
        base2: win.rect.y,
      };
    },
    [focus, win.id, win.maximized, win.rect.x, win.rect.y],
  );

  const onTitlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const g = gesture.current;
      if (!g) return;
      const nx = Math.max(0, g.base + (e.clientX - g.startX));
      const ny = Math.max(0, g.base2 + (e.clientY - g.startY));
      setDrag({ x: nx, y: ny });
    },
    [],
  );

  const onTitlePointerUp = useCallback(() => {
    if (gesture.current && drag) move(win.id, drag.x, drag.y);
    gesture.current = null;
    setDrag(null);
  }, [drag, move, win.id]);

  const onResizePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.stopPropagation();
      focus(win.id);
      const target = e.currentTarget as HTMLElement;
      target.setPointerCapture(e.pointerId);
      gesture.current = {
        startX: e.clientX,
        startY: e.clientY,
        base: win.rect.w,
        base2: win.rect.h,
      };
    },
    [focus, win.id, win.rect.w, win.rect.h],
  );

  const onResizePointerMove = useCallback((e: React.PointerEvent) => {
    const g = gesture.current;
    if (!g) return;
    setSize({
      w: Math.max(280, g.base + (e.clientX - g.startX)),
      h: Math.max(160, g.base2 + (e.clientY - g.startY)),
    });
  }, []);

  const onResizePointerUp = useCallback(() => {
    if (gesture.current && size) resize(win.id, size.w, size.h);
    gesture.current = null;
    setSize(null);
  }, [resize, size, win.id]);

  if (win.minimized) return null;

  return (
    <section
      role="dialog"
      aria-label={win.title}
      aria-modal={false}
      onPointerDown={() => focus(win.id)}
      style={{
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
        zIndex: win.z,
      }}
      className={[
        'absolute flex flex-col rounded-pixel-lg border border-border bg-card',
        focused ? 'shadow-[var(--shadow-window)]' : 'shadow-[var(--shadow-window)] opacity-95',
      ].join(' ')}
    >
      {/* Titlebar */}
      <header
        onPointerDown={onTitlePointerDown}
        onPointerMove={onTitlePointerMove}
        onPointerUp={onTitlePointerUp}
        onDoubleClick={() => toggleMaximize(win.id)}
        className={[
          'flex h-7 shrink-0 select-none items-center gap-2 px-2',
          'cursor-grab active:cursor-grabbing',
          focused
            ? 'bg-gradient-to-r from-violet to-[#6f2fcf] text-white'
            : 'bg-border text-ink-dim',
        ].join(' ')}
      >
        <span className="truncate font-mono text-xs font-semibold uppercase tracking-wide">
          {win.title}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <TitleButton label="Minimize" onClick={() => toggleMinimize(win.id)}>
            _
          </TitleButton>
          <TitleButton label="Maximize" onClick={() => toggleMaximize(win.id)}>
            ▢
          </TitleButton>
          <TitleButton label="Close" danger onClick={() => close(win.id)}>
            ✕
          </TitleButton>
        </div>
      </header>

      {/* Body */}
      <div className="min-h-0 flex-1 overflow-auto bg-bg p-3 pixel-inset">
        {children}
      </div>

      {/* Resize grip */}
      {!win.maximized && (
        <div
          onPointerDown={onResizePointerDown}
          onPointerMove={onResizePointerMove}
          onPointerUp={onResizePointerUp}
          aria-hidden
          className="absolute bottom-0 right-0 h-4 w-4 cursor-nwse-resize"
          style={{
            background:
              'repeating-linear-gradient(135deg, var(--color-border) 0 2px, transparent 2px 4px)',
          }}
        />
      )}
    </section>
  );
}

function TitleButton({
  children,
  onClick,
  label,
  danger,
}: {
  children: ReactNode;
  onClick: () => void;
  label: string;
  danger?: boolean;
}) {
  return (
    <button
      aria-label={label}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={onClick}
      className={[
        'pixel-raised flex h-4 w-4 items-center justify-center rounded-pixel',
        'bg-card text-[10px] leading-none text-ink active:pixel-inset',
        danger ? 'hover:bg-red hover:text-white' : 'hover:brightness-125',
      ].join(' ')}
    >
      {children}
    </button>
  );
}

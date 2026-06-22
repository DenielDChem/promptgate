// LEFT pane (~22%): block outline derived from the template. Clicking an entry
// scrolls Monaco to that line (via the shared `revealLine` callback).

import { useMemo } from 'react';
import { deriveOutline } from '@/lib/promptOutline';

interface OutlinePaneProps {
  template: string;
  onJump: (line: number) => void;
}

export function OutlinePane({ template, onJump }: OutlinePaneProps) {
  const outline = useMemo(() => deriveOutline(template), [template]);
  const sections = outline.filter((o) => o.kind === 'section');
  const variables = outline.filter((o) => o.kind === 'variable');

  return (
    <nav
      aria-label="Block outline"
      className="flex h-full flex-col gap-3 overflow-auto pixel-inset rounded-pixel bg-bg p-2"
    >
      <Group title="Sections" empty="none detected">
        {sections.map((o) => (
          <Entry key={`s-${o.line}`} label={o.label} onClick={() => onJump(o.line)} />
        ))}
      </Group>

      <Group title="Variables" empty="no {{ vars }}">
        {variables.map((o) => (
          <Entry
            key={`v-${o.label}`}
            label={`{{ ${o.label} }}`}
            mono
            onClick={() => onJump(o.line)}
          />
        ))}
      </Group>
    </nav>
  );
}

function Group({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: React.ReactNode;
}) {
  const items = Array.isArray(children) ? children : [children];
  const isEmpty = items.flat().filter(Boolean).length === 0;
  return (
    <section className="flex flex-col gap-1">
      <h3 className="font-mono text-[10px] uppercase tracking-widest text-ink-dim">
        {title}
      </h3>
      {isEmpty ? (
        <span className="font-mono text-[10px] italic text-ink-dim/70">{empty}</span>
      ) : (
        <ul className="flex flex-col gap-0.5">{children}</ul>
      )}
    </section>
  );
}

function Entry({
  label,
  mono,
  onClick,
}: {
  label: string;
  mono?: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        onClick={onClick}
        className={[
          'w-full truncate rounded-pixel px-1.5 py-0.5 text-left text-xs text-ink',
          'hover:bg-violet/20 hover:text-neon',
          mono ? 'font-mono text-violet' : 'font-mono',
        ].join(' ')}
      >
        {label}
      </button>
    </li>
  );
}

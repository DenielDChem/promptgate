// Shared table primitives for the pixel data tables (Prompts / Jobs / Quality /
// Results). `Th` is the column header; `interactiveRowProps` returns the full
// set of props that make a <tr> behave like a button (pointer + keyboard
// activation, focus ring), so every clickable row stays consistent and
// accessible without each table re-implementing Enter/Space handling.

import type { HTMLAttributes, ReactNode } from 'react';

export function Th({
  children,
  className = '',
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <th scope="col" className={`px-2 py-1.5 text-left font-normal ${className}`}>
      {children}
    </th>
  );
}

/** Props that turn a table row into an accessible button. Spread onto a <tr>. */
export function interactiveRowProps(
  label: string,
  onActivate: () => void,
): HTMLAttributes<HTMLTableRowElement> & { tabIndex: number } {
  return {
    tabIndex: 0,
    role: 'button',
    'aria-label': label,
    onClick: onActivate,
    onKeyDown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onActivate();
      }
    },
    className:
      'cursor-pointer border-b border-border text-ink hover:bg-violet/15 focus:bg-violet/20',
  };
}

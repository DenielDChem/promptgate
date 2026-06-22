// Derive a lightweight block outline from a prompt template (LEFT pane, P2).
//
// Two kinds of entries:
//   • variables — every distinct `{{ name }}` mustache, with its first line.
//   • sections  — static role markers (system / user / output) if the template
//     uses a recognizable header for them. Kept deliberately simple: a line
//     that is just a role keyword (optionally markdown-headed / colon-suffixed).

export type OutlineKind = 'variable' | 'section';

export interface OutlineEntry {
  kind: OutlineKind;
  /** Display label (variable name or section title). */
  label: string;
  /** 1-based line where this entry first appears (for scroll-to). */
  line: number;
}

const VAR_RE = /\{\{\s*([\w.]+)\s*\}\}/g;

// Recognized section headers, e.g. "# System", "SYSTEM:", "## Output format".
const SECTION_RE =
  /^\s*#{0,3}\s*(system|user|assistant|output|context|instructions?)\b[:\s]*$/i;

/** Parse a template into an ordered, de-duplicated outline. */
export function deriveOutline(template: string): OutlineEntry[] {
  const lines = template.split('\n');
  const sections: OutlineEntry[] = [];
  const variables: OutlineEntry[] = [];
  const seenVars = new Set<string>();

  lines.forEach((raw, idx) => {
    const lineNo = idx + 1;

    const sectionMatch = SECTION_RE.exec(raw);
    if (sectionMatch) {
      const label = sectionMatch[1].toLowerCase();
      sections.push({
        kind: 'section',
        label: label.charAt(0).toUpperCase() + label.slice(1),
        line: lineNo,
      });
    }

    VAR_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = VAR_RE.exec(raw)) !== null) {
      const name = m[1];
      if (seenVars.has(name)) continue;
      seenVars.add(name);
      variables.push({ kind: 'variable', label: name, line: lineNo });
    }
  });

  // Sections first (structure), then variables (inputs).
  return [...sections, ...variables];
}

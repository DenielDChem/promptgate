// Desktop module metadata: title + placeholder pixel glyph per module.

import type { ModuleId } from './types';

export interface ModuleMeta {
  id: ModuleId;
  title: string;
  glyph: string; // simple emoji/box placeholder (spec: 32px pixel icons)
}

export const MODULE_META: Record<ModuleId, ModuleMeta> = {
  'my-prompts': { id: 'my-prompts', title: 'My Prompts', glyph: '▤' },
  templates: { id: 'templates', title: 'Templates', glyph: '▦' },
  validator: { id: 'validator', title: 'Validator', glyph: '◉' },
  quality: { id: 'quality', title: 'Quality', glyph: '📊' },
  admin: { id: 'admin', title: 'Admin', glyph: '⚙' },
  logs: { id: 'logs', title: 'Agent Logs', glyph: '☰' },
  trash: { id: 'trash', title: 'Trash', glyph: '⌫' },
};

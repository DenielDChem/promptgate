// Single source of truth for UI role-based access (spec §12, team-lead matrix).
//
//   admin     → all modules, full access
//   prompter  → My Prompts, Templates, Validator, Quality, Trash (no Admin / Logs)
//   validator → Validator (full) + Quality + My Prompts (read-only)
//   guest     → My Prompts (read-only) only — no Validator run, no Quality
//
// Any module not listed for a role is implicitly hidden.
//
// `validate.run` maps to FULL access on the `validator` module; `stats.view_own`
// maps to visibility of the `quality` module. Guests get neither.

import type { ModuleAccess, ModuleId, Role } from './types';

const HIDDEN: ModuleAccess = { visible: false, readOnly: true };
const FULL: ModuleAccess = { visible: true, readOnly: false };
const READ_ONLY: ModuleAccess = { visible: true, readOnly: true };

type Matrix = Record<Role, Partial<Record<ModuleId, ModuleAccess>>>;

const MATRIX: Matrix = {
  admin: {
    'my-prompts': FULL,
    templates: FULL,
    validator: FULL,
    quality: FULL,
    admin: FULL,
    logs: FULL,
    trash: FULL,
  },
  prompter: {
    'my-prompts': FULL,
    templates: FULL,
    validator: FULL,
    quality: FULL,
    trash: FULL,
  },
  validator: {
    validator: FULL,
    quality: FULL,
    'my-prompts': READ_ONLY,
  },
  guest: {
    'my-prompts': READ_ONLY,
  },
};

/** All modules in canonical desktop order. */
export const ALL_MODULES: ModuleId[] = [
  'my-prompts',
  'templates',
  'validator',
  'quality',
  'admin',
  'logs',
  'trash',
];

/** Whether a role may launch deep validation runs (spec `validate.run`). */
export function canRunValidation(role: Role): boolean {
  return !moduleAccess(role, 'validator').readOnly && canAccess(role, 'validator');
}

/** Resolve a role's access to a specific module. */
export function moduleAccess(role: Role, module: ModuleId): ModuleAccess {
  return MATRIX[role]?.[module] ?? HIDDEN;
}

/** Whether a role may see/open a module at all. */
export function canAccess(role: Role, module: ModuleId): boolean {
  return moduleAccess(role, module).visible;
}

/** Modules a role can see, in canonical order. */
export function visibleModules(role: Role): ModuleId[] {
  return ALL_MODULES.filter((m) => canAccess(role, m));
}

// Shared domain types for PromptGate frontend.

export type Role = 'admin' | 'prompter' | 'validator' | 'guest';

export interface User {
  id: number | string;
  username: string;
  email: string;
  role: Role;
}

export interface AuthSuccess {
  access_token: string;
  token_type: 'bearer';
  user: User;
}

/** Identifiers for every desktop module/window. */
export type ModuleId =
  | 'my-prompts'
  | 'templates'
  | 'validator'
  | 'admin'
  | 'logs'
  | 'trash';

/** Per-module access an RBAC role may grant. */
export interface ModuleAccess {
  /** Whether the icon is visible / window openable at all. */
  visible: boolean;
  /** If true, the module opens in a read-only mode. */
  readOnly: boolean;
}

// ─── Prompts (P2) ──────────────────────────────────────────────────────────

export type PromptStatus = 'draft' | 'published';

/** Row shape returned by GET /api/prompts (list view). */
export interface PromptSummary {
  id: string;
  name: string;
  tags: string[];
  model?: string;
  status: PromptStatus;
  current_version: number;
  owner_id: number | string;
}

/** Full PromptConfig returned by GET /api/prompts/{id}. */
export interface PromptConfig {
  id: string;
  name: string;
  tags: string[];
  template: string;
  schema: string;
  description: string;
  status: PromptStatus;
  current_version: number;
}

/** Body for POST /api/prompts (create or update + record a version). */
export interface PromptSavePayload {
  id: string;
  name: string;
  template: string;
  schema: string;
  tags?: string[];
  description?: string;
  message?: string;
}

/** One entry in GET /api/prompts/{id}/versions (newest first). */
export interface PromptVersion {
  version_no: number;
  author_id: number | string;
  message: string;
  created_at: string;
}

// ─── Live validation / lint (P2 §4) ──────────────────────────────────────────

export type LintType = 'stylistic' | 'determinism' | 'hallucination';

/** One finding from POST /api/lint. `line`/`col` are 1-based; `end_col` exclusive. */
export interface LintFinding {
  type: LintType;
  severity: 'info' | 'warning' | 'error';
  line: number;
  col: number;
  end_col: number;
  message: string;
  suggestion?: string;
}

export interface LintResult {
  findings: LintFinding[];
}

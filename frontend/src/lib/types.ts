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

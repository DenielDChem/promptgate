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
  | 'quality'
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

// ─── Deep validation + quality (P3 §4, §8.2) ─────────────────────────────────

/** Traffic-light grade shared by validation runs and quality scores. */
export type ValidationColor = 'green' | 'yellow' | 'red';

/** A single test-set entry the user authors before running a validation. */
export interface TestCase {
  question: string;
  payload?: string;
}

/** Body for POST /api/prompts/{id}/validate. */
export interface ValidatePayload {
  model_id: string;
  cases?: TestCase[];
  repeats?: number;
}

/** One graded answer in a validation run. */
export interface ValidationCaseResult {
  question: string;
  answer: string;
  /** Comprehension/quality judge score for this answer, 0–10 (higher better). */
  score: number;
  /** Hallucination score for this answer, 0–10 (LOWER better). */
  hallucination: number;
  /** Verbatim slice of the answer the judge flagged, if any. */
  flagged_block?: string;
}

/** Aggregate metrics shared by a run summary and a full run. */
export interface ValidationMetrics {
  model_id: string;
  /** Answer stability across repeats, 0–100 (%). */
  determinism: number;
  /** Comprehension judge score, 0–10 (higher better). */
  comprehension: number;
  /** Hallucination score, 0–10 (LOWER better). */
  hallucination: number;
  latency_ms: number;
  n_cases: number;
}

/** Full result of POST /api/prompts/{id}/validate and GET /api/validations/{run_id}. */
export interface ValidationRun extends ValidationMetrics {
  run_id: string;
  color: ValidationColor;
  cases: ValidationCaseResult[];
}

/** One row of GET /api/prompts/{id}/validations (newest first). */
export interface ValidationRunSummary extends ValidationMetrics {
  run_id: string;
  created_at: string;
}

/** GET /api/prompts/{id}/quality — null/404 if never validated. */
export interface QualityScore {
  prompt_id: string;
  version_no: number;
  avg_score: number;
  comprehension: number;
  determinism: number;
  hallucination: number;
  n_validations: number;
  color: ValidationColor;
}

/** One row of the GET /api/quality dashboard. */
export interface QualityRow {
  prompt_id: string;
  name: string;
  avg_score: number;
  hallucination: number;
  determinism: number;
  color: ValidationColor;
  n_validations: number;
}

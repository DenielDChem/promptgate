# PromptGate Platform — Architecture & Phased Plan

> Status: **PLAN (no code yet)** · Date: 2026-06-22 · Supersedes the single-user `pgate` UI.
> Source brief: "PromptGate — Полная UI/UX спецификация v1.0" (user-provided).
> Decisions locked: replace `pgate`'s UI in place · cyberpunk/Win95 pixel aesthetic · stack recommended below · this round = plan only, approve before build.

---

## 0. Positioning — what changes

`pgate` today is a **single-user, offline, no-telemetry pip package**: store/compile/validate/run prompt contracts (FastAPI + SQLite + vanilla SPA, ships inside the wheel).

PromptGate (the platform) is a **multi-user, invite-only web app** with accounts, RBAC, an admin console, an async task queue, quality analytics, and a desktop-metaphor UI. We grow **this repo** into it: keep and extend the FastAPI backend; replace the vanilla `/ui` SPA with a built frontend.

This is a real product pivot. The package will no longer be a pure buildless offline tool — note the ROADMAP "Never: GUI without explicit user request / no telemetry" lines: the GUI is now explicitly requested; **we keep the no-telemetry / offline-capable promise** (self-hosted, no external calls except the LLM providers the user configures).

---

## 1. Recommended stack

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | **React + TypeScript + Vite** | Spec needs Monaco, a window manager, 10-tab admin, live-validated editor — vanilla no-build can't carry this. Vite gives fast HMR + a static `dist/`. |
| UI state | **Zustand** | Already the house pattern in the user's other projects (agent-portal). Lighter than Redux Toolkit for this. |
| Styling | **Tailwind v4 + custom pixel design-system** | Token-driven; encode the cyberpunk/Win95 palette + 4px pixel grid as Tailwind tokens. Custom `<Window>`, `<PixelButton>`, `<PixelIcon>` primitives. |
| Code editor | **Monaco** | 3-pane prompt editor, syntax/error squiggles, find. |
| Graph (CoT) | **React Flow** | Draggable block tree + CoT node/edge graph in the YAML decomposer. |
| Backend | **Keep FastAPI** (extend `make_app` with routers) | Reuse everything below. |
| Auth | **JWT (24h) + invite tokens**, `passlib[bcrypt]`, `pyotp` (TOTP 2FA), optional OAuth2 later | Per spec §11. |
| DB | **SQLite (dev) → Postgres (prod)** via the already-scaffolded `backends/` abstraction (ROADMAP v0.5) | Versions/quality/audit need real tables; FTS5 stays for SQLite, `tsvector`/pgvector path for PG. |
| Task queue | **Start in-process (`asyncio` workers + DB-backed job table)**; upgrade to Celery/RQ + Redis only if load demands | Avoids a Redis dependency for self-hosters on day one. |
| Packaging | FastAPI serves the built `frontend/dist/` via `StaticFiles`; CI builds the SPA and commits/ships `dist/` so `pip install` users still get a working UI | Preserves "works after pip install". |

**Repo layout (target):**
```
promptgate/            # existing python package (backend) — extended
  api/                 # split monolithic api.py into routers: auth, prompts, versions,
                       # validate, templates, queue, admin, stats, security, env, models
  auth/                # users, jwt, invites, rbac, 2fa
  quality/             # 3-type validation engine + scoring
  queue/               # job model + workers
  storage.py, runner.py, chains.py, profiles.py, keystore.py, models_registry.py  # REUSE
frontend/              # NEW — React+TS+Vite SPA (replaces promptgate/ui/)
  src/{desktop,windows,components,stores,api,theme}
  dist/                # built output, served by FastAPI
docs/                  # this file + future specs
migrations/            # new — schema migrations
```

---

## 2. Reuse vs. build-new (mapped to current code)

**Reuse as-is / light extension:**
- `PromptConfig`, `CompiledContract`, `ValidationResult`, `ModelHints` (`models.py`)
- `compiler.py` (Jinja2 compile), `runner.py` (LiteLLM run+retry), `chains.py`
- `storage.py` SQLiteBackend + FTS5 → add `user_id`, soft-delete (trash), version FK
- `models_registry.py` → feeds the admin "Models" tab + per-user model access
- `profiles.py` → generalizes into the 3-level **env vars** system (global/user/model)
- `keystore.py` (Fernet) → becomes the API-key vault (provider keys + agent API keys)
- `make_app()` factory + existing `/api/*` endpoints (prompts/search/compile/run/validate/chains/models) → wrapped behind auth, kept

**Build new:**
- Auth (users, JWT, invites, RBAC, registration requests, 2FA, audit log)
- Prompt **versioning** (history + rollback; every save = new version row)
- **3-type live validation engine** (stylistic / non-determinism / hallucination) — see §4
- **YAML decomposer** + CoT graph
- **Validator** test-set runner + metrics (determinism %, hallucination score, latency)
- **Async task queue** (validation / template generation / mass-testing)
- **Quality analytics** (per-prompt + per-block scoring, dashboards)
- **Admin console** (10 tabs), **storage policies**, **integrations** (SMTP/webhook/telegram/export)
- **Frontend** (desktop shell, window manager, pixel theme, Monaco editor)
- **Hermes** integration hook (`/opt/hermes/` agents)

---

## 3. Data model (new tables, names indicative)

- `users(id, username, email, pw_hash, role, totp_secret?, created_at, status)`
- `invites(token, role, expires_at, one_time, used_by?, created_by, status)`
- `registration_requests(id, email, reason, created_at, status)`
- `prompt_versions(id, prompt_id, version_no, body_json, author_id, created_at, message)` — prompt text/schema snapshot per save
- `prompts` (extend): `owner_id`, `status` (draft/published), `current_version`, `deleted_at`
- `validation_runs(id, prompt_id, version_no, model_id, determinism, comprehension, hallucination, latency_ms, created_at)`
- `validation_cases(id, run_id, question, answer, score, flagged_block?)`
- `quality_scores(prompt_id, version_no, avg_score, hallucination, determinism, n_validations, color)`
- `jobs(id, type, target_prompt, model_id, priority, status, progress, result_json, created_by, created_at)`
- `env_vars(scope, scope_id, key, value, encrypted)` — scope ∈ global|user|model
- `api_keys(id, name, key_hash, scopes, last_used, created_by)` — for agents
- `audit_log(id, ts, event, user_id?, ip, detail_json)`
- `storage_policies(path_glob, role/user, read, write, delete)`

SQLite via migrations; Postgres parity through `backends/` abstraction.

---

## 4. The 3-type validation engine (core differentiator, spec §4 & §6)

Two layers:
1. **Live (in-editor, fast, local):** static analysis over the template, no LLM call.
   - 🟡 **Stylistic** — repetition, filler/water, hedging words → suggest replacement.
   - 🔵 **Non-determinism** — vague instructions ("maybe", "try to", unbounded lists, missing output format) → suggest tightening.
   - 🔴 **Hallucination risk** — asks for facts/citations without a provided source/`{{context}}` → suggest adding a source block.
   - Implemented as a rule registry returning `{type, line, span, message, suggestion}`; Monaco renders squiggles + hover + quick-fix.
2. **Deep (Validator, async, LLM-backed):** run the prompt over a test-set (default 5 Qs) N times → compute **determinism** (answer stability across runs), **comprehension** (judge score 1–10), **hallucination** (judge/grounding score), **latency**. Reuse `runner.py`. Per-block attribution feeds `quality_scores` and the quality dashboard.

Color thresholds (spec §8.2): 🟢 score ≥8.0 & halluc <1.5 · 🟡 6.0–7.9 / 1.5–3.5 · 🔴 <6.0 / >3.5.

---

## 5. Frontend architecture

- **Desktop shell**: 24px grid background, taskbar (Start/clock/user), draggable/resizable `<Window>` components, double-click icons → windows, right-click context menu. A `windowManager` Zustand store (open windows, z-order, focus, minimize).
- **Theme**: dark `#0D0F14` + neon green `#00FF9D` / violet `#9D4EFF` / orange `#FF6B35`; JetBrains Mono (code) + IBM Plex Sans (UI); 4px-step pixel transitions; terminal-print + scanline micro-effects (respect `prefers-reduced-motion`).
- **Key windows**: Login/Invite · Desktop · My Prompts (table+filter) · Prompt Editor (3-pane + Monaco + inspector + version dropdown) · YAML Decomposer (React Flow) · Validator · Admin (10 tabs) · Agent Logs · Trash.
- **RBAC in UI**: route/window guards from the JWT role; icons hidden per matrix (spec §12).
- **Offline-ish**: localStorage/IndexedDB draft autosave (spec §13).

---

## 6. Phased roadmap (build-ready, each phase = shippable)

**P0 — Foundation & scaffolding**
Split `api.py` into routers; stand up `frontend/` (Vite+TS+Tailwind+pixel design-system + `<Window>`/desktop shell); migrations harness; FastAPI serves `dist/`. Deliverable: empty desktop + taskbar renders, one demo window.

**P1 — Auth & RBAC** (everything depends on this)
Users, bcrypt, JWT, invite tokens, registration-request flow, 4-role matrix, login/invite UI, 2FA optional. Deliverable: invite → register → login → role-gated desktop.

**P2 — Prompts + Editor + Versioning**
Per-user prompts (owner_id), 3-pane Monaco editor, version history + rollback, live 3-type validation (static rules), hotkeys. Deliverable: create/edit/version/publish a prompt with live squiggles.

**P3 — Validator + Quality**
Deep validation runner (test-sets, determinism/comprehension/hallucination/latency), quality scores + dashboard + per-block attribution + graphs. Deliverable: run validation, see metrics + color grades.

**P4 — Task Queue**
Job table + in-process async workers, queue UI (status/progress/cancel/report), job types: validation / template-gen / mass-test. Deliverable: async jobs with live progress.

**P5 — YAML Decomposer + CoT**
Block tree (draggable), CoT graph (React Flow), save-as-YAML, publish to agents. Deliverable: decompose a prompt → YAML + graph.

**P6 — Admin console & platform ops**
10 tabs: dashboard, users, storage policies, models, env vars (3-level), queue, statistics, security/audit, logs, integrations (SMTP/webhook/telegram/export). Rate limiting, audit log, backups. Deliverable: full admin.

**P7 — Hermes + integrations hardening**
Hermes agent framework hook; OAuth2; export (CSV/JSON/PDF); Postgres prod path.

Suggested grouping for parallel agents later: P1 (auth) and P0 (scaffold) first & serial; P2/P3/P4 can fan out once P1 lands; P5/P6 after.

---

## 7. Risks & open questions

- **Buildless promise broken**: pip users now need a prebuilt `dist/`. Mitigation: CI builds + commits `dist/`; document `npm` only for contributors.
- **Scope**: this is ~7 phases / weeks of work, not a sprint. Recommend shipping P0–P2 as a usable MVP before committing to P4–P7.
- **Pixel/cyberpunk + accessibility**: neon-on-dark and pixel fonts risk legibility/contrast. Need an AA pass and a "reduce effects" toggle.
- **2FA/OAuth2/Postgres/Celery**: all "later unless needed" to keep self-hosting simple.
- **Hermes coupling**: needs the real `/opt/hermes/` API surface confirmed before P7.
- **Single-user `pgate` users**: provide a migration (existing prompts → owner = first admin).

---

## 8. Future / parking lot (ideas for future work)

- **Prompt marketplace / sharing** between users or instances (ROADMAP v1.0).
- **A/B prompt variants** + eval scoring (ROADMAP v0.6) — git-style branching on versions.
- **Auto-fix from validation**: one-click apply the suggested rewrite for 🟡/🔴 findings.
- **LLM-assisted schema extraction** (paste raw text → schema) — ROADMAP v0.4+ idea, now a window.
- **Diff view between prompt versions** (side-by-side, like git).
- **Cross-agent @-mentions / mini-council** review of a prompt (mirrors agent-portal idea).
- **Real-time collaboration** (multi-cursor) on a prompt — later, needs CRDT/websockets.
- **Cost tracking** per validation/run (tokens × model price) in the stats tab.
- **Scheduled re-validation** (cron) to catch quality drift over time.
- **Template library / scenario presets** the decomposer can start from.
- **Webhook/Telegram alerts** on job completion or quality regression (ties to user's existing TG bots).
- **PDF/CSV export** of quality reports for sharing.
- **Plugin/rule SDK** so users add custom live-validation rules.
- **Mobile/responsive** read-only mode for dashboards.

---

## 9. Immediate next step (on approval)

Build **P0 + P1** (scaffold + auth) as the foundation everyone else depends on — then reassess before fanning out P2–P4. No code until this plan is approved.

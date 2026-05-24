# PGate Roadmap

## Released

### v0.1 — Core
SQLite+FTS5 storage · BM25 search · Jinja2 compiler · JSON validator · MCP stdio · CLI (init/add/search/compile/mcp/purge)

### v0.2 — Watch + Rich Validation + Crypto
`pgate watch` — inotify file watcher, auto-upsert on .yaml change
`pgate keys` — Fernet-encrypted keystore (~/.promptgate/keys.enc)
FormatChecker: email, url, uuid, date, pattern, enum

### v0.3 — Execute + Chains + REST API + Profiles
`pgate run` — LiteLLM call + retry loop with schema feedback
`pgate chain` — prompt chains, context pipe, input_map/output_as
`pgate serve` — FastAPI REST API (/api/prompts, /api/chains, /api/compile, /api/run, /api/validate, /api/search)
`pgate profile` — named env configs (dev/staging/prod), api_base + default_model per profile
Profile-aware run: api_base + api_key resolved from active profile + keystore automatically

---

## Planned

### v0.4 — Local Web UI

**Goal:** human-facing interface served directly by `pgate serve` on localhost. Zero extra install.

**Approach:** FastAPI serves static SPA at `/ui/` alongside existing REST API.
Vanilla JS or Preact (~50kb, no build step). User runs `pgate serve` → browser opens `http://localhost:8080/ui/` automatically (`--open` flag).

**Screens:**

| Screen | Description |
|--------|-------------|
| Library | Prompt list with search, tags filter, create/delete |
| Editor | YAML template + schema editor, live compile preview, missing fields highlighted |
| Run | Profile/model dropdown, payload form auto-generated from JSON Schema, Run button → validated JSON result |
| Chains | Chain list, step visualizer, run with payload |
| Profiles | Profile list, add/edit/set default, linked keystore key status |

**Key features:**
- Payload form auto-generated from JSON Schema (no manual JSON typing for end users)
- Live compile preview as user edits template
- Run history per prompt (last N results, attempt count, model used)
- Model picker populated from `pgate models list`

**CLI addition:**
```bash
pgate serve --open   # opens browser tab automatically
```

---

### v0.4+ — LLM-assisted Prompt Extraction (UI layer)

**Goal:** user pastes raw prompt text → UI extracts schema fields automatically.

**Flow:**
1. User pastes raw prompt text in textarea (plain text, markdown, anything)
2. Click "Extract schema" → calls LLM via active profile with meta-prompt
3. LLM returns detected input fields → auto-populated JSON Schema
4. User reviews/edits field types, adds constraints (required, format, enum)
5. Save → stored as PromptConfig in SQLite

This is the human-facing extraction layer discussed — lives in UI, not in pgate core.
pgate core stays: compile/cache/validate/run (agent middleware).

---

### v0.5 — Pluggable Storage Backends

PostgreSQL backend for team/server deployments.
`StorageBackend` abstract class already scaffolded in `backends/`.

---

### v0.6 — Prompt Variants + Eval

Git-style branching for prompts: A/B test two template versions.
Eval: run prompt on test dataset, score output against expected schema + custom assertions.

---

### v1.0 — Marketplace + Commercial License

Schema marketplace: publish/buy prompt contracts.
`pgate add --url marketplace/finance/quarterly-report`
Commercial license (offline hash: email + machine_id).
Team prompt hub (shared SQLite or PostgreSQL backend).

---

## Never

- Cloud sync of user data
- Telemetry
- GUI without explicit user request

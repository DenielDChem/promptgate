# PGate

**Prompt ORM for LLM agents.** Store, find, compile, validate, and cache prompt contracts — locally, without cloud, without telemetry.

## Install

```bash
pip install pgate
```

## Quickstart

```bash
pgate init
pgate add --file examples/report_sales.yaml
pgate compile --interactive
```

## MCP (Claude Desktop / Cursor)

Add to `claude_desktop_config.json`:

```json
{
  "pgate": {
    "command": "pgate",
    "args": ["mcp", "--stdio"]
  }
}
```

## Status

v0.1 — in development.

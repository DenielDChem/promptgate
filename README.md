# PromptGate

**Prompt ORM for LLM agents.** Store, find, compile, validate, and cache prompt contracts — locally, without cloud, without telemetry.

## Install

```bash
pip install promptgate
```

## Quickstart

```bash
promptgate init
promptgate add --file examples/report_sales.yaml
promptgate compile --interactive
```

## MCP (Claude Desktop / Cursor)

Add to `claude_desktop_config.json`:

```json
{
  "promptgate": {
    "command": "promptgate",
    "args": ["mcp", "--stdio"]
  }
}
```

## Status

v0.1 — in development.

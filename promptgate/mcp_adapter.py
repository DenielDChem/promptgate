"""Read-only MCP stdio server: pg_find_prompt, pg_get_contract."""
from __future__ import annotations

import asyncio
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from promptgate.file_api import get_or_compile
from promptgate.router import search
from promptgate.storage import SQLiteBackend, _DEFAULT_DB_PATH


def build_mcp_server(db_path: str | Path = _DEFAULT_DB_PATH) -> FastMCP:
    """Construct a read-only FastMCP server for PromptGate.

    Exposes two tools:
    - ``pg_find_prompt``: full-text search over stored prompts.
    - ``pg_get_contract``: compile a prompt with a given payload and return the contract.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        Configured FastMCP instance ready for ``run_stdio_async()``.

    Examples:
        >>> server = build_mcp_server(":memory:")
        >>> server.name
        'promptgate'
    """
    mcp = FastMCP("promptgate")
    _db = Path(db_path) if db_path != ":memory:" else db_path

    @mcp.tool()
    def pg_find_prompt(query: str, limit: int = 5) -> list[dict]:
        """Search stored prompts by relevance.

        Args:
            query: Search string. Supports FTS5 boolean operators.
            limit: Maximum results to return.

        Returns:
            List of dicts with keys: id, name, description, tags, score.
        """
        backend = SQLiteBackend(_db)
        backend.init()
        hits = search(query, db_path=_db, limit=limit)
        results = []
        for prompt_id, score in hits:
            prompt = backend.get(prompt_id)
            if prompt:
                results.append(
                    {
                        "id": prompt.id,
                        "name": prompt.name,
                        "description": prompt.description,
                        "tags": prompt.tags,
                        "score": round(score, 4),
                    }
                )
        return results

    @mcp.tool()
    def pg_get_contract(prompt_id: str, payload: dict) -> dict:
        """Compile a prompt with payload and return the contract.

        Args:
            prompt_id: ID of the stored prompt.
            payload: Key-value data matching the prompt's schema.

        Returns:
            Dict representation of CompiledContract.

        Raises:
            ValueError: If prompt_id not found or template rendering fails.
        """
        try:
            contract = get_or_compile(prompt_id, payload, db_path=_db)
            return contract.model_dump()
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

    return mcp


def run_stdio(db_path: str | Path = _DEFAULT_DB_PATH) -> None:
    """Launch the MCP server in stdio mode (blocking).

    Args:
        db_path: Path to the SQLite database.

    Examples:
        >>> # Called by CLI: promptgate mcp --stdio
        >>> callable(run_stdio)
        True
    """
    server = build_mcp_server(db_path)
    asyncio.run(server.run_stdio_async())

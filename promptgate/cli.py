"""Click CLI: init, add, search, compile, mcp."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml
from loguru import logger

from promptgate.file_api import get_or_compile, purge_stale
from promptgate.models import PromptConfig
from promptgate.router import search as pg_search
from promptgate.storage import SQLiteBackend, _DEFAULT_DB_PATH


def _configure_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="<level>{level}</level> {message}")
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging.")
@click.option(
    "--db",
    default=str(_DEFAULT_DB_PATH),
    show_default=True,
    help="Path to SQLite database.",
)
@click.pass_context
def main(ctx: click.Context, verbose: bool, db: str) -> None:
    """PromptGate - Prompt ORM for LLM agents."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = db
    _configure_logging(verbose)


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize the PromptGate database.

    Creates ~/.promptgate/db.sqlite and FTS5 tables if they don't exist.
    """
    backend = SQLiteBackend(ctx.obj["db"])
    backend.init()
    click.echo(f"Initialized: {ctx.obj['db']}")


@main.command("add")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), help="Path to YAML prompt file.")
@click.option("--url", "-u", help="URL to fetch YAML prompt from.")
@click.pass_context
def add_prompt(ctx: click.Context, file_path: str | None, url: str | None) -> None:
    """Add or update a prompt from a YAML file or URL.

    Examples:

        promptgate add --file examples/report_sales.yaml

        promptgate add --url https://example.com/my_prompt.yaml
    """
    if not file_path and not url:
        raise click.UsageError("Provide --file or --url.")

    raw: str
    if url:
        import urllib.request
        with urllib.request.urlopen(url) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    else:
        raw = Path(file_path).read_text(encoding="utf-8")

    data = yaml.safe_load(raw)
    prompt = PromptConfig.model_validate(data)

    backend = SQLiteBackend(ctx.obj["db"])
    backend.init()
    backend.upsert(prompt)
    click.echo(f"Added prompt: {prompt.id} ({prompt.name})")


@main.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=5, show_default=True, help="Max results.")
@click.pass_context
def search_cmd(ctx: click.Context, query: str, limit: int) -> None:
    """Search prompts by full-text relevance.

    Examples:

        promptgate search "sales report"
    """
    results = pg_search(query, db_path=ctx.obj["db"], limit=limit)
    if not results:
        click.echo("No results.")
        return
    for prompt_id, score in results:
        click.echo(f"  {score:.4f}  {prompt_id}")


@main.command("compile")
@click.argument("prompt_id")
@click.option("--payload", "-p", default="{}", help="JSON payload string.")
@click.option("--model", "-m", default=None, help="LLM model ID for model-aware compilation.")
@click.option("--interactive", "-i", is_flag=True, help="Prompt for each required field interactively.")
@click.pass_context
def compile_cmd(ctx: click.Context, prompt_id: str, payload: str, model: str | None, interactive: bool) -> None:
    """Compile a prompt and print the system_prompt.

    Examples:

        promptgate compile sales_v1 --payload '{"period": "2024-01"}'

        promptgate compile sales_v1 --model gpt-4o --payload '{"period": "2024-01"}'

        promptgate compile sales_v1 --interactive
    """
    backend = SQLiteBackend(ctx.obj["db"])
    backend.init()
    prompt = backend.get(prompt_id)
    if prompt is None:
        raise click.ClickException(f"Prompt '{prompt_id}' not found.")

    data: dict = json.loads(payload)

    if interactive:
        required = prompt.schema_.get("required", [])
        props = prompt.schema_.get("properties", {})
        for field in required:
            if field not in data:
                desc = props.get(field, {})
                hint = desc.get("type", "string")
                value = click.prompt(f"  {field} ({hint})")
                data[field] = value

    contract = get_or_compile(prompt_id, data, db_path=ctx.obj["db"], model_id=model)
    click.echo(contract.system_prompt)
    if contract.missing_fields:
        click.echo(f"\n[missing: {', '.join(contract.missing_fields)}]", err=True)
    if contract.model_hints:
        h = contract.model_hints
        rm_tag = {"none": "", "chain_of_thought": f" [CoT:{h.cot_strategy}]", "native": " [think]"}.get(
            h.reasoning_mode, ""
        )
        sys_tag = "" if h.supports_system_prompt else " [no-sys]"
        logger.debug("Model: {} ({}) ctx={}k{}{}", h.model_id, h.family, h.context_window // 1000, rm_tag, sys_tag)


@main.group("models", invoke_without_command=True)
@click.pass_context
def models_group(ctx: click.Context) -> None:
    """Manage LLM model registry.

    Without a subcommand, lists all registered models.

    Examples:

        promptgate models

        promptgate models list --family anthropic

        promptgate models add --id gpt-5 --family openai --ctx 400000 --reasoning native

        promptgate models rm gpt-5

        promptgate models show gpt-4o
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(models_list)


def _print_models_table(rows: list[tuple[str, object]], custom_ids: set[str]) -> None:
    """Print a formatted table row for each (model_id, ModelCapabilities) pair."""
    from promptgate.models_registry import ModelCapabilities as MC
    rm_labels = {"none": "     ", "chain_of_thought": " CoT ", "native": "think"}
    for name, caps in rows:
        rm = rm_labels.get(caps.reasoning_mode, "     ")
        cot = f"/{caps.cot_strategy}" if caps.reasoning_mode == "chain_of_thought" else ""
        sys_tag = "  " if caps.supports_system_prompt else "NS"
        json_tag = "J" if caps.json_native else " "
        ctx_k = caps.context_window // 1000
        custom_tag = "*" if name in custom_ids else " "
        click.echo(f"  {custom_tag}[{rm}{cot:<12}] [{sys_tag}][{json_tag}]  ctx={ctx_k:>5}k  {name}")


@models_group.command("list")
@click.option("--family", "-f", default=None, help="Filter by family (openai, anthropic, deepseek...)")
@click.option("--reasoning", "-r", is_flag=True, help="Show only models with reasoning support.")
@click.option("--custom", "-c", is_flag=True, help="Show only user-defined models.")
def models_list(family: str | None, reasoning: bool, custom: bool) -> None:
    """List registered LLM models and their capabilities.

    A leading ``*`` marks user-defined models.

    Examples:

        promptgate models list

        promptgate models list --family anthropic

        promptgate models list --reasoning

        promptgate models list --custom
    """
    from promptgate.models_registry import _REGISTRY, _USER_REGISTRY

    all_rows: dict = {**_REGISTRY, **_USER_REGISTRY}  # user overrides win
    rows = sorted(all_rows.items())
    if family:
        rows = [(k, v) for k, v in rows if v.family == family]
    if reasoning:
        rows = [(k, v) for k, v in rows if v.reasoning_mode != "none"]
    if custom:
        rows = [(k, v) for k, v in rows if k in _USER_REGISTRY]

    if not rows:
        click.echo("No models match the filter.")
        return
    _print_models_table(rows, set(_USER_REGISTRY.keys()))


@models_group.command("add")
@click.option("--id", "model_id", required=True, help="Unique model identifier.")
@click.option("--family", "-f", required=True, help="Provider family (openai, anthropic, deepseek...)")
@click.option("--ctx", "context_window", required=True, type=int, help="Context window in tokens.")
@click.option(
    "--reasoning", "-r", default="none",
    type=click.Choice(["none", "chain_of_thought", "native"]),
    help="Reasoning mode.",
)
@click.option(
    "--cot-strategy", default="zero_shot",
    type=click.Choice(["zero_shot", "structured", "react"]),
    help="CoT algorithm for chain_of_thought models.",
)
@click.option("--json-native", is_flag=True, help="Model supports native JSON output mode.")
@click.option("--no-system-prompt", is_flag=True, help="Model does not accept a system prompt.")
@click.option("--reasoning-budget", type=int, default=None, help="Token budget for native reasoning.")
@click.option("--max-output", type=int, default=4096, help="Max output tokens.")
def models_add(
    model_id: str,
    family: str,
    context_window: int,
    reasoning: str,
    cot_strategy: str,
    json_native: bool,
    no_system_prompt: bool,
    reasoning_budget: int | None,
    max_output: int,
) -> None:
    """Add or override a model in the user registry.

    Writes to ``~/.promptgate/models.yaml``.

    Examples:

        promptgate models add --id gpt-5 --family openai --ctx 400000 --reasoning native

        promptgate models add --id my-llm --family custom --ctx 8000 --reasoning chain_of_thought --cot-strategy structured
    """
    from promptgate.models_registry import ModelCapabilities, register_model

    caps = ModelCapabilities(
        family=family,
        context_window=context_window,
        reasoning_mode=reasoning,
        cot_strategy=cot_strategy,
        json_native=json_native,
        supports_system_prompt=not no_system_prompt,
        reasoning_budget_tokens=reasoning_budget,
        max_output_tokens=max_output,
    )
    register_model(model_id, caps)
    click.echo(f"Registered '{model_id}' ({family}, ctx={context_window:,}) → ~/.promptgate/models.yaml")


@models_group.command("rm")
@click.argument("model_id")
def models_rm(model_id: str) -> None:
    """Remove a custom model from the user registry.

    Only user-defined models can be removed; built-in entries are protected.

    Examples:

        promptgate models rm my-custom-llm
    """
    from promptgate.models_registry import unregister_model

    if not unregister_model(model_id):
        raise click.ClickException(
            f"'{model_id}' not found in user registry. Built-in models cannot be removed."
        )
    click.echo(f"Removed '{model_id}' from ~/.promptgate/models.yaml")


@models_group.command("show")
@click.argument("model_id")
def models_show(model_id: str) -> None:
    """Show full capabilities for a specific model.

    Examples:

        promptgate models show gpt-4o

        promptgate models show my-custom-llm
    """
    from promptgate.models_registry import _USER_REGISTRY, resolve_model

    caps = resolve_model(model_id)
    if caps is None:
        raise click.ClickException(f"Unknown model: '{model_id}'")

    is_custom = model_id in _USER_REGISTRY
    source = "user-defined" if is_custom else "built-in"
    click.echo(f"  model_id:                {model_id}  [{source}]")
    click.echo(f"  family:                  {caps.family}")
    click.echo(f"  context_window:          {caps.context_window:,}")
    click.echo(f"  max_output_tokens:       {caps.max_output_tokens:,}")
    click.echo(f"  reasoning_mode:          {caps.reasoning_mode}")
    click.echo(f"  cot_strategy:            {caps.cot_strategy}")
    click.echo(f"  json_native:             {caps.json_native}")
    click.echo(f"  supports_system_prompt:  {caps.supports_system_prompt}")
    if caps.reasoning_budget_tokens is not None:
        click.echo(f"  reasoning_budget_tokens: {caps.reasoning_budget_tokens:,}")


@main.command("mcp")
@click.option("--stdio", "transport", flag_value="stdio", default=True, help="Run MCP over stdio.")
@click.pass_context
def mcp_cmd(ctx: click.Context, transport: str) -> None:
    """Start the PromptGate MCP server.

    Add to Claude Desktop config:

        {\"command\": \"promptgate\", \"args\": [\"mcp\", \"--stdio\"]}
    """
    from promptgate.mcp_adapter import run_stdio
    run_stdio(db_path=ctx.obj["db"])


@main.command("purge")
@click.option("--days", default=7, show_default=True, help="Delete contracts older than N days.")
@click.pass_context
def purge_cmd(ctx: click.Context, days: int) -> None:
    """Delete stale compiled contract files.

    Examples:

        promptgate purge --days 3
    """
    deleted = purge_stale(max_age_seconds=days * 86400)
    click.echo(f"Deleted {deleted} stale contract file(s).")

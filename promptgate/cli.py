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


@main.command("watch")
@click.argument("directory", default="prompts", type=click.Path())
@click.pass_context
def watch_cmd(ctx: click.Context, directory: str) -> None:
    """Watch a directory for YAML changes and auto-upsert prompts.

    Blocks until Ctrl+C. Uses OS-native file events (inotify on Linux).

    Examples:

        pgate watch

        pgate watch ./my_prompts
    """
    from promptgate.watcher import watch as pg_watch
    try:
        pg_watch(directory, db_path=ctx.obj["db"])
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc


@main.group("keys")
def keys_group() -> None:
    """Manage encrypted API keys stored in ~/.promptgate/keys.enc."""


@keys_group.command("set")
@click.argument("name")
@click.argument("value")
def keys_set(name: str, value: str) -> None:
    """Store an API key encrypted at rest.

    Examples:

        pgate keys set openai sk-...

        pgate keys set anthropic sk-ant-...
    """
    from promptgate.keystore import set_key
    set_key(name, value)
    click.echo(f"Stored '{name}'.")


@keys_group.command("get")
@click.argument("name")
def keys_get(name: str) -> None:
    """Retrieve and print a stored API key.

    Examples:

        pgate keys get openai
    """
    from promptgate.keystore import get_key
    value = get_key(name)
    if value is None:
        raise click.ClickException(f"Key '{name}' not found.")
    click.echo(value)


@keys_group.command("list")
def keys_list() -> None:
    """List stored key names (values are never shown).

    Examples:

        pgate keys list
    """
    from promptgate.keystore import list_keys
    names = list_keys()
    if not names:
        click.echo("No keys stored.")
        return
    for name in names:
        click.echo(f"  {name}")


@keys_group.command("rm")
@click.argument("name")
def keys_rm(name: str) -> None:
    """Delete a stored API key.

    Examples:

        pgate keys rm openai
    """
    from promptgate.keystore import delete_key
    if not delete_key(name):
        raise click.ClickException(f"Key '{name}' not found.")
    click.echo(f"Removed '{name}'.")


@main.command("run")
@click.argument("prompt_id")
@click.option("--payload", "-p", default="{}", help="JSON payload string.")
@click.option("--model", "-m", default=None, help="LiteLLM model string. Falls back to active profile default_model.")
@click.option("--max-retries", default=3, show_default=True, help="Max LLM call attempts.")
@click.option("--user-message", default=None, help="Custom user turn (default: serialised payload).")
@click.option("--api-base", default=None, help="Override api_base URL. Falls back to active profile litellm_api_base.")
@click.option("--api-key", default=None, help="Override API key. Falls back to keystore key named after active profile.")
@click.option("--profile", default=None, help="Profile name to use (default: active profile).")
@click.pass_context
def run_cmd(ctx: click.Context, prompt_id: str, payload: str, model: str | None, max_retries: int, user_message: str | None, api_base: str | None, api_key: str | None, profile: str | None) -> None:
    """Compile a prompt, call LLM, validate output, retry on failure.

    Provider settings (api_base, api_key, model) resolve in this order:
    CLI flag > active profile > environment variables.

    API key is read from the keystore under the profile name:
    ``pgate keys set <profile_name> <api_key>``

    Requires litellm: pip install pgate[litellm]

    Examples:

        pgate run sales_v1 --payload '{"period": "2024-01"}'

        pgate run sales_v1 --model openrouter/openai/gpt-5-mini --profile routerai
    """
    try:
        from promptgate.runner import run as pg_run
    except ImportError as exc:
        raise click.ClickException("litellm not installed: pip install pgate[litellm]") from exc

    from promptgate.profiles import get_profile
    from promptgate.keystore import get_key

    try:
        prof = get_profile(profile)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    resolved_model = model or prof.get("default_model")
    if not resolved_model:
        raise click.ClickException("No model specified. Pass --model or set default_model in the active profile.")

    resolved_api_base = api_base or prof.get("litellm_api_base")
    resolved_api_key = api_key or get_key(prof.get("_name", profile or "default"))

    litellm_kwargs: dict = {}
    if resolved_api_base:
        litellm_kwargs["api_base"] = resolved_api_base
    if resolved_api_key:
        litellm_kwargs["api_key"] = resolved_api_key

    data: dict = json.loads(payload)
    result = pg_run(prompt_id, data, resolved_model, db_path=ctx.obj["db"], max_retries=max_retries, user_message=user_message, litellm_kwargs=litellm_kwargs or None)
    if result.ok:
        click.echo(json.dumps(result.data, ensure_ascii=False, indent=2))
    else:
        click.echo(f"[FAILED after {result.attempts} attempt(s)]", err=True)
        click.echo(result.raw_output, err=True)
        raise SystemExit(1)


@main.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8080, show_default=True, help="Bind port.")
@click.option("--open", "open_browser", is_flag=True, default=False, help="Open browser to UI automatically.")
@click.pass_context
def serve_cmd(ctx: click.Context, host: str, port: int, open_browser: bool) -> None:
    """Start the PGate REST API server + local web UI.

    Requires fastapi + uvicorn: pip install pgate[serve]

    Examples:

        pgate serve

        pgate serve --open

        pgate serve --host 0.0.0.0 --port 9000
    """
    try:
        import uvicorn
        from promptgate.api import make_app
    except ImportError as exc:
        raise click.ClickException("fastapi/uvicorn not installed: pip install pgate[serve]") from exc

    app = make_app(ctx.obj["db"], start_worker=True)
    ui_url = f"http://{host}:{port}/ui/"
    click.echo(f"PGate API  → http://{host}:{port}")
    click.echo(f"PGate UI   → {ui_url}")
    if open_browser:
        import threading, webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(ui_url)).start()
    uvicorn.run(app, host=host, port=port)


@main.group("chain", invoke_without_command=True)
@click.pass_context
def chain_group(ctx: click.Context) -> None:
    """Manage and run prompt chains.

    Without a subcommand, lists all chains.

    Examples:

        pgate chain list

        pgate chain add --file chains/pipeline.yaml

        pgate chain run my_chain --payload '{}'
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(chain_list)


@chain_group.command("list")
@click.pass_context
def chain_list(ctx: click.Context) -> None:
    """List all stored chains.

    Examples:

        pgate chain list
    """
    from promptgate.chains import list_chains
    chains = list_chains(ctx.obj["db"])
    if not chains:
        click.echo("No chains stored.")
        return
    for c in chains:
        click.echo(f"  {c.id}  {c.name}  ({len(c.steps)} steps)")


@chain_group.command("show")
@click.argument("chain_id")
@click.pass_context
def chain_show(ctx: click.Context, chain_id: str) -> None:
    """Show chain definition as YAML.

    Examples:

        pgate chain show my_chain
    """
    from promptgate.chains import get_chain
    import yaml as _yaml
    c = get_chain(chain_id, ctx.obj["db"])
    if c is None:
        raise click.ClickException(f"Chain '{chain_id}' not found.")
    click.echo(_yaml.dump(c.model_dump(), default_flow_style=False, allow_unicode=True))


@chain_group.command("add")
@click.option("--file", "-f", "file_path", required=True, type=click.Path(exists=True), help="YAML chain definition file.")
@click.pass_context
def chain_add(ctx: click.Context, file_path: str) -> None:
    """Add or update a chain from a YAML file.

    Examples:

        pgate chain add --file chains/pipeline.yaml
    """
    from promptgate.chains import load_chain_from_yaml, upsert_chain
    chain = load_chain_from_yaml(file_path)
    upsert_chain(chain, ctx.obj["db"])
    click.echo(f"Added chain: {chain.id} ({chain.name})")


@chain_group.command("rm")
@click.argument("chain_id")
@click.pass_context
def chain_rm(ctx: click.Context, chain_id: str) -> None:
    """Delete a chain by ID.

    Examples:

        pgate chain rm my_chain
    """
    from promptgate.chains import delete_chain
    if not delete_chain(chain_id, ctx.obj["db"]):
        raise click.ClickException(f"Chain '{chain_id}' not found.")
    click.echo(f"Removed chain '{chain_id}'.")


@chain_group.command("run")
@click.argument("chain_id")
@click.option("--payload", "-p", default="{}", help="JSON initial payload.")
@click.option("--max-retries", default=3, show_default=True, help="Max LLM retries per step.")
@click.option("--api-base", default=None, help="Override api_base URL. Falls back to active profile litellm_api_base.")
@click.option("--api-key", default=None, help="Override API key. Falls back to keystore key named after active profile.")
@click.option("--profile", default=None, help="Profile name to use (default: active profile).")
@click.pass_context
def chain_run(ctx: click.Context, chain_id: str, payload: str, max_retries: int, api_base: str | None, api_key: str | None, profile: str | None) -> None:
    """Run a chain with an initial payload.

    Provider settings resolve from active profile (api_base, api_key).
    Store API key with: ``pgate keys set <profile_name> <api_key>``

    Requires litellm: pip install pgate[litellm]

    Examples:

        pgate chain run my_chain --payload '{"topic": "AI"}'

        pgate chain run my_chain --profile routerai --payload '{"topic": "AI"}'
    """
    from promptgate.profiles import get_profile
    from promptgate.keystore import get_key

    try:
        prof = get_profile(profile)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    resolved_api_base = api_base or prof.get("litellm_api_base")
    resolved_api_key = api_key or get_key(prof.get("_name", profile or "default"))

    litellm_kwargs: dict = {}
    if resolved_api_base:
        litellm_kwargs["api_base"] = resolved_api_base
    if resolved_api_key:
        litellm_kwargs["api_key"] = resolved_api_key

    data: dict = json.loads(payload)
    try:
        from promptgate.chains import run_chain
        result = run_chain(chain_id, data, db_path=ctx.obj["db"], max_retries_per_step=max_retries, litellm_kwargs=litellm_kwargs or None)
    except ImportError as exc:
        raise click.ClickException("litellm not installed: pip install pgate[litellm]") from exc
    if result.ok:
        click.echo(json.dumps(result.context, ensure_ascii=False, indent=2))
    else:
        click.echo(f"[FAILED at step {result.failed_step}]", err=True)
        raise SystemExit(1)


@main.group("profile", invoke_without_command=True)
@click.pass_context
def profile_group(ctx: click.Context) -> None:
    """Manage named environment profiles (dev/staging/prod).

    Without a subcommand, lists all profiles.

    Examples:

        pgate profile list

        pgate profile add dev --db ~/.promptgate/dev.sqlite

        pgate profile set dev
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(profile_list)


@profile_group.command("list")
def profile_list() -> None:
    """List all profiles with default marker.

    Examples:

        pgate profile list
    """
    from promptgate.profiles import list_profiles
    profiles = list_profiles()
    if not profiles:
        click.echo("No profiles configured.")
        return
    for name, is_default in profiles:
        marker = "* " if is_default else "  "
        click.echo(f"{marker}{name}")


@profile_group.command("show")
@click.argument("name", default=None, required=False)
def profile_show(name: str | None) -> None:
    """Show resolved config for a profile (default if name omitted).

    Examples:

        pgate profile show

        pgate profile show staging
    """
    from promptgate.profiles import get_profile
    try:
        p = get_profile(name)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    for k, v in p.items():
        click.echo(f"  {k}: {v}")


@profile_group.command("add")
@click.argument("name")
@click.option("--db", "db_path", default=None, help="Path to SQLite DB.")
@click.option("--cache-dir", default=None, help="Contract cache directory.")
@click.option("--model", "default_model", default=None, help="Default LiteLLM model.")
@click.option("--api-base", "litellm_api_base", default=None, help="Custom LiteLLM API base URL.")
def profile_add(name: str, db_path: str | None, cache_dir: str | None, default_model: str | None, litellm_api_base: str | None) -> None:
    """Create or update a named profile.

    Examples:

        pgate profile add dev --db ~/.promptgate/dev.sqlite --model gpt-4o-mini
    """
    from promptgate.profiles import save_profile
    config: dict = {}
    if db_path:
        config["db_path"] = db_path
    if cache_dir:
        config["cache_dir"] = cache_dir
    if default_model:
        config["default_model"] = default_model
    if litellm_api_base:
        config["litellm_api_base"] = litellm_api_base
    save_profile(name, config)
    click.echo(f"Saved profile '{name}'.")


@profile_group.command("set")
@click.argument("name")
def profile_set(name: str) -> None:
    """Set the default profile.

    Examples:

        pgate profile set prod
    """
    from promptgate.profiles import set_default_profile
    try:
        set_default_profile(name)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Default profile set to '{name}'.")


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


@main.command("migrate")
@click.pass_context
def migrate_cmd(ctx: click.Context) -> None:
    """Apply pending platform schema migrations (users, invites, audit…).

    Examples:

        pgate migrate
    """
    from promptgate.migrations import run_migrations
    applied = run_migrations(ctx.obj["db"])
    if applied:
        click.echo("Applied: " + ", ".join(applied))
    else:
        click.echo("Already up to date.")


@main.group("admin")
def admin_group() -> None:
    """Platform administration: bootstrap admins, manage invites."""


@admin_group.command("create-admin")
@click.option("--username", required=True, help="Admin username.")
@click.option("--email", required=True, help="Admin email.")
@click.option("--password", default=None, help="Password (prompted securely if omitted).")
@click.pass_context
def create_admin(ctx: click.Context, username: str, email: str, password: str | None) -> None:
    """Create an admin account (bootstrap the platform).

    Examples:

        pgate admin create-admin --username alex --email alex@example.com
    """
    from promptgate.migrations import run_migrations
    from promptgate.auth.db import AuthDB, AuthError

    run_migrations(ctx.obj["db"])
    if password is None:
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    if len(password) < 8:
        raise click.ClickException("Password must be at least 8 characters.")
    try:
        user = AuthDB(ctx.obj["db"]).create_user(username, email, password, "admin")
    except AuthError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created admin '{user['username']}' (id={user['id']}).")


@admin_group.command("invite")
@click.option("--role", default="prompter",
              type=click.Choice(["admin", "prompter", "validator", "guest"]),
              show_default=True, help="Role granted by this invite.")
@click.option("--expires-hours", default=720, show_default=True,
              help="Validity window in hours (0 = never expires).")
@click.option("--multi", is_flag=True, help="Reusable invite (default is one-time).")
@click.pass_context
def admin_invite(ctx: click.Context, role: str, expires_hours: int, multi: bool) -> None:
    """Generate an invite token.

    Examples:

        pgate admin invite --role prompter
        pgate admin invite --role validator --expires-hours 168
    """
    from promptgate.migrations import run_migrations
    from promptgate.auth.db import AuthDB

    run_migrations(ctx.obj["db"])
    invite = AuthDB(ctx.obj["db"]).create_invite(
        role=role, created_by=None,
        expires_hours=expires_hours or None, one_time=not multi,
    )
    click.echo(f"Invite token ({role}): {invite['token']}")
    click.echo(f"Register link: /#/register?invite={invite['token']}")


@admin_group.command("requests")
@click.option("--status", default="pending", help="Filter by status (pending|approved|rejected|all).")
@click.pass_context
def admin_requests(ctx: click.Context, status: str) -> None:
    """List registration requests.

    Examples:

        pgate admin requests
        pgate admin requests --status all
    """
    from promptgate.migrations import run_migrations
    from promptgate.auth.db import AuthDB

    run_migrations(ctx.obj["db"])
    rows = AuthDB(ctx.obj["db"]).list_registration_requests(None if status == "all" else status)
    if not rows:
        click.echo("No registration requests.")
        return
    for r in rows:
        click.echo(f"  #{r['id']}  {r['email']:<30} [{r['status']}]  {r['reason'][:40]}")

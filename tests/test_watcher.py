"""Tests for file watcher auto-upsert behavior."""
import time
import threading
import pytest
from pathlib import Path

from promptgate.storage import SQLiteBackend
from promptgate.watcher import watch


def _poll_until(condition, timeout: float = 4.0, interval: float = 0.1) -> bool:
    """Poll condition() until it returns True or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return False


def _start_watcher(prompts_dir: Path, db_path: Path) -> tuple[threading.Event, threading.Thread]:
    """Start watcher in background thread; returns (stop_event, thread)."""
    stop = threading.Event()

    def _run():
        watch(prompts_dir, db_path, stop_event=stop)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return stop, t


def test_watch_raises_for_missing_dir(tmp_path: Path):
    """watch() raises FileNotFoundError for non-existent directory."""
    with pytest.raises(FileNotFoundError):
        watch(tmp_path / "nonexistent", tmp_path / "db.sqlite")


def test_watch_auto_upserts_yaml(tmp_path: Path):
    """Writing a valid YAML file into the watched dir causes it to appear in DB."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    db_path = tmp_path / "db.sqlite"

    stop, t = _start_watcher(prompts_dir, db_path)
    time.sleep(0.5)  # give observer time to register inotify watches

    yaml_content = (
        "id: watch_test_prompt\n"
        "name: Watch Test\n"
        "schema:\n"
        "  type: object\n"
        "  properties:\n"
        "    x:\n"
        "      type: string\n"
        'template: "Hello {{ x }}"\n'
    )
    (prompts_dir / "watch_test.yaml").write_text(yaml_content, encoding="utf-8")

    backend = SQLiteBackend(db_path)
    backend.init()
    found = _poll_until(lambda: backend.get("watch_test_prompt") is not None)

    stop.set()
    t.join(timeout=3)

    assert found, "Prompt not upserted within 4s after YAML file was written"
    assert backend.get("watch_test_prompt").name == "Watch Test"


def test_watch_skips_non_yaml(tmp_path: Path):
    """Non-YAML files written to watched dir are silently ignored."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    db_path = tmp_path / "db.sqlite"

    stop, t = _start_watcher(prompts_dir, db_path)
    time.sleep(0.5)

    (prompts_dir / "notes.txt").write_text("not a prompt", encoding="utf-8")
    time.sleep(0.6)
    stop.set()
    t.join(timeout=3)

    backend = SQLiteBackend(db_path)
    backend.init()
    assert backend.list_all() == []

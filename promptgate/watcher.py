"""File watcher: auto-upsert prompt YAML files on change."""
from __future__ import annotations

import time
from pathlib import Path

import yaml
from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from promptgate.models import PromptConfig
from promptgate.storage import SQLiteBackend


class _YamlHandler(FileSystemEventHandler):
    def __init__(self, backend: SQLiteBackend) -> None:
        self._backend = backend

    def _process(self, path: str) -> None:
        p = Path(path)
        if p.suffix not in {".yaml", ".yml"}:
            return
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            prompt = PromptConfig.model_validate(data)
            self._backend.upsert(prompt)
            logger.info("Auto-upserted '{}' from {}", prompt.id, p.name)
        except Exception as exc:
            logger.warning("Failed to process {}: {}", p.name, exc)

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._process(event.src_path)

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._process(event.src_path)


def watch(
    directory: str | Path,
    db_path: str | Path,
    stop_event: "threading.Event | None" = None,
) -> None:
    """Watch a directory for YAML prompt file changes and auto-upsert.

    Blocks until Ctrl+C or ``stop_event`` is set. Uses OS-native
    inotify/FSEvents — zero polling overhead.

    Args:
        directory: Path to directory containing ``.yaml``/``.yml`` prompt files.
        db_path: Path to SQLite database.
        stop_event: Optional :class:`threading.Event`; when set, watch exits cleanly.
            Useful for testing and programmatic control.

    Examples:
        >>> # watch() blocks — use in CLI or thread; not suitable for doctest
    """
    import threading as _threading

    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    backend = SQLiteBackend(db_path)
    backend.init()

    observer = Observer()
    handler = _YamlHandler(backend)
    observer.schedule(handler, str(directory), recursive=False)
    observer.start()
    logger.info("Watching {} for YAML changes (Ctrl+C to stop)", directory)
    try:
        while observer.is_alive():
            if stop_event is not None and stop_event.is_set():
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()

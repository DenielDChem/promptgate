"""Default job handlers (P4). Real LLM work is lazy-imported so the queue and
its tests don't require the ``litellm`` extra; tests inject fakes instead.

Each handler ``(job, store)`` updates progress via ``store``, polls
``store.is_cancel_requested(job["id"])`` between steps (raising
:class:`promptgate.jobs.worker.JobCancelled`), and returns a result dict.
"""
from __future__ import annotations

from pathlib import Path

from promptgate.jobs.worker import JobCancelled


def _check_cancel(store, job_id: int) -> None:
    if store.is_cancel_requested(job_id):
        raise JobCancelled


def _run_validation(db_path, prompt_id, model_id, params, created_by):
    """Shared: run deep validation for one prompt, persist, return a summary."""
    from promptgate.quality import deep, scorers
    from promptgate.quality.store import QualityStore
    from promptgate.prompts_service import PromptMetaStore

    cases = params.get("cases")
    if not cases:
        raise ValueError("validation job requires params.cases (a non-empty test set)")
    generate_fn = scorers.build_generate_fn(prompt_id, model_id, db_path)
    judge_fn = scorers.build_judge_fn(model_id)
    result = deep.run_validation(cases, generate_fn, judge_fn, repeats=params.get("repeats", 3))
    meta = PromptMetaStore(db_path).get_meta(prompt_id)
    run_id = QualityStore(db_path).save_run(
        prompt_id, meta["current_version"] if meta else None, model_id, result, created_by,
    )
    return {"run_id": run_id, "color": result.color, "determinism": result.determinism,
            "comprehension": result.comprehension, "hallucination": result.hallucination}


def default_handlers(db_path: str | Path) -> dict:
    """Build the production handler registry bound to ``db_path``."""

    def validation(job: dict, store) -> dict:
        _check_cancel(store, job["id"])
        store.update_progress(job["id"], 0, 1)
        summary = _run_validation(
            db_path, job["prompt_id"], job["model_id"], job["params"], job.get("created_by"),
        )
        store.update_progress(job["id"], 1, 1)
        return summary

    def mass_test(job: dict, store) -> dict:
        prompts = job["params"].get("prompts") or ([job["prompt_id"]] if job["prompt_id"] else [])
        if not prompts:
            raise ValueError("mass_test job requires params.prompts (a list of prompt ids)")
        total = len(prompts)
        store.update_progress(job["id"], 0, total)
        runs = []
        for i, pid in enumerate(prompts):
            _check_cancel(store, job["id"])
            runs.append({"prompt_id": pid, **_run_validation(
                db_path, pid, job["model_id"], job["params"], job.get("created_by"))})
            store.update_progress(job["id"], i + 1, total)
        return {"runs": runs}

    def generation(job: dict, store) -> dict:
        import litellm  # lazy
        description = job["params"].get("description", "")
        if not description:
            raise ValueError("generation job requires params.description")
        store.update_progress(job["id"], 0, 1)
        resp = litellm.completion(model=job["model_id"], messages=[
            {"role": "system", "content": "You generate a single reusable prompt template."},
            {"role": "user", "content": f"Write a prompt template for: {description}. "
                                         "Use {{ variable }} placeholders. Output only the template."},
        ])
        store.update_progress(job["id"], 1, 1)
        return {"template": resp.choices[0].message.content}

    return {"validation": validation, "mass_test": mass_test, "generation": generation}

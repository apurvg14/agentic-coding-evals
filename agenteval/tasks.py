"""Task discovery and loading.

A task is a directory containing:
  task.json     metadata (id, title, prompt, optional prompt_vague)
  workspace/    the starting (buggy/incomplete) code the agent may edit
  solution/     the reference fix (used by the `reference` agent and as an oracle)
  check.py      a deterministic grader: run inside the solved workspace, exit 0 = pass
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Task:
    id: str
    title: str
    prompt: str
    dir: Path
    prompt_vague: str | None = None
    check: str = "check.py"
    extra: dict = field(default_factory=dict)

    @property
    def workspace_dir(self) -> Path:
        return self.dir / "workspace"

    @property
    def solution_dir(self) -> Path:
        return self.dir / "solution"

    @property
    def check_path(self) -> Path:
        return self.dir / self.check


def load_task(task_dir: Path) -> Task:
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    return Task(
        id=meta["id"],
        title=meta.get("title", meta["id"]),
        prompt=meta["prompt"],
        prompt_vague=meta.get("prompt_vague"),
        check=meta.get("check", "check.py"),
        dir=task_dir,
        extra={k: v for k, v in meta.items()
               if k not in {"id", "title", "prompt", "prompt_vague", "check"}},
    )


def discover_tasks(suite_dir: Path, only: list[str] | None = None) -> list[Task]:
    tasks = []
    for p in sorted(Path(suite_dir).iterdir()):
        if (p / "task.json").exists():
            t = load_task(p)
            if only and t.id not in only:
                continue
            tasks.append(t)
    return tasks

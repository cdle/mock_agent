from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LaunchContext:
    raw: dict[str, Any]
    json_file: Path

    @property
    def task(self) -> dict[str, Any]:
        return self.raw.get("task", {})

    @property
    def worker(self) -> dict[str, Any]:
        return self.raw.get("worker", {})

    @property
    def model(self) -> dict[str, Any]:
        return self.raw.get("model", {})

    @property
    def repository(self) -> dict[str, Any]:
        return self.raw.get("repository", {})

    @property
    def paths(self) -> dict[str, Any]:
        return self.raw.get("paths", {})

    @property
    def user(self) -> dict[str, Any]:
        return self.raw.get("user", {})

    @property
    def task_id(self) -> str:
        return str(self.task.get("task_id", ""))

    @property
    def user_id(self) -> int:
        return int(self.task.get("user_id", self.user.get("user_id", 0)) or 0)

    @property
    def worker_base_url(self) -> str:
        return str(self.worker.get("base_url", "")).rstrip("/")

    @property
    def worker_token(self) -> str:
        return str(self.worker.get("token", ""))

    @property
    def worker_id(self) -> str:
        return str(self.worker.get("worker_id", ""))

    @property
    def workspace(self) -> str:
        return str(self.paths.get("workspace", ""))

    @property
    def skills_dir(self) -> str:
        return str(self.paths.get("skills_dir", ""))

    @property
    def memory_file(self) -> str:
        return str(self.paths.get("memory_file", ""))

    @property
    def memory_content(self) -> str:
        return str(self.user.get("memory_content", ""))

    @property
    def skills(self) -> list[dict[str, Any]]:
        return list(self.user.get("skills", []) or [])



def load_launch_context(json_file: str | Path) -> LaunchContext:
    path = Path(json_file)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return LaunchContext(raw=raw, json_file=path)



def parse_json_file_arg(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonFile", required=True)
    args = parser.parse_args(argv)
    return Path(args.jsonFile)

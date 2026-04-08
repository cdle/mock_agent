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
    def schema_version(self) -> str:
        return str(self.raw.get("schema_version", ""))

    @property
    def task(self) -> dict[str, Any]:
        return dict(self.raw.get("task", {}) or {})

    @property
    def worker(self) -> dict[str, Any]:
        return dict(self.raw.get("worker", {}) or {})

    @property
    def model(self) -> dict[str, Any]:
        return dict(self.raw.get("model", {}) or {})

    @property
    def repository(self) -> dict[str, Any]:
        return dict(self.raw.get("repository", {}) or {})

    @property
    def paths(self) -> dict[str, Any]:
        return dict(self.raw.get("paths", {}) or {})

    @property
    def user(self) -> dict[str, Any]:
        return dict(self.raw.get("user", {}) or {})

    @property
    def task_id(self) -> str:
        return str(self.task.get("task_id", ""))

    @property
    def user_id(self) -> int:
        return int(self.task.get("user_id", self.user.get("user_id", 0)) or 0)

    @property
    def task_status(self) -> str:
        return str(self.task.get("status", ""))

    @property
    def branch(self) -> str:
        return str(self.task.get("branch", ""))

    @property
    def commit_id(self) -> str:
        return str(self.task.get("commit_id", ""))

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
    def repository_alias(self) -> str:
        return str(self.repository.get("alias", ""))

    @property
    def repository_url(self) -> str:
        return str(self.repository.get("repo_url", ""))

    @property
    def repository_launch_command(self) -> str:
        return str(self.repository.get("launch_command", ""))

    @property
    def repository_branch(self) -> str:
        return str(self.repository.get("branch", ""))

    @property
    def repository_commit_id(self) -> str:
        return str(self.repository.get("commit_id", ""))

    @property
    def model_alias(self) -> str:
        return str(self.model.get("alias", ""))

    @property
    def model_provider(self) -> str:
        return str(self.model.get("provider", ""))

    @property
    def model_vendor(self) -> str:
        return str(self.model.get("vendor", ""))

    @property
    def model_base_url(self) -> str:
        return str(self.model.get("base_url", "")).rstrip("/")

    @property
    def model_api_key(self) -> str:
        return str(self.model.get("api_key", ""))

    @property
    def model_name(self) -> str:
        return str(self.model.get("model", ""))

    @property
    def model_headers(self) -> dict[str, str]:
        return dict(self.model.get("headers", {}) or {})

    @property
    def model_options(self) -> dict[str, Any]:
        return dict(self.model.get("options", {}) or {})

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
    def launch_config_file(self) -> str:
        return str(self.paths.get("launch_config_file", ""))

    @property
    def memory_path(self) -> str:
        return str(self.user.get("memory_path", self.memory_file))

    @property
    def memory_content(self) -> str:
        return str(self.user.get("memory_content", ""))

    @property
    def skills(self) -> list[dict[str, Any]]:
        return [dict(item or {}) for item in (self.user.get("skills", []) or [])]



def load_launch_context(json_file: str | Path) -> LaunchContext:
    path = Path(json_file)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return LaunchContext(raw=raw, json_file=path)



def parse_json_file_arg(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonFile", required=True)
    args = parser.parse_args(argv)
    return Path(args.jsonFile)

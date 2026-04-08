from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

from .launch import LaunchContext


class WorkerClient:
    def __init__(self, *, base_url: str, token: str, task_id: str, owner_worker_id: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.task_id = task_id
        self.owner_worker_id = owner_worker_id

    @classmethod
    def from_context(cls, context: LaunchContext) -> "WorkerClient":
        return cls(
            base_url=context.worker_base_url,
            token=context.worker_token,
            task_id=context.task_id,
            owner_worker_id=context.worker_id,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Worker-Token": self.token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def pull_messages(self, limit: int = 10) -> list[dict[str, Any]]:
        response = self._post(
            "/internal/agent/pull_messages",
            {
                "task_id": self.task_id,
                "limit": limit,
            },
        )
        return ((response.get("data") or {}).get("list") or [])

    def report_message(
        self,
        *,
        message_id: int,
        role: str,
        content: str,
        status: str,
        append: bool = False,
        client_message_id: str = "",
    ) -> dict[str, Any]:
        return self._post(
            "/internal/agent/report_message",
            {
                "task_id": self.task_id,
                "message_id": message_id,
                "client_message_id": client_message_id,
                "role": role,
                "content": content,
                "status": status,
                "append": append,
            },
        )

    def update_title(self, title: str) -> dict[str, Any]:
        return self._post(
            "/internal/agent/update_title",
            {
                "task_id": self.task_id,
                "title": title,
            },
        )

    def report_log(self, *, log_id: int, level: str, content: str) -> dict[str, Any]:
        return self._post(
            "/internal/agent/report_log",
            {
                "task_id": self.task_id,
                "log_id": log_id,
                "level": level,
                "content": content,
            },
        )

    def report_dag(self, dag: dict[str, Any]) -> dict[str, Any]:
        return self._post(
            "/internal/agent/report_dag",
            {
                "task_id": self.task_id,
                "dag": dag,
            },
        )

    def report_result(self, *, status: str, error_message: str = "", stop_reason: str = "") -> dict[str, Any]:
        return self._post(
            "/internal/agent/report_result",
            {
                "task_id": self.task_id,
                "status": status,
                "error_message": error_message,
                "stop_reason": stop_reason,
            },
        )

    def heartbeat(self) -> dict[str, Any]:
        if not self.owner_worker_id:
            return {}
        return self._post(
            "/internal/agent/heartbeat",
            {
                "task_id": self.task_id,
                "owner_worker_id": self.owner_worker_id,
            },
        )

    def stream_text(
        self,
        *,
        message_id: int,
        role: str,
        text: str,
        chunk_size: int = 24,
        delay_seconds: float = 0.0,
    ) -> None:
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)] or [""]
        self.report_message(message_id=message_id, role=role, content=chunks[0], status="streaming", append=False)
        for chunk in chunks[1:]:
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            self.report_message(message_id=message_id, role=role, content=chunk, status="streaming", append=True)
        self.report_message(message_id=message_id, role=role, content="", status="completed", append=False)

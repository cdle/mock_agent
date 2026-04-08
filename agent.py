#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import sys
import time
import urllib.error
import urllib.request
from typing import Any


from mpai_agent_sdk import LaunchContext, WorkerClient, load_launch_context  # noqa: E402
from mpai_agent_sdk.launch import parse_json_file_arg  # noqa: E402

RUNNING = True


class Sequence:
    def __init__(self, start: int = 1):
        self.value = start

    def next(self) -> int:
        current = self.value
        self.value += 1
        return current


class OpenAICompatibleAgent:
    def __init__(self, context: LaunchContext):
        self.context = context
        self.client = WorkerClient.from_context(context)
        self.message_seq = Sequence(1)
        self.log_seq = Sequence(1)
        self.last_heartbeat_at = 0.0
        self.heartbeat_interval = 10.0
        self.poll_interval = 1.0

    def report_log(self, level: str, content: str) -> None:
        self.client.report_log(log_id=self.log_seq.next(), level=level, content=content)

    def report_dag(self, state: str, current_message_id: int | None = None) -> None:
        self.client.report_dag({
            "task_id": self.context.task_id,
            "state": state,
            "current_message_id": current_message_id,
            "updated_at": time.time(),
        })

    def maybe_heartbeat(self) -> None:
        now = time.time()
        if now - self.last_heartbeat_at < self.heartbeat_interval:
            return
        if self.context.worker_id:
            self.client.heartbeat()
        self.last_heartbeat_at = now

    def build_messages(self, user_content: str) -> list[dict[str, str]]:
        parts: list[str] = []
        if self.context.memory_content:
            parts.append("用户 memory:\n" + self.context.memory_content)
        if self.context.skills:
            rendered = []
            for item in self.context.skills:
                path = item.get("path", "")
                content = item.get("content", "")
                rendered.append(f"## {path}\n{content}".strip())
            parts.append("用户 skills:\n" + "\n\n".join(rendered))
        system_text = "你是接入 MPAI worker 的 agent。基于上下文回复用户。"
        if parts:
            system_text += "\n\n" + "\n\n".join(parts)
        return [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_content},
        ]

    def generate_reply(self, user_content: str) -> str:
        model = self.context.model
        provider = model.get("provider", "")
        if provider == "mock":
            alias = model.get("alias") or model.get("model") or "mock"
            return f"[{alias}] {user_content}"
        if provider != "openai-compatible":
            raise RuntimeError(f"unsupported provider: {provider}")

        base_url = str(model.get("base_url", "")).rstrip("/")
        api_key = str(model.get("api_key", ""))
        model_name = str(model.get("model", ""))
        headers = {"Content-Type": "application/json", **(model.get("headers") or {})}
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": self.build_messages(user_content),
        }
        for key, value in (model.get("options") or {}).items():
            payload[key] = value

        request = urllib.request.Request(
            base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"openai-compatible http error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"openai-compatible request failed: {exc}") from exc

        data = json.loads(raw)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"invalid openai-compatible response: {data}")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "".join(text_parts)
        return str(content or "")

    def handle_user_message(self, item: dict[str, Any]) -> None:
        client_message_id = str(item.get("client_message_id", ""))
        user_content = str(item.get("content", ""))

        user_message_id = self.message_seq.next()
        self.client.report_message(
            message_id=user_message_id,
            client_message_id=client_message_id,
            role="user",
            content=user_content,
            status="completed",
            append=False,
        )
        self.report_log("info", f"confirmed user message client_message_id={client_message_id}")

        assistant_message_id = self.message_seq.next()
        self.report_dag("processing", assistant_message_id)
        reply = self.generate_reply(user_content)
        self.client.stream_text(
            message_id=assistant_message_id,
            role="assistant",
            text=reply,
            chunk_size=24,
            delay_seconds=0.1,
        )
        self.report_log("info", f"completed assistant message message_id={assistant_message_id}")
        self.report_dag("idle", assistant_message_id)

    def bootstrap(self) -> None:
        model = self.context.model
        self.report_log(
            "info",
            f"agent started provider={model.get('provider', '')} model={model.get('model', '')} workspace={self.context.workspace}",
        )
        self.report_dag("idle", None)

    def run(self) -> int:
        self.bootstrap()
        while RUNNING:
            self.maybe_heartbeat()
            items = self.client.pull_messages(limit=10)
            if not items:
                time.sleep(self.poll_interval)
                continue
            for item in items:
                self.handle_user_message(item)
        self.client.report_result(status="stopped", stop_reason="agent_stopped")
        return 0


def handle_stop(signum, frame):
    del signum, frame
    global RUNNING
    RUNNING = False


def main() -> int:
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    context = load_launch_context(parse_json_file_arg())
    agent = OpenAICompatibleAgent(context)
    try:
        return agent.run()
    except Exception as exc:  # noqa: BLE001
        try:
            agent.client.report_result(status="failed", error_message=str(exc))
        except Exception:
            pass
        print(f"agent failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

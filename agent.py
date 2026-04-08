#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import sys
import time
import urllib.error
import urllib.request
from typing import Any


from mpai_agent_sdk import LaunchContext, WorkerClient, load_launch_context, parse_json_file_arg  # noqa: E402

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
        self.dialog_round = 0
        self.max_visible_rounds = 8
        self.title_synced = context.task_title.strip() not in {"", "新任务"}

    def report_log(self, level: str, content: str) -> None:
        self.client.report_log(log_id=self.log_seq.next(), level=level, content=content)

    def build_mock_dag(self, phase: str, current_message_id: int | None = None) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = [
            {
                "id": "d_session",
                "type": "DATA",
                "name": "session_context",
                "desc": "当前会话上下文（mock）",
                "status": "done",
                "output_key": "session_context",
            }
        ]
        edges: list[dict[str, Any]] = []

        if self.dialog_round <= 0:
            nodes.append({
                "id": "s_bootstrap",
                "type": "SKILL",
                "name": "bootstrap_session",
                "desc": "初始化会话 DAG（mock）",
                "status": "done",
                "output_key": "bootstrap_ready",
            })
            edges.append({
                "from": "d_session",
                "to": "s_bootstrap",
                "label": "session_context",
                "reason": "初始化 mock 会话状态",
            })
            return {"nodes": nodes, "edges": edges}

        start_round = max(1, self.dialog_round - self.max_visible_rounds + 1)
        previous_reply_id = ""
        for round_no in range(start_round, self.dialog_round + 1):
            request_id = f"d_round_{round_no}_request"
            intent_id = f"s_round_{round_no}_intent"
            draft_id = f"g_round_{round_no}_draft"
            reply_id = f"t_round_{round_no}_reply"
            is_current_round = round_no == self.dialog_round

            intent_status = "done"
            draft_status = "done"
            reply_status = "done"
            if is_current_round:
                if phase == "processing":
                    draft_status = "running"
                    reply_status = "pending"
                elif phase == "responding":
                    reply_status = "running"
                elif phase == "completed":
                    pass
                else:
                    intent_status = "pending"
                    draft_status = "pending"
                    reply_status = "pending"

            nodes.extend([
                {
                    "id": request_id,
                    "type": "DATA",
                    "name": f"round_{round_no}_request",
                    "desc": f"第 {round_no} 轮用户输入（mock）",
                    "status": "done",
                    "output_key": f"round_{round_no}_request",
                },
                {
                    "id": intent_id,
                    "type": "SKILL",
                    "name": "intent-classification",
                    "desc": "模拟理解当前轮次意图",
                    "status": intent_status,
                    "output_key": f"round_{round_no}_intent" if intent_status == "done" else "",
                },
                {
                    "id": draft_id,
                    "type": "GLUE_CODING",
                    "name": "draft-generation",
                    "desc": "模拟生成候选答复草稿",
                    "status": draft_status,
                    "output_key": f"round_{round_no}_draft" if draft_status in {"done", "running"} else "",
                },
                {
                    "id": reply_id,
                    "type": "TEXT_RESPONSE",
                    "name": "final-response",
                    "desc": "模拟向前端输出答复",
                    "status": reply_status,
                    "output_key": (
                        f"assistant_message_{current_message_id}"
                        if is_current_round and current_message_id is not None and reply_status in {"done", "running"}
                        else (f"round_{round_no}_reply" if reply_status == "done" else "")
                    ),
                },
            ])
            edges.extend([
                {
                    "from": "d_session",
                    "to": intent_id,
                    "label": "session_context",
                    "reason": "使用会话历史辅助当前轮意图理解",
                },
                {
                    "from": request_id,
                    "to": intent_id,
                    "label": "user_request",
                    "reason": "解析当前轮用户输入",
                },
                {
                    "from": intent_id,
                    "to": draft_id,
                    "label": "intent",
                    "reason": "根据意图组织候选答复草稿",
                },
                {
                    "from": draft_id,
                    "to": reply_id,
                    "label": "draft_reply",
                    "reason": "将草稿整理为最终回复",
                },
            ])
            if previous_reply_id:
                edges.append({
                    "from": previous_reply_id,
                    "to": intent_id,
                    "label": "previous_reply",
                    "reason": "后续轮次基于前一轮回复继续推进",
                })
            previous_reply_id = reply_id

        return {"nodes": nodes, "edges": edges}

    def report_dag(self, phase: str, current_message_id: int | None = None) -> None:
        self.client.report_dag(self.build_mock_dag(phase=phase, current_message_id=current_message_id))

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

    def extract_text_parts(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            text_parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    text_parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
                    continue
                if isinstance(text, dict):
                    nested_text = text.get("value")
                    if isinstance(nested_text, str):
                        text_parts.append(nested_text)
            return text_parts
        return []

    def extract_choice_text(self, choice: dict[str, Any]) -> str:
        parts: list[str] = []
        delta = choice.get("delta")
        if isinstance(delta, dict):
            parts.extend(self.extract_text_parts(delta.get("content")))
        message = choice.get("message")
        if isinstance(message, dict):
            parts.extend(self.extract_text_parts(message.get("content")))
        return "".join(parts)

    def generate_reply(self, user_content: str) -> str:
        provider = self.context.model_provider
        if provider == "mock":
            alias = self.context.model_alias or self.context.model_name or "mock"
            return f"[{alias}] {user_content}"
        if provider != "openai-compatible":
            raise RuntimeError(f"unsupported provider: {provider}")

        base_url = self.context.model_base_url
        api_key = self.context.model_api_key
        model_name = self.context.model_name
        headers = {"Content-Type": "application/json", **self.context.model_headers}
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"
        if "User-Agent" not in headers:
            headers["User-Agent"] = "mpai-agent-sdk/0.1"

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": self.build_messages(user_content),
        }
        for key, value in self.context.model_options.items():
            payload[key] = value
        payload["stream"] = True

        request = urllib.request.Request(
            base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                content_type = response.headers.get("Content-Type", "")
                parts: list[str] = []
                if "text/event-stream" in content_type:
                    for line in response:
                        decoded = line.decode("utf-8", errors="replace").strip()
                        if not decoded or not decoded.startswith("data:"):
                            continue
                        payload_line = decoded[5:].strip()
                        if payload_line == "[DONE]":
                            break
                        chunk = json.loads(payload_line)
                        for choice in chunk.get("choices") or []:
                            text = self.extract_choice_text(choice)
                            if text:
                                parts.append(text)
                else:
                    raw = response.read().decode("utf-8")
                    data = json.loads(raw)
                    for choice in data.get("choices") or []:
                        text = self.extract_choice_text(choice)
                        if text:
                            parts.append(text)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"openai-compatible http error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"openai-compatible request failed: {exc}") from exc

        reply = "".join(parts)
        if reply.strip() == "":
            raise RuntimeError("openai-compatible response contained no assistant text")
        return reply

    def handle_user_message(self, item: dict[str, Any]) -> None:
        client_message_id = str(item.get("client_message_id", ""))
        user_content = str(item.get("content", ""))
        self.dialog_round += 1
        if not self.title_synced and user_content.strip():
            try:
                self.client.update_title(user_content)
                self.title_synced = True
            except Exception as exc:  # noqa: BLE001
                self.report_log("warn", f"update title failed: {exc}")

        user_message_id = self.message_seq.next()
        self.client.report_message(
            message_id=user_message_id,
            client_message_id=client_message_id,
            role="user",
            content=user_content,
            status="completed",
            append=False,
        )
        self.report_log("info", f"confirmed user message client_message_id={client_message_id} round={self.dialog_round}")

        assistant_message_id = self.message_seq.next()
        self.report_dag("processing", assistant_message_id)
        reply = self.generate_reply(user_content)
        self.report_dag("responding", assistant_message_id)
        self.client.stream_text(
            message_id=assistant_message_id,
            role="assistant",
            text=reply,
            chunk_size=24,
            delay_seconds=0.1,
        )
        self.report_log("info", f"completed assistant message message_id={assistant_message_id} round={self.dialog_round}")
        self.report_dag("completed", assistant_message_id)

    def bootstrap(self) -> None:
        self.report_log(
            "info",
            "agent started "
            f"provider={self.context.model_provider} "
            f"model={self.context.model_name} "
            f"repo={self.context.repository_alias or self.context.repository_url} "
            f"workspace={self.context.workspace} "
            f"launch_json={self.context.launch_config_file or self.context.json_file}",
        )
        self.report_dag("bootstrap", None)

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

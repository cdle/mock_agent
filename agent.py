#!/usr/bin/env python3
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request


BASE_URL = os.environ["MPAI_WORKER_BASE_URL"].rstrip("/")
WORKER_TOKEN = os.environ["MPAI_WORKER_TOKEN"]
WORKER_ID = os.environ.get("MPAI_WORKER_ID", "")
TASK_ID = os.environ["MPAI_TASK_ID"]

NEXT_MESSAGE_ID = 1
RUNNING = True


def post(path: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Worker-Token": WORKER_TOKEN,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def next_message_id() -> int:
    global NEXT_MESSAGE_ID
    current = NEXT_MESSAGE_ID
    NEXT_MESSAGE_ID += 1
    return current


def report_log(log_id: int, level: str, content: str):
    post(
        "/internal/agent/report_log",
        {
            "task_id": TASK_ID,
            "log_id": log_id,
            "level": level,
            "content": content,
        },
    )


def report_dag(state: str, current_message_id=None):
    payload = {
        "task_id": TASK_ID,
        "dag": {
            "task_id": TASK_ID,
            "state": state,
            "current_message_id": current_message_id,
            "updated_at": time.time(),
        },
    }
    post("/internal/agent/report_dag", payload)


def report_message(message_id: int, role: str, content: str, status: str, append: bool = False, client_message_id: str = ""):
    payload = {
        "task_id": TASK_ID,
        "message_id": message_id,
        "client_message_id": client_message_id,
        "role": role,
        "content": content,
        "status": status,
        "append": append,
    }
    post("/internal/agent/report_message", payload)


def heartbeat():
    if not WORKER_ID:
        return
    post(
        "/internal/agent/heartbeat",
        {
            "task_id": TASK_ID,
            "owner_worker_id": WORKER_ID,
        },
    )


def pull_messages():
    response = post(
        "/internal/agent/pull_messages",
        {
            "task_id": TASK_ID,
            "limit": 10,
        },
    )
    data = response.get("data") or {}
    return data.get("list") or []


def report_result(status: str, error_message: str = "", stop_reason: str = ""):
    post(
        "/internal/agent/report_result",
        {
            "task_id": TASK_ID,
            "status": status,
            "error_message": error_message,
            "stop_reason": stop_reason,
        },
    )


def handle_user_message(item: dict, log_id: int) -> int:
    client_message_id = item.get("client_message_id", "")
    user_content = item.get("content", "")

    user_message_id = next_message_id()
    report_message(
        user_message_id,
        "user",
        user_content,
        "completed",
        append=False,
        client_message_id=client_message_id,
    )
    report_log(log_id, "info", f"received user message client_message_id={client_message_id}")
    log_id += 1

    assistant_message_id = next_message_id()
    reply = f"mock agent received: {user_content}"
    chunks = [
        reply[: min(10, len(reply))],
        reply[min(10, len(reply)) : min(20, len(reply))],
        reply[min(20, len(reply)) :],
    ]
    chunks = [chunk for chunk in chunks if chunk]

    if chunks:
        report_message(assistant_message_id, "assistant", chunks[0], "streaming", append=False)
        time.sleep(0.2)
        for chunk in chunks[1:]:
            report_message(assistant_message_id, "assistant", chunk, "streaming", append=True)
            time.sleep(0.2)
    report_message(assistant_message_id, "assistant", "", "completed", append=False)
    report_dag("idle", assistant_message_id)
    report_log(log_id, "info", f"finished assistant reply message_id={assistant_message_id}")
    return log_id + 1


def handle_stop(signum, frame):
    global RUNNING
    RUNNING = False


def main():
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    log_id = 1
    report_log(log_id, "info", "mock agent started")
    log_id += 1
    report_dag("idle", None)

    last_heartbeat = 0.0
    while RUNNING:
        now = time.time()
        if now - last_heartbeat >= 10:
            try:
                heartbeat()
            except Exception:
                pass
            last_heartbeat = now

        try:
            items = pull_messages()
            if items:
                report_dag("processing", None)
                for item in items:
                    log_id = handle_user_message(item, log_id)
            else:
                time.sleep(1.0)
        except urllib.error.HTTPError as exc:
            report_result("failed", f"http error: {exc.code}")
            return 1
        except Exception as exc:
            report_result("failed", str(exc))
            return 1

    try:
        report_result("stopped", stop_reason="mock_agent_stopped")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

# mock_agent

MPAI 测试 agent，已升级为 `--jsonFile` 启动协议，并内置 Python SDK。

## 能力

- 读取 worker 生成的 `--jsonFile` 启动文件
- 通过 `mpai_agent_sdk` 调用 worker 内部 API
- 支持 `mock` provider 回显模式
- 支持 `openai-compatible` provider，调用 `/chat/completions`
- 上报 user / assistant message、流式 append、DAG、log、result、heartbeat

## 运行

```bash
python3 agent.py --jsonFile /absolute/path/to/.mpai/agent-launch.json
```

## 仓库结构

- `agent.py`: 简易 OpenAI compatible agent
- `mpai_agent_sdk/`: agent 接入 SDK
- `pyproject.toml`: SDK 打包配置

## 约定

`jsonFile` 中至少包含：

- `task.task_id`
- `worker.base_url`
- `worker.token`
- `model.provider` / `model.model`
- `paths.workspace`
- `user.skills` / `user.memory_content`

默认 provider 为 `mock` 时不会调用外部模型接口。

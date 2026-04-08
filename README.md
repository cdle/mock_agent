# mock_agent

MPAI 测试 agent，使用 `--jsonFile` 作为唯一运行参数输入，并内置 Python SDK。

## 能力

- 读取 worker 生成的 `--jsonFile` 启动文件
- 通过 `mpai_agent_sdk` 调用 worker 内部 API
- 支持 `mock` provider 回显模式
- 支持 `openai-compatible` provider，调用 `/chat/completions`
- 上报 user / assistant message、流式 append、DAG、log、result、heartbeat
- 支持通过 SDK 调用 `update_title()` 更新任务标题
- 支持读取 launch json 中的系统级 skills / memory 与用户级 skills / memory
- DAG 使用 MolPlusAgent 风格的 `nodes + edges` 完整快照，节点包含 `status` / `output_key`，方便前端联调
- 不依赖任何环境变量，运行参数全部从 launch json 读取

## 运行

```bash
python3 agent.py --jsonFile /absolute/path/to/.mpai/agent-launch.json
```

## 仓库结构

- `agent.py`: 简易 OpenAI compatible agent
- `mpai_agent_sdk/`: agent 接入 SDK
- `pyproject.toml`: SDK 打包配置

## 约定

`jsonFile` 中应包含 agent 运行所需全部参数，至少包括：

- `task.task_id`
- `task.title`
- `task.branch`
- `task.commit_id`
- `repository.alias` / `repository.repo_url` / `repository.launch_command`
- `worker.base_url`
- `worker.token`
- `worker.worker_id`
- `model.provider` / `model.model`
- `model.base_url` / `model.api_key` / `model.headers` / `model.options`
- `paths.workspace`
- `paths.launch_config_file`
- `paths.system_skills_dir` / `paths.system_memory_file`
- `system.skills` / `system.memory_content`
- `user.skills` / `user.memory_content`

默认 provider 为 `mock` 时不会调用外部模型接口。

当前示例 agent 会在收到首条用户消息时调用 `update_title()`，把任务标题同步为首轮用户输入（worker 侧只负责压缩空白、截断并落库/推送）。

构造模型 prompt 时，示例 agent 会按以下顺序拼接上下文：

1. 系统 memory
2. 系统 skills
3. 用户 memory
4. 用户 skills

# mock_agent

A minimal Python agent for MPAI integration testing.

## Behavior

- pulls user messages from worker
- reports user/assistant messages
- streams assistant deltas
- reports logs
- reports DAG updates
- reports final result on stop/error

## Run

The agent expects these environment variables from MPAI worker:

- `MPAI_TASK_ID`
- `MPAI_WORKER_BASE_URL`
- `MPAI_WORKER_TOKEN`
- `MPAI_WORKER_ID`

Then start with:

```bash
python3 agent.py
```

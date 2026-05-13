# Managed Agents

> ⚠️ **This is NOT a multi-agent swarm.** It's a single-machine batch task runner for free-tier LLMs. The name "Managed Agents" reflects managed task execution, not autonomous multi-agent coordination. For swarm-like behavior, see Hermes Agent's delegate_task and cronjob subsystems.

> A personal batch task runner for free-tier LLMs. Not an agent framework.

This is a lightweight tool for running structured LLM tasks in batches using free API keys. It lives in the gap between "one-off curl" and "full agent framework".

## What it is

- **Batch runner**: Submit N tasks, run them sequentially from a SQLite queue
- **Playbook-driven**: Tasks follow JSON-defined step sequences so cheap models don't need to plan
- **Results as data**: Output is structured JSON, not chatty prose
- **Free-tier only**: Built around OpenRouter free models, no paid keys

## What it is NOT

- NOT a conversational agent (no memory, no multi-turn chat)
- NOT a framework for building AI applications (firn does that)
- NOT autonomous (it runs what you tell it to run, nothing more)

## When to use it

| Use this | Don't use this |
|---|---|
| "Research 10 repos and output a comparison table" | "Chat with me about research findings" |
| "Run the same playbook 50 times with different inputs" | "Plan a complex multi-step project dynamically" |
| "Collect arXiv abstracts on a topic" | "Write a novel with narrative arc" |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Submit    │────▶│ SQLite Queue │────▶│  Dispatcher │
│   Batch     │     │  (task_queue)│     │  (sequential)│
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌────────────────────────────┘
                    ▼
           ┌─────────────────┐
           │  Playbook Runner│───▶ LLM function calls
           │  (per step)     │───▶ Results → JSON
           └─────────────────┘
```

## Quick Start

```bash
# 1. Submit a batch of 5 research tasks
python3 -m core.v2.harness_v2 batch research '{"topic":"MCP","angle":"server"}' 5
# → batch_abc12345

# 2. Run the queue
python3 -m core.v2.harness_v2 dispatch

# 3. Check progress
python3 -m core.v2.harness_v2 status batch_abc12345

# 4. Collect results
python3 -m core.v2.harness_v2 results batch_abc12345
```

## Repo layout

| Path | What |
|---|---|
| `core/v2/` | Current batch runner (playbook + queue + dispatcher) |
| `core/v1/` | Deprecated old code (single-session harness) |
| `playbooks/` | JSON workflow definitions |
| `research/` | Deep-dive reports (not daily noise) |

## Relationship to other projects

- **firn** (Hang's project): The actual AI agent framework. Managed-agents is a satellite tool it may call for batch work.
- **Hermes Agent**: The system I run in. Managed-agents is my personal utility, not part of Hermes core.

## License

MIT

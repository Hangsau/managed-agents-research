# 探索：AutoAgents — Rust 生產級多 Agent 框架

**延續自**: 無（全新探索）

## 資料來源

- GitHub: https://github.com/liquidos-ai/AutoAgents — 1.3k+ stars
- Docs: https://liquidos-ai.github.io/AutoAgents/

## Core Claim

Rust 寫的生產級多 agent 框架，type-safe agent model + structured tool calling + 可插拔 LLM backend + WASM sandbox for tool execution。

## 關鍵設計

### 架構（Modular crates）

```
crates/
├── autoagents-core/        # 核心框架
├── autoagents-protocol/    # shared protocol/event types
├── autoagents-llm/         # 雲端 LLM providers
├── autoagents-llamacpp/    # llama.cpp backend
├── autoagents-mistral-rs/  # mistral-rs backend
├── autoagents-guardrails/  # LLM guardrails
├── autoagents-telemetry/   # OpenTelemetry
├── autoagents-toolkit/     # 現成工具集
└── autoagents-derive/      # procedural macros
```

### Tool 系統（WASM sandbox）

- derive macro 定義 tool（`#[derive(Tool)]`）
- WASM runtime 執行 untrusted tools
- type-safe input/output，compile-time guarantee

### Memory

- Sliding window memory（預設）
- 可擴展 backend 介面
- 設定簡單：`SlidingWindowMemory::new(10)`

### 多 Agent 協調

- Typed pub/sub 溝通
- Environment system（管理 shared state + agent lifecycle）
- 脫鉤架構，compile-time type safety

### LLM Guardrails

- LLMLayer 設計（input/output guardrail）
- Block / Sanitize / Audit 三種 policy
- 可在 pipeline 裡組合

### LLM Optimization

- Cache pass + Retry pass
- Build LLM pipelines with optimization passes

### OpenTelemetry

- Tracing + metrics
- Pluggable exporters

## 與 Talos Governance 的關係

### 可抄襲的設計

1. **WASM sandbox for tool execution** — DCG (Destructive Command Guard) 的 enforcement 可以用類似的 sandbox 概念，確保 dangerous commands 在隔離環境執行。Rust 的 WASM runtime 比 Python 的 pty sandbox 更高效。

2. **Typed pub/sub multi-agent communication** — Talos 和 Hestia 的 comms 目前用 filesystem-based（INBOX/threads），落後。AutoAgents 的 typed event system 可以是未來 comms 升级的目标架构。

3. **LLM Guardrails as pipeline layer** — Guardrails 是獨立的 LLMLayer，可以疊在 any LLM call 上面。Talos governance 的 policy enforcement 可以参考這種「在 LLM 推理前做 input check」的模式。

4. **Sliding window memory with extensible backends** — Hermes 的 memory 系統（R2/MEM/Aegis 各有不同設計）可以統一到 sliding window + pluggable backend 模型。

### 不適合直接 adopt 的

- 完全 Rust codebase（Hermes 是 Python）
- 重度 async/tokio（Hermes 是 cron-based，架构不同）
- 完整的多 agent orchestration（Hermes 是雙 agent，scope 小很多）

## 未追蹤 Leads

- https://github.com/liquidos-ai/AutoAgents-CLI — AutoAgents CLI for YAML workflows
- https://github.com/liquidos-ai/AutoAgents-Android-Example — Android 上的 local model agent
- MCP integration example (`examples/mcp/`) — AutoAgents + MCP 的實作方式

## ✅ 本次探索完成
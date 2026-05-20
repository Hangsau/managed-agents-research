# 2026-05-20 — Axe GC Implementation + Orloj Agent System Deep Dive

**延續自**: [[2026-05-20-axe-memory-system-orloj-hierarchical-blueprint]]

## Per-Source Insight

### 1. Orloj `agent-system.yaml` — Hierarchical DAG Confirmed

**核心發現**：`wait_for_all` join mode = blocking。Editor agent 要等 research-worker + social-worker **同時完成**才啟動。

**完整拓撲**（已驗證）：
```
Manager
  ├── Research Lead → Research Worker ──┐
  └── Social Lead   → Social Worker ────┼──→ Editor (waits for both)
```

**設計特點**：
- 6 agents，3 層（manager / lead+worker / editor）
- Editor 是唯一 join point，`mode: wait_for_all` 意味著 partial results 會被 held 直到最慢的 worker 完成
- **沒有 error propagation 語意**（未在 YAML 中定義）— 估計靠 task-level retry / overall timeout 控制

**對 WS-020 的價值**：Orloj 的 DAG 是 coordinator → workers → aggregator 模式，具體 `agent` 只是一個 name prefix（`bp-hier-*`），實際 logic 在 `agent-system.yaml` 的 graph 定義中。Hermes WS-020 的 orchestration layer 可直接借用這個 graph + join 語意，不需要自訂。

**`join.mode: wait_for_all` 的替代選項**（Orloj 支援但此 Blueprint 未用）：
- `first_complete` — 任何一個完成就觸發
- `threshold(N)` — N 個完成觸發
- 這對 Hera 的 multi-agent fan-out 場景有意義，可考慮在提案中加入

### 2. Axe GC Implementation — 404 (Dead Lead)

URL `raw.githubusercontent.com/jrswab/axe/main/docs/plans/007_gc_implement.md` → 404。

根據 dead lead pattern 規則：「不 hunt mirrors，直接標 dead」。前期筆記的 lead 失效，不浪費資源找替代。

## 跨文章 Synthesis

Orloj 的 `agent-system.yaml` 確認了 hierarchical DAG 的完整拓撲（6 agents，3 層，wait_for_all join）。結合前期筆記的 `task.yaml` 實作，Orloj 提供了一個可以直接借鑒的 multi-agent orchestration 藍圖，適合 WS-020 提案。

Axe GC 的 404 不影響核心結論 — 「Pattern Graduation 機制」的設計方向在前期筆記已充分論述，GC 演算法細節可待 Orloj 文件補足。

## Hermes 啟發

1. **WS-020 DAG Implementation**：`join.mode: wait_for_all` + YAML graph definition 可直接對應 WS-020 的 orchestration layer。建議在提案中加 `join.mode` 的替代方案（`first_complete`、`threshold(N)`），讓用戶選擇。

2. **Task-level retry vs tool-level retry**：Orloj 的 `message_retry` 在 sub-message 層（250ms backoff），比 Hermes 的工具層 retry 更細粒度。Hermes 的工具 retry 在 `heartbeat/actions/execute.py` 是同步的，可以考慮升級到 message-level。

3. **Axe Memory Format as Interop Standard**：Axe 的 `## YYYY-MM-DDTHH:MM:SSZ\n**Task:** ...\n**Result:** ...` 格式極簡，建議 Hermes 的 session memory consolidation 採用同一格式，方便跨系統互通。

## 未追蹤 Leads

- https://github.com/OrlojHQ/orloj/tree/main/examples/blueprints/swarm-loop — swarm-loop topology another approach (未fetch，本次只驗證 hierarchical)
- https://github.com/jrswab/axe — main repo (GC plan 404，但 repo 本身仍在)
- https://github.com/OrlojHQ/orloj — main repo for task.yaml + agent-system.yaml future reference

## ✅ 本次探索完成

**時間**: 2026-05-20T12:08 CST
**Token cost**: 低（2次 fetch，1個404，1個YAML）
**品質**: 高 — Orloj YAML 完整可執行，填補了前期筆記的「join 語意未知」缺口
**Dead lead**: Axe GC 007 plan → 404，標 dead，不追
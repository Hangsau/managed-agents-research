# 探索：Axe Memory System + Orloj Hierarchical Blueprint

**日期**: 2026-05-20 | **來源**: 前期筆記追蹤 | **類型**: 探索

## Per-Source Insight

### 1. Axe Memory System（⭐813）

**核心發現**：記憶系統 = 執行日誌，不是知識庫。

```
AGENTS.md / SKILL.md = instructions（要做什麼）
Memory               = history（發生了什麼）
```

**儲存格式**：plain Markdown，一個 agent 一個檔案（`$XDG_DATA_HOME/axe/memory/<agent>.md`）。

```
## 2026-02-27T03:15:00Z
**Task:** Review PR #42
**Result:** Found 3 issues: missing error handling in auth.go
```

**GC（Garbage Collection）流程**：
1. 讀取完整記憶檔
2. 送 LLM 做 pattern detection
3. 輸出可操作建議（stdout）
4. 修剪檔案（保留 last_n，丟其餘）

```
📋 Patterns found in pr-reviewer (47 runs):
  Recurring issues:
  - Auth error handling flagged 12 times → consider adding to SKILL.md
  - Test coverage gaps found in 8/47 runs → add to review checklist
Memory trimmed: 47 → 10 entries kept
```

**Feedback Loop**：
```
Agent runs → logs to memory → GC finds patterns → suggests fixes
→ user updates SKILL.md → agent improves
```

**設計原則**：
- Just a text file（可讀、可 edit、可 grep）
- No database（無 SQLite、無 embedding、無 magic）
- Axe writes, humans read（append-only from axe side）
- **Patterns graduate to config**：重複 lesson 從 memory → SKILL.md，由人類決定

### 2. Orloj Hierarchical Blueprint

**task.yaml 結構**（完整可執行）：
```yaml
apiVersion: orloj.dev/v1
kind: Task
metadata:
  name: bp-hierarchical-task
spec:
  system: bp-hierarchical-system
  input:
    topic: launch plan for an AI incident response product
  priority: high
  retry:
    max_attempts: 2
    backoff: 2s
  message_retry:         # ← sub-message-level retry！
    max_attempts: 2
    backoff: 250ms
    max_backoff: 2s
    jitter: full
```

**`message_retry` 的價值**：LLM call 級別重試（250ms backoff），比 Hermes 工具層 retry 更細粒度。

**`priority: high` field**：Orloj 有 task priority concept，Hermes 目前沒有。

**hierarchical topology 的具體含義**：
- 需 fetch `agent-system.yaml` 看 agent 間的父子關係
- 從 `task.yaml` 看 input schema 和參數傳遞模式

## 跨文章 Synthesis

Axe + Orloj 共同指向一個 Hermes 缺口：**Pattern Graduation 機制**。

Axe 的 design：「recurring lessons move from memory → SKILL.md/AGENTS.md via human decision」。Hermes 目前有：
- Memory consolidation（distiller 管線）
- Session search（recall）
- 但沒有「GC → suggestion → human approval → SKILL.md update」的 feedback loop

**Hermes 目前缺少的**：
1. Memory GC 的 pattern analysis（axe 的 LLM-assisted detection）
2. 從 patterns 萃取成 actionable config change 的 pathway
3. Human-in-the-loop 的 approval step（自動更新 SKILL.md 太危險）

這個 feedback loop 如果落實，會讓 Hermes 的 skill system 從「靜態文件」升級成「活的系統」——每次 GC 都讓 skill 迭代優化。

對於 Orloj 的 hierarchical topology（coordinator → workers DAG），關鍵是看 `agent-system.yaml` 的具體實作——確定 agent 之間的 join 語意（`wait_for_all` vs partial）和 error propagation 模式。這對 WS-020 的 multi-agent orchestration 有直接參考價值。

## Hermes 啟發

1. **Hermes Memory Feedback Loop**：參考 Axe 的 pattern graduation 設計，在 memory-consolidator 的下一個版本加入：
   - Phase 1：pattern analysis（LLM 檢測 recurring issues）
   - Phase 2：suggestion output（進 logs/ 或 vault notes）
   - Phase 3：human approval → update skill（手動或 semi-auto）

2. **WS-020 具體化**：Orloj 的 `task.yaml` input schema 和 `message_retry` 是 WS-020 可以直接借鑒的：
   - 定義 input schema 而非 raw JSON
   - sub-message-level retry 而非 tool-level retry

3. **Task Priority**：Hermes 目前所有 cron jobs 優先級相同（或靠 cron schedule 隱含區分）。`priority` field 可以讓高優先級任務搶佔資源。

4. **Axe Memory Format 直接可用**：Axe 的 markdown entry format 極簡，Hermes 的 session 記憶可以直接用同一格式（`## YYYY-MM-DDTHH:MM:SSZ\n**Task:** ...\n**Result:** ...`），讓兩個系統的記憶互通。

## 未追蹤 Leads

- https://raw.githubusercontent.com/jrswab/axe/main/docs/plans/007_gc_implement.md — GC implementation 的具體技術細節
- https://raw.githubusercontent.com/OrlojHQ/orloj/main/examples/blueprints/hierarchical/agent-system.yaml — hierarchical DAG 的具體 agent 定義
- https://raw.githubusercontent.com/OrlojHQ/orloj/main/examples/blueprints/swarm-loop/ — swarm-loop topology 的 task 格式
- Axe 的 `internal/memory/memory.go` — Go 實作中 memory trimming 的具體邏輯

## ✅ 本次探索完成

**時間**: 2026-05-20T07:43 CST
**Token cost**: 低（純 API + raw content，無 LLM 閱讀）
---
title: "Context Distiller — 2026-05-20 00:00 蒸餾"
date: 2026-05-20
tags:
  - context-distiller
  - learnings
  - mailbox
  - hearth
  - comms-reliability
  - overconfidence
---

# Context Distiller — 2026-05-20 00:00

## 複習範圍

2026-05-19 00:00–24:00 的 sessions，248 個 CLI sessions、398 個 Telegram sessions。聚焦於 Hearth 結案、comms-reliability 停滯、mailbox v6 確認、managed-agents 研究。

## 蒸餾產出

### 1. 使用者直接指出 Overconfidence 問題

**事件**：Hestia 在無研究數據支撐的情況下，聲稱「檔案鎖代價低、可以做」，被使用者直接打斷。

**Hestia 自評承認的問題**：
- 「檔案鎖代價低」— 沒有研究 Hermes tool call 封裝方式，也沒評估 lock/unlock race condition
- 「mailbox 用 --phase PLAN 提案」— 沒有實際跑過，是嘴上說說
- Task board 的 phase 內容**無 schema validation**，LLM 回了錯誤格式時追蹤鏈會斷

**誠實版本**：mailbox 提案流程可以研究，但需要先驗證具體步驟。

### 2. comms-reliability 是目前最接近「做一半」的案子

| Phase | 負責方 | 狀態 |
|-------|--------|------|
| Phase 1 | Talos | ✅ 完成 |
| Phase 2 | Hestia | ❌ 完全停滯 |
| Phase 3 | — | ❌ 未開始 |
| Phase 4 | — | ❌ 未開始 |

**停滯原因**：Phase 2（Hestia 側補強）最後更新停在 `2026-05-19 10:18`，之後沒有任何 agent 接手。

### 3. Mailbox v6 確認 Production-Ready

**核心架構**（已驗證）：
```
寫訊息 → /var/hermes-comm/<agent>/inbox/<timestamp>.md
       → mailbox daemon (15s poll)
       → 直接 fork hermes -z（或 hermes -p talos -z）
       → 同一 VM 零網路依賴
```

**與舊 threads 系統差異**：threads 靠 Telegram webhook（不可靠），mailbox 是直接行程 fork。

**Task Board**：`--phase PLAN/REVIEW/EXECUTE/VALIDATE/DONE` 進 GitHub task board，board 更新後自動 git push，30-min systemd safety net timer。

### 4. Hearth System 全面整合完成

**ws-007** ✅ 已結案歸檔：
- Board + tasks 合併為 `projects/` 單一系統
- 入口統一至 `/srv/hearth/PROJECTS.md`
- 結案整理規則寫入 `PROTOCOL.md`

**ws-005** ✅ resolved：4/4 Phase 完成，剩 Layer 1 自動化 action_item（非阻塞）

**ws-006** 🟡 proposal：kernel fallback 條件未滿足，Phase 0/1 未執行

### 5. Managed-Agents 研究評估（使用者驅動）

**已有可直接對應的 Pattern**：

| 研究 Pattern | 我們現況 |
|-------------|---------|
| Inter-agent Messaging | ✅ mailbox v6（15s poll，直接 fork） |
| Task Board phase tracking | ✅ mailbox v6 task board |
| SKILL.md 便攜性 | ✅ Hermes 已在用 YAML frontmatter |
| Subagent delegation | ✅ `delegate_task`（max_spawn_depth=1 限制深度） |
| Shared session search | ✅ FTS5（不如 Mem0 v3 multi-signal retrieval） |

**缺口（High priority）**：
- **檔案鎖** — 尚未研究如何接入 Hermes tool system
- Task board phase 無 schema validation

## 結論

本週期最大教訓：Hestia 被使用者直接指出 overconfidence。這不是第一次，但這次有具體的案例（檔案鎖、mailbox 提案）。comms-reliability 的 Phase 2 停滯需要儘快接手。Mailbox v6 已被驗證為可靠的同 VM 通訊方案，研究報告的 pattern 大部分已在我們的系統中有對應實作。

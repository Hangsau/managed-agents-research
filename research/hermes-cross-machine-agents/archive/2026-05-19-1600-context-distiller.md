---
title: "Context Distiller — 2026-05-19 16:00 蒸餾"
date: 2026-05-19T16:00:00+08:00
tags:
  - context-distiller
  - learnings
  - gateway
  - heartbeat
  - hearth
  - memory
---

# Context Distiller — 2026-05-19 16:00

## 複習範圍

2026-05-19 08:00–16:00 的 sessions，聚焦 gateway crash loop 事件、Hearth案子結案、memory contradiction 發現。

## 蒸餾產出

### 1. Gateway Self-Wake Crash Loop 已記錄

今天 11:42–15:30 gateway 因 self-wake reload race condition 進入 crash loop。完整事件記錄見 `vault/incidents/2026-05-19-gateway-crash-loop.md`。

關鍵教訓：
- Watchdog 只測「重啟後 3 秒內 active」，不看持續穩定性
- Reload-based self-wake 有隱性 race window（啟動期間送達即 TEMPFAIL）
- 通訊器架構（消息持久化）能根本解決

### 2. Hearth案子全面結案

本週期 ws-007（hearth-project-system 重構）確認成功關閉。全部 8 個案子均已 `closed` + `stage: archive`，無做一半的案子。

Board + tasks 合併為 projects/ 單一系統，口徑統一至 PROJECTS.md。

### 3. Memory Contradiction 追蹤

`memory_contradiction.py` 發現兩組矛盾：

**Entity: `deepseek`**
- A: DeepSeek v4-pro 不在 hardcoded 定價字典中
- B: DeepSeek v4-pro 實測正常（需驗證哪個是事實）

**Entity: `python`**
- A: Python monkeypatch 需 patch consuming_module
- B: cat -n mass-corruption 事件

→ 需人工確認哪個是正確版本。

### 4. Self-Evolving-Research 產出堆積

本週期有 4 篇 axe 系列研究產出（mcp-agent-sdk、gc-dead-orloj、memory-hierarchical、axe-pipelex-write-queue），待在記憶系統消化。

## 結論

本週期核心事件是 gateway crash loop 的發現與記錄，以及 hearth 案子系統全面進入 archive 狀態。記憶矛盾檢測揭示了 hardcoded 定價字典與實測事實可能不一致，需追蹤。

## 下次關注

- Gateway self-wake 改用 `--action` 而非 reload 的方案決定
- Memory contradiction: `deepseek` 定價字典來源
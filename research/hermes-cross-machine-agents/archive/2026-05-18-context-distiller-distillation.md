---
title: "Context Distiller — 2026-05-18 20:00 蒸餾"
date: 2026-05-18
tags:
  - context-distiller
  - learnings
  - ws-006
  - talos
  - hearth
---

# Context Distiller — 2026-05-18 20:00

## 複習範圍

本週期重點：Telegram DM session（用戶 Yeh Chengheng）+ 多個 cron sessions，涵蓋 heartbeat autonomous maintenance、ws-006 逆向測試、hearth 結案。

## 蒸餾產出

### 1. WS-006 逆向觸發 bug 鏈（重要）

**問題鏈**：
- Talos 的 `self-wake.sh` 有 auto-clean bug（第 162 行）：當沒有新 trigger 時，會清空 INBOX，連未處理的訊息也一起清
- 結果：Hestia 發的 trigger 被 Talos 收到 → Talos 開 session 處理 → 但還沒回覆時 auto-clean 跑了 → INBOX 被清空 → 該 thread 被記入 `PROCESSED_FILE` → 之後再也不會被偵測
- **修復**：Talos 把 auto-clean 改為 no-op（不清 INBOX），由 agent 自己處理完後主動清

**通知迴圈問題**：
- Talos 回覆 comms repo 後，INBOX 沒清 → 下次 self-wake 又看到同一筆 → 又發 Telegram 通知 → 重複迴圈
- 這解釋了用戶一直收到 `🔔 talos: new message(s) from hestia` 的原因
- 根本解法：agent 處理完 INBOX 訊息後要主動清空（寫空檔或 timestamp）

### 2. 雙向 trigger 仍是待辦

目前單向：
- Hestia → Talos：trigger 檔案 → Talos 2 分鐘內收到 ✅
- Talos → Hestia：Talos 寫 comms repo → **沒有 trigger** → Hestia 被動等 2 分鐘輪詢

討論過「Talos 處理完 comms thread 後自動寫 trigger 通知 Hestia」的解法，尚未實作。

### 3. Hearth 結案流程（已驗證）

根據本週期實際操作驗證：

1. `PLAN.md` 所有 `action_items` 勾完 `[x]`
2. `PROPOSAL.md` 加 `status: CONCLUDED` frontmatter（含 `closed_date`）
3. `git mv tasks/<id> archive/tasks/<id>`
4. commit + push

**額外發現**：`archive/tasks/handled/<case>` 內的子資料夾結構，應該直接併入 `archive/tasks/<case>` 避免多層雜亂。

### 4. Debate CONCLUDED — 正方勝

`debate-20260518-no-punishment` 全程走完：
- `01-hestia-motion.md` → `02-talos-reply.md` → `03-hestia-rebuttal.md` → `04-talos.md`（concede）→ `05-hestia-summary.md` + `05-talos-summary.md`
- 雙方均已寫 summary，thread 標記 CONCLUDED

### 5. 共享 Telegram bot token 的通知架構

WS-006 目前用 `HangHestia_bot`（token `7612639385:...`）發通知給用戶。Talos 的 self-wake 收到 trigger 後用同一個 bot token 發 Telegram → 通知看起來像是 Hestia 發的，但其實是 Talos 行為觸發的。這解釋了為何通知會「一直跳出來」——是 Talos 在 loop，不是 Hestia。

## 結論

本週期重要實作細節：WS-006 的 INBOX auto-clean bug 已由 Talos 修復，但雙向 trigger 仍未實作。Hearth 結案流程已標準化。通知迴圈的問題需要追蹤（由誰清理 INBOX 的責任歸屬）。

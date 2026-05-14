# 提案：Hermes Token/Cost Visibility（Level 1 觀測層）

**日期**: 2026-05-14 | **來源**: [[2026-05-14-agent-cost-curve]] | **類型**: CHANGE
**摘要**: 在 heartbeat 或 session ending hook 加入 token/cost tracking，不改行為，純觀測。讓 Hermes 知道自己花了多少錢。
**預估成本**: 2-4h 實作，低風險（純 additive）
**前提**: 需先確認 provider API response 是否已包含 token usage（DeepSeek/Anthropic 都有 `usage` field）

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | ✅ DONE |
| **階段** | 實作 → 測試 → 部署 |
| **目前階段** | 完成 |
| **最後行動** | 05-14: cost_aggregator.py + heartbeat callback 上線 |
| **下一步** | — |
| **阻擋** | 無 |
| **關聯** | WS-003 |

## 背景

LLM agent 成本是 O(n²)（見 [[2026-05-14-agent-cost-curve]]）。Hermes 架構隱含地做了很多對的事（agent cache, auto-continue, subagent delegation），但**完全不知道自己的 conversation 成本曲線長怎樣**。沒有 data，就無從優化。

## 範圍

**只做 Level 1：不改行為，純觀測。**

具體：
- Session 結束時記錄 `total_input_tokens` / `total_output_tokens` / `estimated_cost`
- 加進 `heartbeat_state.json`（或獨立的 `session_cost.json`）
- `/cost` slash command：顯示當前 session 的 token/cost breakdown
- Heartbeat v2 tick 時附帶最近 24h 的 cost summary

## 不做的事（Level 2/3）

- Cost-aware conversation break（等有 data 再說）
- Dollar-based iteration budget（等有 data 再說）
- Provider multiplier logic

## 實作路徑

1. 確認 provider response 的 `usage` field（DeepSeek API 有 `usage.total_tokens`）
2. 在 session context 或 Hermes Gateway 側累積 token count
3. Session end hook 寫入 tracking file
4. 加 `/cost` slash command
5. Heartbeat v2 拉 cost summary

## 邊際價值

- **Immediate**: 知道自己花多少錢（現在完全不知道）
- **Long-term**: 收集 data → 驗證 quadratic curve 對 Hermes 是否適用 → 後續優化有依據

## 狀態更新 (2026-05-14)

**STATUS: DONE** — 已實作三個 component：

- ✅ `get_cost_summary(since_hours=24|None)` — SessionDB 方法，SQL 聚合 tokens/cost
- ✅ `cost_aggregator.py` — CLI 腳本，`--markdown` / `--json` / `--all` 輸出
- ✅ Heartbeat `cost_24h` injection — 每 30min 自動注入 `heartbeat_state.json`
- ✅ 4 tests (incl. all-time cumulative) — 全 pass
- ❌ `/cost` slash command — 未實作（可用 aggregator 腳本替代）
- 🔄 需重啟 gateway 生效

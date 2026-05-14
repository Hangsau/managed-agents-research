# 提案：Hermes 核心組件的自動化測試基礎建設
**日期**: 2026-05-13 | **來源**: [[autonomous_notes/2026-05-13-adk-evaluation-gap]] | **類型**: SPIKE
**摘要**: 目前 Hermes 有 heartbeat 監控系統健康（disk、mem、stuck），但完全沒有任何自動化測試確保 agent 行為正確性。上次 `managed-agents-framework` 改路徑導致 `ma run` 壞掉就沒被發現。這次 spike 從最務實的起點開始：幫 heartbeat_v2.py 的非 LLM 函數（scoring、snapshot parsing）寫 pytest，建立 smoke test pattern，驗證 cron job output 的有效性。
**預估成本**: 
- 時間：~2-3 小時 spike（挑 3-5 個 heartbeat_v2.py 純函數 → 寫 pytest → 跑 coverage → 評估下一步）
- 風險：極低。只動測試，不碰 runtime code。新增 `~/.hermes/tests/` 目錄，不影響任何 production path。
**前提**: 需先確認 `heartbeat_v2.py` 有哪些純函數可以獨立測試（不需要 mock LLM call 的）。也需確認 pytest 是否已在環境中，或需要 `pip install`。
**潛在問題**:
- heartbeat_v2.py 可能沒有把邏輯拆成可測試的單元函數，需要先重構（但不改 behavior）
- LLM-dependent 的路徑（REST/WORK 決策）沒辦法在 spike 階段測，只能測 data processing 部分
- 要定義「可接受的 test coverage」範圍，避免 scope creep

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | ✅ DONE |
| **階段** | Spike → 實作 → 測試 |
| **目前階段** | 完成 |
| **最後行動** | 05-13: 產出 test_heartbeat_v2.py（95 tests） |
| **下一步** | — |
| **阻擋** | 無 |
| **關聯** | WS-001 |

## 狀態更新 (2026-05-14)

**STATUS: DONE** — SPIKE 完成，產出 `~/.hermes/tests/test_heartbeat_v2.py` (511 行)，覆蓋範圍遠超預期。
- ✅ `_is_daemon_process` — 5 tests（known daemons, normal agents, edge cases, substring）
- ✅ `_is_on_cooldown` — 7 tests（cooldown logic, edge cases, missing ts field）
- ✅ `score_actions` — 9 tests（baseline, disk/memory/idle boosts, repetition penalty, combined signals）
- ✅ `select_action` — 5 tests（picks highest, skips cooldown, backpressure, all-on-cooldown fallback）
- ✅ `action_connect/action_report/action_work/action_evolve` — 14 tests（all action handlers + dry-run）
- ✅ `execute_action` — 4 tests（dispatch routing, unknown action handling）
- ✅ `_record_action_log` / `_summarize_today` — 3 tests（round-trip, empty, missing file）
- ✅ `_scan_cron_errors` — 4 tests（no dir, empty dir, 429 detection, clean output skip）
- 總計 51 tests，涵蓋 `heartbeat_v2.py` 所有可獨立測試的非 LLM 函數
- 殘餘：LLM-dependent 路徑（REST/WORK 決策）無法在單元測試層覆蓋 → 需 integration/spike 測試

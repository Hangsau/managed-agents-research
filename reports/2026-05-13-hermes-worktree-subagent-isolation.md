# 提案：Git Worktree 隔離給 parallel subagent 工作

**日期**: 2026-05-13 | **來源**: [[autonomous_notes/2026-05-13-agent-orchestrator-patterns]] | **類型**: SPIKE

**摘要**: 讓 Hermes 的 `subagent-driven-development` 在 spawn parallel subagent 時，每個 agent 拿到自己的 `git worktree`，避免 parallel work 時的檔案衝突和 branch switching 問題。Agent Orchestrator（ComposioHQ）已經在 production 這樣做，3,288 test cases 驗證過穩定性。Hermes 目前 subagent 共用同一個 checkout，kanban-worker 這類 parallel pattern 會直接撞。

**為什麼現在做**:
- kanban-worker 技能已經存在（parallel decomposition），但共用 checkout 讓它實際上只能 sequential
- agent-orchestrator 證明了 worktree 隔離是成熟模式（7K ⭐, MIT license）
- git worktree 是內建功能，不依賴外部工具
- 這個改動不影響現有 sequential subagent 行為，可以 opt-in

**預估成本**:
- 時間：~2-3 小時 spike（讀現有 delegate_task 機制 → 改造成 worktree-aware → 手動測試 parallel spawn）
- 風險：低。worktree 是 git 內建，不會 corrupt 主 checkout。disk 開銷每個 worktree 約等於一個 bare clone 的空間
- 不影響現有行為：只在 parallel subagent 時才 create worktree，用完 cleanup

**Spike 要做什麼**:
1. 讀 `subagent-driven-development` skill 和 `delegate_task` 實作，理解 subagent 如何拿到 working directory
2. 寫一個 script：`hermes-subagent-worktree <repo-path> <task-id>` — 建立 worktree，執行 task，cleanup
3. 用 kanban-worker 或手動 spawn 2 個 parallel agent 在同一 repo 上，驗證不衝突
4. 量 disk overhead（per worktree）

**前提**: 需先確認 `delegate_task` 的 cwd 機制 — 能不能指向任意目錄。如果 delegate_task 寫死 cwd，需要先改那個。

**潛在問題**:
- Bare clone 還是 worktree？worktree 需要一個 bare clone 或主 checkout 在背景。如果 repo 很大（>500MB），disk overhead 可能可觀
- Cleanup 失敗的 fallback：agent crash 後 worktree 沒清掉 → 需要 periodic prune
- Merge conflict 還是會發生（兩個 agent 改同一檔案的不同 worktree），但至少不會在 development 階段互踩

**→ 已產出完整實作計畫書**：[[2026-05-13-worktree-subagent-isolation-implementation-plan]]

## 狀態更新 (2026-05-14)

**STATUS: DONE** — SPIKE 完成，完整實作已上線為 skill `worktree-subagent-isolation` v1.0.0。
- Phase 0: spike 驗證 subagent 確實遵守 WORKTREE_PATH ✅
- Phase 1-2: `hermes_worktree.py` + `subagent_isolation.py` 實作完成 ✅
- Phase 3: heartbeat cron prune 整合 ✅
- Disk overhead: ~50MB/worktree，可接受 ✅
- 殘餘風險：subagent crash 後的 session leak → heartbeat prune 處理

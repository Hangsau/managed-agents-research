# Git Worktree 子代理隔離 — 實作計畫書

**日期**：2026-05-13  
**類型**：實作計畫（基於 SPIKE 提案深入研究後產出）  
**參考**：Agent Orchestrator `workspace-worktree` plugin（674 行 TypeScript, MIT）

---

## 一、問題

Hermes `delegate_task` 可以 parallel spawn 3 個 subagent，但全部共用同一個 working directory。
結果是 `kanban-worker`（parallel decomposition 技能）名義上 parallel，實際上只能 sequential — 兩個 agent 改同一檔案會互踩。

---

## 二、解法：Git Worktree 隔離

`git worktree` 是 git 內建功能（2.5+），讓一個 repo 同時有多個 working directory：

```
主 checkout: /root/projects/firn
  ├── ~/.hermes/worktrees/session-A/  ← subagent-A 有自己的檔案系統
  └── ~/.hermes/worktrees/session-B/  ← subagent-B 有自己的檔案系統
```

Agent Orchestrator（ComposioHQ, 7K⭐）已經在 production 這樣做。

---

## 三、為什麼不直接拿 AO 的來用

AO 是 TypeScript，674 行。但：
- 80% 程式碼處理 Windows 特有問題（file-handle drain, junction symlink）
- Plugin interface 跟 Hermes 對不齊
- Linux only 環境不需要那些複雜度

**結論**：自己寫 Python 版本，核心 ~40 行，加 error recovery ~90 行。

---

## 四、實作架構

```
兩個新檔案：

1. hermes_worktree.py（獨立模組）
   - create_worktree(repo, session_id, branch, base_ref) → WorktreeInfo
   - destroy_worktree(path)
   - prune_stale_worktrees(repo) → 清理數量

2. subagent_isolation.py（整合層）
   - 在 delegate_task 前: 為每個 parallel task 建立 worktree
   - 在 delegate_task 後: 清理 worktree
   - 透過 context 參數把 worktree 路徑傳給 subagent
```

## 五、關鍵設計決策

1. **不改 delegate_task 核心**：只在外層包裝
2. **透過 context 傳遞 worktree 路徑**：subagent 收到 `WORKTREE_PATH=...` 後，自行用 `terminal(workdir=...)` 
3. **不做 auto-merge**：merge 由 orchestrator/parent 手動處理，worktree 只解決檔案系統隔離
4. **Stale cleanup 用 cron**：每小時跑 `prune_stale_worktrees()`，防止 crash 後殘留

---

## 六、分階段實作

| Phase | 內容 | 時間 |
|-------|------|------|
| 0: Spike | 手動驗證 git worktree 在環境中可用、量 disk overhead | 30 分鐘 |
| 1: 獨立模組 | `hermes_worktree.py` 三 API + 單元測試 | 1 小時 |
| 2: 整合層 | `subagent_isolation.py` wrapper + delegate_task 串接 | 30 分鐘 |
| 3: Cron cleanup | 每小時 prune stale worktrees | 20 分鐘 |
| 4: 整合測試 | 用 kanban-worker 驗證 parallel 不衝突 | 30 分鐘 |

**總計約 3 小時**。

---

## 七、風險與緩解

| 風險 | 緩解 |
|------|------|
| subagent 忽略 context 中的 worktree 提示 | Plan B: 改用 cronjob workdir（cronjob 已原生支援）或對 Hermes 提 PR 加 workdir |
| Disk overhead | 實測 firn repo worktree ~50MB，3 concurrent < 200MB |
| Stale worktree 累積 | Phase 3 cron prune |
| Branch 命名衝突 | UUID session_id，已驗證安全 |

---

## 八、可行性結論

✅ **技術可行** — git worktree 十年穩定，邏輯極簡  
⚠️ **整合需驗證** — 取決於 delegate_task subagent 是否遵守 workdir 提示  
✅ **價值明確** — 解鎖 kanban-worker 的 parallel 能力  
💰 **成本低廉** — ~3 小時，零外部相依，零 API cost

**建議**：立即開始 Phase 0 Spike，30 分鐘內確認關鍵未知數。

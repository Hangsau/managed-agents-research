# 提案：Hermes Workspace Manager — 跨 Session Context 連續性 + 文件自動同步

**日期**: 2026-05-14 | **優先序**: P0 | **狀態**: 設計階段

## 一句話

> 讓 Hermes 永遠知道「現在在忙什麼」，而且所有計畫書會自己跟上進度。

---

## 一、雙重問題診斷

### 問題 1：Session 斷片（最痛）

新 session 啟動時，agent 完全不知道上一回合在做什麼。

| 症狀 | 實例 |
|------|------|
| 被問「繼續剛剛的事」→ 狂搜 session_search | 本回合就是：user 說「繼續剛剛還沒做的」→ 搜了 N 次才重建 context |
| 無法跨 session 追蹤進度 | 4 個提案（core-testing/worktree/cost-visibility/consolidation）做完 2 個，但沒有單一入口知道 |
| 人類需重複說明 | 每次新 session 都要解釋一次「我們在做 X」 |

**根因**：Hermes 有 `session_search`（被動回溯）、有 `memory`（離散事實）、有 `auto_continue`（1h window），但**沒有 session start injection**——新 session 啟動時不注入「當前在做什麼」。

### 問題 2：文件漂移（慢性病）

所有計畫文件凍結在撰寫當下，實作進化後沒人更新。

| 文件 | 聲稱 | 實際 | 落差 |
|------|------|------|------|
| `hermes-heartbeat-project-proposal.md` | heartbeat_v2.py 912 行、53 tests | 已模組化成 7 檔案 package、95 tests | 架構已變、測試數幾乎翻倍 |
| `2026-05-13-hermes-core-testing-infra.md` | 51 tests | 95 tests（從 memory 確認） | 測試數已更新但提案本身未標記 |
| `hermes-2026-05-13-hermes-worktree-subagent-isolation.md` | DONE ✅ | 無明顯落差 | 狀態更新及時，是唯一的好案例 |

**根因**：提案文件是**一次性產出**，沒有機制在實作演進時自動更新。agent 做完事情後不會回頭改計畫書。

### 兩者的關聯

```
Session 斷片 ←── 共享根因 ──→ 文件漂移
     │                              │
     └─ 沒有「現在在做什麼」的單一入口 ─┘
```

如果有一個永遠最新的 workspace index，新 session 啟動時注入它，兩個問題一起解。

---

## 二、設計理念

### 不是再做一套 issue tracker

不需要 Linear/Jira/Notion 的複雜度。我們要的是：

> **一個檔案結構 + 一個自動更新慣例 + 一個 heartbeat sensor**

### 三層架構

```
Layer 1: WORKSPACE INDEX          ~/.hermes/workspace/INDEX.md
         ├─ 所有活躍專案的清單
         ├─ 每個的狀態（PLANNING / IN PROGRESS / DONE / STALE）
         ├─ 指向詳細計畫書的路徑
         └─ 最後更新時間（heartbeat 可偵測漂流）

Layer 2: PLAN DOCUMENTS           每個專案一份（proposals/ 或 vault/）
         ├─ 固定的 ## STATUS 區塊（純結構化欄位）
         ├─ agent 做完動作後自動 patch 這個區塊
         └─ 內容：status emoji、last_action、date、phase、blocker

Layer 3: ACTIVE CONTEXT           新 session 啟動時注入
         ├─ 從 INDEX.md 萃取 top N 個 IN_PROGRESS 專案
         ├─ 每個摘要：在做什麼、下一步、卡在哪
         └─ 放 context 尾端（Handbook Defense 2：最高 attention 位置）
```

### 關鍵設計決策

| 決策 | 選項 | 理由 |
|------|------|------|
| 存哪裡 | `~/.hermes/workspace/` | 與現有 `proposals/` `autonomous_notes/` 同層，不新增頂層目錄 |
| 格式 | Markdown（結構化區塊） | 相容現有技能生態，人類可讀，LLM 友善 |
| 更新機制 | agent 慣例（非強制） | 強制 hook 會增加複雜度且可能失敗；先做慣例，heartbeat 偵測漂移做安全網 |
| 自動 vs 手動 | agent 自主更新 | 不靠人類維護——人類會忘記 |
| 索引檔案 | 單一 INDEX.md | YAML frontmatter 的結構化欄位可以 grep，不需要 CSV/JSON 的解析開銷 |

---

## 三、INDEX.md 格式設計

```markdown
---
updated: 2026-05-14T09:00:00+08:00
total_active: 3
total_done: 2
---

# Hermes Workspace Index

> 最後更新：2026-05-14 09:00 | 活躍專案：3 | 已完成：2

## IN PROGRESS

| ID | 專案 | 計畫書 | 狀態 | 開始 | 最後動作 |
|----|------|--------|------|------|----------|
| WS-003 | Cost Visibility | [proposal](~/managed-agents-research/reports/2026-05-14-hermes-cost-visibility.md) | 🔴 零進度 | 05-13 | — |
| WS-004 | Consolidation Step | [proposal](~/managed-agents-research/reports/2026-05-14-hermes-consolidation-step.md) | 🟡 SPIKE 已設計 | 05-13 | 05-13: 設計完成，未寫 code |
| WS-005 | Workspace Manager | [proposal](~/managed-agents-research/reports/2026-05-14-hermes-workspace-context-continuity.md) | 🟢 設計中 | 05-14 | 05-14: 撰寫本計畫書 |

## DONE

| ID | 專案 | 計畫書 | 完成日期 |
|----|------|--------|----------|
| WS-001 | Core Testing Infra | [proposal](~/managed-agents-research/reports/2026-05-13-hermes-core-testing-infra.md) | 05-13 |
| WS-002 | Worktree Subagent Isolation | [proposal](~/managed-agents-research/reports/2026-05-13-hermes-worktree-subagent-isolation.md) | 05-14 |

## DEPRECATED / ARCHIVED

（暫無）
```

### YAML frontmatter 的目的

不是為了 parser——是為了 **grep 友善** + **heartbeat sensor 可讀**：

```bash
# heartbeat 可以這樣偵測漂移
yq '.updated' ~/.hermes/workspace/INDEX.md  # 最後更新時間
grep "IN PROGRESS" -A 20 ~/.hermes/workspace/INDEX.md  # 活躍專案
```

---

## 四、PLAN DOCUMENT 的 STATUS 區塊格式

每個計畫書的 **檔頭（緊接 YAML frontmatter 之後）** 必須有一個標準化的狀態區塊：

```markdown
## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🟡 SPIKE 已設計 |
| **階段** | 設計 → 實作 → 測試 → 部署 |
| **目前階段** | 設計 |
| **最後行動** | 05-14: 撰寫 INDEX.md 格式設計 |
| **下一步** | 實作 workspace_update.sh |
| **阻擋** | 無 |
| **關聯** | WS-005 |
```

### 更新慣例

agent 在以下時機**應該**更新 STATUS 區塊（用 `patch` 工具，不重寫整個檔案）：

1. **完成一個 subtask** → 更新「最後行動」「下一步」
2. **遇到阻擋** → 更新「阻擋」欄位
3. **切換階段** → 更新「目前階段」「狀態 emoji」
4. **完成專案** → 狀態改 ✅，通知人類

不需要每次 terminal call 都更新——只更新「有意義的進展」。

---

## 五、Session Start Injection（解 session 斷片）

### 注入內容

新 session 啟動時，系統自動從 INDEX.md + STATUS 區塊組裝 context block，注入到 system prompt 尾部：

```markdown
## CURRENT WORKSPACE STATE (auto-injected)

You have 3 active projects:

1. **WS-003 Cost Visibility** [🔴 零進度]
   - Plan: ~/.hermes/proposals/2026-05-14-hermes-cost-visibility.md
   - Blocker: 無
   - Next: 需要開始 — 無前次行動紀錄

2. **WS-004 Consolidation Step** [🟡 SPIKE 已設計]
   - Plan: ~/.hermes/proposals/2026-05-14-hermes-consolidation-step.md
   - Last: 05-13 — 設計完成，未寫 code
   - Next: 實作 ConsolidateAgent cron job

3. **WS-005 Workspace Manager** [🟢 設計中]
   - Plan: ~/.hermes/proposals/2026-05-14-hermes-workspace-context-continuity.md
   - Last: 05-14 — 撰寫計畫書
   - Next: 討論實作順序

Recently completed: WS-001 (Core Testing), WS-002 (Worktree Isolation)
```

### Token 預算

控制在 **300-500 tokens**（5-8 個活躍專案 + summary）。成本 ≈ $0.0004/session start（用 deepseek-v4-pro 價格），幾乎可忽略。

### 注入位置

**System prompt 尾部**（非頭部）。理由：

- Handbook Defense 2 說「重新注入指令」是最有效的 context rot 防線
- 尾部是 attention 最高的位置（recency bias）
- Claude Code 的 CLAUDE.md 也放尾部

---

## 六、Heartbeat Integration（防漂移安全網）

文件漂移不會 100% 被 agent 慣例防止——需要一個 safety net。

### 新增 heartbeat sensor：`check_workspace_sync`

```python
def check_workspace_sync() -> list[SyncIssue]:
    """
    掃描 ~/.hermes/workspace/INDEX.md 中的所有活躍專案，
    比對計畫書的 STATUS.updated 欄位 vs INDEX.updated。
    超過 24h 沒更新 → flag STALE。
    """
```

運作方式：

1. 每次 cognitive cycle（30 分鐘）執行
2. 發現 STALE 文件 → 寫入 heartbeat log
3. 下次 REPORT 時附上：「2 個計畫書已超過 24h 沒更新」

### 這個 sensor 不做的事

- ❌ 不自動更新文件（那是 agent 的工作）
- ❌ 不強制 agent 更新
- ✅ 只偵測 + 報告漂移

人類看到報告後可以說「去更新一下 WS-003」——而不是自己手動改。

---

## 七、實作計畫

### Phase 0：建立基礎（~1 小時）

| 步驟 | 內容 | 產出 |
|------|------|------|
| 0.1 | 建立 `~/.hermes/workspace/` 目錄 | 目錄 |
| 0.2 | 掃描現有 `proposals/` → 生成初始 INDEX.md | INDEX.md |
| 0.3 | 為現有計畫書補上 ## STATUS 區塊 | 更新 5 份文件 |
| 0.4 | 寫 `workspace_update.sh`（CLI 工具：`workspace update WS-003 --status "IN PROGRESS" --action "started implementation"`） | script |
| 0.5 | 寫 `workspace_inject.py`（讀 INDEX → 生成 context block） | script |

### Phase 1：Session Injection（~1 小時）

| 步驟 | 內容 | 產出 |
|------|------|------|
| 1.1 | 找到 Hermes gateway 的 session init hook 點 | 確認注入機制 |
| 1.2 | 修改 session init → 呼叫 `workspace_inject.py` → 注入到 system prompt | 功能上線 |
| 1.3 | 手動測試：開新 session → 確認有 workspace context | 驗證 |

### Phase 2：文件自動更新慣例（與 Phase 1 並行）

| 步驟 | 內容 | 產出 |
|------|------|------|
| 2.1 | 寫 Agent Convention Guide（什麼時候該更新 STATUS） | 文件 |
| 2.2 | 在 agent personality 加入慣例提示 | 更新 personality skill |
| 2.3 | 實際跑幾次 task → 觀察 agent 是否自主更新 | 驗證 |

### Phase 3：Heartbeat Drift Detection（~30 分鐘）

| 步驟 | 內容 | 產出 |
|------|------|------|
| 3.1 | 在 heartbeat sensor 加入 `check_workspace_sync()` | 新 sensor |
| 3.2 | 在 REPORT action 加入漂移警告 | 報告增強 |
| 3.3 | 手動製造一個 stale 文件 → 確認偵測 | 驗證 |

### Phase 4：Skill 包裝（~30 分鐘）

| 步驟 | 內容 | 產出 |
|------|------|------|
| 4.1 | 將整個系統包成 `workspace-manager` skill | skill |
| 4.2 | Skill 內容：INDEX.md 格式規範、STATUS 區塊規範、更新腳本、注入腳本 | — |

---

## 八、與現有系統的關係

| 現有系統 | 關係 | 說明 |
|----------|------|------|
| `proposals/` | 被索引 | INDEX.md 指向 proposals，不重複內容 |
| `autonomous_notes/` | 被索引 | Consolidation note 可被納入 |
| `memory` | 互補 | memory 存持久事實（用戶偏好等），workspace 存專案進度 |
| `session_search` | 退居備援 | 有 workspace 後優先從 INDEX 找；搜不到才 fallback 到 session_search |
| `heartbeat` | 防漂移 | heartbeat sensor 偵測文件漂移 |
| `consolidation-step` | 受益者 | consolidation cron 可讀 workspace index 找該消化的筆記 |

---

## 九、成本分析

| 項目 | Token 成本 | 頻率 |
|------|-----------|------|
| Session start injection | ~300-500 tokens | 每次新 session |
| STATUS 區塊更新（patch） | ~0 tokens（patch 工具不經 LLM） | 每 task ~0-5 次 |
| Heartbeat drift scan | 0 tokens（純 fs 操作） | 每 30 分鐘 |
| INDEX.md 更新 | ~0 tokens（patch） | agent 做完 milestone 時 |
| **總計** | ~$0.0004/session + $0 持續成本 | — |

---

## 十、風險與疑慮

| 風險 | 緩解 |
|------|------|
| Agent 忘記更新 STATUS | Heartbeat drift detection 做 safety net；人類看到報告提醒 |
| INDEX.md 過大（專案累積） | DONE 專案移到 ARCHIVED 區塊，只注入 IN PROGRESS |
| 多 agent 並發寫 INDEX.md | patch 工具是 atomic 的；heartbeat 只讀不寫 |
| 提案被刪但 INDEX 還有連結 | heartbeat sensor 可偵測 broken link |
| Session injection 造成 token 浪費 | 控制 500 token 上限；只注入活躍專案 |

---

## 十一、成功指標

- [ ] 新 session 啟動後，agent 不需要搜尋就知道有哪些 IN PROGRESS 專案
- [ ] 人類說「繼續」時，agent 直接從 workspace context 找到對的專案
- [ ] 心跳提案的 STATUS 區塊反映實際 95 tests + 模組化架構
- [ ] Heartbeat REPORT 開始顯示文件漂移警告（如果有的話）
- [ ] 連續 3 個專案完成後，human 不需要手動更新任何文件

---

## 十二、不做的事

- ❌ 不做 web dashboard（過度設計）
- ❌ 不做資料庫（Markdown 夠用，SQLite 是殺雞用牛刀）
- ❌ 不做自動 commit（那是 git 的事，不是 workspace manager 的事）
- ❌ 不做 dependency tracking（A blocking B 的關係——等遇到再說）
- ❌ 不做 template engine（每個計畫書格式自由，只有 STATUS 區塊標準化）

---

## 十三、為什麼現在做

1. **Session 斷片是 daily pain**——每次開新 session 都在重複搜尋
2. **文件漂移只會更嚴重**——專案越多，手動維護越不可行
3. **Phase 0 只要 1 小時**——這不是大工程，是補一個洞
4. **做完後 consolidation-step 會更容易**——consolidation 需要知道該消化哪些文件

---

## 附錄 A：現有專案清查（2026-05-14）

| ID | 專案 | 計畫書 | 實際狀態 |
|----|------|--------|----------|
| WS-001 | Core Testing Infra | `reports/2026-05-13-hermes-core-testing-infra.md` | ✅ DONE（95 tests，但提案寫 51） |
| WS-002 | Worktree Subagent Isolation | `reports/2026-05-13-hermes-worktree-subagent-isolation.md` | ✅ DONE |
| WS-003 | Cost Visibility | `reports/2026-05-14-hermes-cost-visibility.md` | 🔴 零進度 |
| WS-004 | Consolidation Step | `reports/2026-05-14-hermes-consolidation-step.md` | 🟡 SPIKE 設計完成，未寫 code |
| WS-005 | Workspace Manager | `reports/2026-05-14-hermes-workspace-context-continuity.md` | 🟢 本提案 |
| — | Heartbeat v2 | `reports/2026-05-14-hermes-heartbeat-project-proposal.md` | 🟢 已上線但文件凍在 v1.0 |

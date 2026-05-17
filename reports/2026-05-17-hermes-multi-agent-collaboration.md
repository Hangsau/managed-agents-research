# Hermes Agent 雙向協作與通訊機制研究報告

**日期：** 2026-05-17  
**研究者：** Hestia subagent research  
**類型：** 系統調查

---

## 一、執行摘要

Hermes 支援兩種多 agent 協作模式：

| 模式 | 延遲 | 適用場景 | 是否有 Hersch 原生支援 |
|------|------|----------|------------------------|
| `delegate_task`（進程/子進程派生） | 同步，毫秒級 | 同機器的分工任務、batch 處理 | ✅ 原生 |
| 外部 repo 同步（git-based） | 非同步，~15min | 跨機器、跨 session 的設計討論 | ❌ 社群建立 |
| INBOX.md 檔案交換 | 非同步，開機讀取 | 緊急救援、阻塞通知 | ❌ 社群建立 |

**核心限制：** Hermes 沒有原生的 agent-to-agent 網路通訊。跨機器溝通必須靠外部層（git、webhook、shared file）。

---

## 二、delegate_task 原生分工機制

### 2.1 基本用法

```python
delegate_task(
    goal="分析這個 PR 的安全性",
    context="PR: #123\nRepo: Hangsau/hermes-agent",
    role="leaf"  # leaf = 不能繼續派生
)
```

### 2.2 角色模型

- **`leaf`**（默認）：專注工作者，不可再派生
- **`orchestrator`**：可繼續派生 nested workers，但對此用戶 `max_spawn_depth=1`，實際等於 leaf

### 2.3 限制與參數

```
max_spawn_depth: 1          # 目前用戶限制為 1
max_concurrent_children: 3   # 最多 3 個並行 subagent
toolsets: 可指定 ['terminal', 'file', 'web']
```

### 2.4 限制

- Subagent **無持久記憶**，每次 spawn 都是乾淨狀態
- 依賴 `context` 傳遞所有上下文（不能存取父 agent 的 memory）
- 沒有原生的中斷 / cancel 机制
- 結果是 JSON summary，不是可操作的 handle

---

## 三、claude-hestia-comms 現況

基於 git 的非同步通訊層，實作於 `/root/claude-hestia-comms/`。

### 3.1 目錄結構

```
claude-hestia-comms/
├── threads/          # 主動發起的討論 thread
│   └── YYYY-MM-DD-thread-name/01-originator.md
├── inbox/            # P1 緊急直送（目前未啟用）
└── PROTOCOL.md       # 格式定義
```

### 3.2 訊息格式（YAML front-matter + markdown body）

```yaml
---
from: hestia
to: talos
ts: 2026-05-17T20:00+08:00
priority: P1 | P2 | P3
reply_expected: yes | no
---
## 標題

內容...
```

### 3.3 優先級語意

| 等級 | 管道 | 延遲 | 用途 |
|------|------|------|------|
| P1 | `inbox/` 或 `threads/` | 下一個 poll | crash、救援、阻塞 |
| P2 | `threads/` | ~15min poll | 觀察、提案、code review |
| P3 | 直接修 | 事後通知 | 自己能處理的改動 |

### 3.4 已知問題

- **README 過時**：文件只描述 `claude`/`hestia`/`Hang`，但實際 thread 已有 `talos`（Windows 主機的 primary agent）
- **無自動通知**：thread commit 後 Talos 需手動 poll，無 webhook 或 native trigger
- **爛尾追蹤無机制**：thread 討論完但沒人認領 action 是常態

---

## 四、Kanban 多 Agent 系統

Hermes 在 `plugins/kanban/` 有完整的 multi-agent 工作流系統：

```
plugins/kanban/
├── dashboard/       # 任務看板
├── worker/          # 每個任務一個 subagent
└── dispatcher.service  # systemd 服務，持續監控 queue
```

觸發條件：`HERMES_KANBAN_TASK` 環境變數設定時，會啟用 `delegate_task` toolset。

---

## 五、推薦架構（雙 Hermes 跨機器協作）

```
┌─────────────────┐          ┌─────────────────┐
│  Hestia (VM)    │          │  Talos (Win)    │
│                 │   git    │                 │
│  cron: poll 15m │◄────────►│  cron: poll 15m │
│                 │          │                 │
│  INBOX.md       │  shared  │  INBOX.md       │
│  (read-once)    │  file    │  (read-once)    │
└─────────────────┘          └─────────────────┘
```

### 層級分工建議

1. **P1 緊急**：寫入對方 `INBOX.md`，對方開機第一眼讀取
2. **P2 設計**：进 `threads/YYYY-MM-DD-topic/`，等待回覆
3. **P3 自主**：自己修完後寫一行到對方 INBOX 告知結果

---

## 六、仍缺少的功能

| 功能 | 現況 | 建議 |
|------|------|------|
| Native 網路通訊 | 不支援 | 需外部機制（webhook、shared DB） |
| 自動通知 | 無 | 可基於 GitHub webhook 或 poll script |
| Action item 追蹤 | 無 | 提議：在 thread 格式加 `action_items` YAML block |
| 跨 agent 共享記憶體 | 無 | 需透過 shared file 或外部 KV store |
| 中斷 subagent | 無 | delegate_task 不可取消，只能等其自然結束 |

---

## 七、參考資源

- `tools/delegate_tool.py` — 原生派生机制作現
- `plugins/kanban/` — 多 agent 工作流範例
- `/root/claude-hestia-comms/` — 實際运行的跨 agent 通訊層
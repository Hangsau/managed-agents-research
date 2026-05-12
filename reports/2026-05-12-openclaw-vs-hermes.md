# OpenClaw vs Hermes Agent 深度對比與整合方案

> 研究日期：2026-05-12
> 基於 OpenClaw main (⭐371K) 與 Hermes Agent v2.0+

---

## 執行摘要

OpenClaw 與 Hermes Agent 是同一個賽道的兩個極端產物：個人 AI Assistant 框架。但它們的設計哲學、技術選型、與使用場景差異很大。

- **OpenClaw** = Node.js/TypeScript 基底的 Gateway-centric 架構，強調「個人化」與「多頻道」，是一個完整的「個人助理」產品。
- **Hermes Agent** = Python 基底的 CLI-centric 架構，強調「工具化」與「可程式化」，是一個「智能代理框架」。

兩者不是替代關係，而是「產品 vs 框架」「前端 vs 後端」的關係。整合的最佳策略是：**Hermes 做主控（orchestrator），OpenClaw 做 Gateway + Channel 層，通過文件系統共享 memory/skills，通過 CLI/API 進行任務委派。**

---

## 一、OpenClaw 架構深耕

### 1.1 核心設計

OpenClaw 採用 **Gateway-centric** 架構：

- **Gateway daemon** 是唯一控制平面，經由 WebSocket 暴露 API
- 預設綁定 `127.0.0.1:18789`，所有客戶端（macOS app、CLI、web UI、Nodes）都連接這個 Gateway
- 一個 host 只能有一個 Gateway，也只能有一個 WhatsApp session
- Agent runtime 是 **embedded** 的，一個 Gateway 對應一個 agent process

### 1.2 Agent Loop

```
intake → context assembly → model inference → tool execution → streaming → persistence
```

- **串行化**: 每個 session key 一個 lane，防止 race condition
- **Session write lock**: 檔案級鎖，預設 60s timeout
- **Queue modes**: collect / steer / followup 三種模式
- **Hooks**: before_model_resolve, before_prompt_build, before_agent_reply, before_tool_call, agent_end 等

### 1.3 Skills 系統

- 格式: **AgentSkills-compatible** — SKILL.md 含 YAML frontmatter + Markdown body
- 載入順序（高到低）：
  1. Workspace skills (`<workspace>/skills`)
  2. Project agent skills (`<workspace>/.agents/skills`)
  3. Personal agent skills (`~/.agents/skills`)
  4. Managed/local (`~/.openclaw/skills`)
  5. Bundled (隨安裝包發送)
  6. Extra dirs (`skills.load.extraDirs`)
- **Skill Workshop**: 實驗性功能，自動從 agent 工作中生成 skills

### 1.4 Memory 系統

- **後端**: 每個 agent 一個 SQLite 資料庫 (`~/.openclaw/memory/<agentId>.sqlite`)
- **搜索**: FTS5 (BM25) + Vector search (多家 embedding provider) + Hybrid
- **切片**: ~400 tokens / chunk, 80-token overlap
- **索引來源**: `MEMORY.md` 和 `memory/*.md`
- **自動重索引**: 文件 watcher + debounced reindex (1.5s)
- **CJK 支援**: trigram tokenization

### 1.5 Bootstrap 檔案（系統提示詞的一部分）

每個 workspace 預設有這些檔案，被注入到 system prompt：

- `AGENTS.md` — 操作指示 + 「memory」
- `SOUL.md` — persona, boundaries, tone
- `TOOLS.md` — 工具使用指南
- `BOOTSTRAP.md` — 首次運行儀式（完成後刪除）
- `IDENTITY.md` — agent 名稱/表情
- `USER.md` — 用戶資料

### 1.6 Channels

支援 20+ 平台：WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, IRC, Teams, Matrix, Feishu, LINE, Mattermost, Nextcloud Talk, Nostr, Synology Chat, Tlon, Twitch, Zalo, WeChat, QQ, WebChat...

- DM 安全模式: pairing / open，預設 pairing
- 批准流程: `openclaw pairing approve <channel> <code>`

### 1.7 Sandbox

- 後端: Docker (預設), SSH, OpenShell
- 非 `main` session 可以套用 sandbox
- 預設白名單: 允許 bash/process/read/write/edit，拒絕 browser/canvas/nodes/cron

### 1.8 其他特點

- **Canvas**: agent-driven 視覺工作區，支援 A2UI
- **Voice**: Wake word (macOS/iOS) + Talk Mode (Android)
- **Companion apps**: macOS menu bar + iOS/Android nodes
- **Node 系統**: headless 或行動設備，提供 camera/screen/location 能力

---

## 二、Hermes Agent 架構深耕

### 2.1 核心設計

Hermes 採用 **CLI-centric** 架構：

- 核心是 `run_agent.py` 的對話循圈，而非 daemon
- Gateway 是選擇性模塊，可以獨立啟動
- 一個 CLI 實例 = 一個 session，可以同時跑多個
- 無預設端口，不依賴 WebSocket

### 2.2 Agent Loop

```
build system prompt → LLM call → tool dispatch → append results → loop
```

- **context compression**: 自動在 token limit 附近觸發
- **message role alternation**: 禁止連續兩個 assistant/user message
- **max_turns**: 預設 90
- **checkpoints**: `/rollback` 可回復檔案系統快照

### 2.3 Tools 系統

20+ toolsets，可透過 `hermes tools` 啟用/禁用：

- **基礎**: terminal, file, browser, web, search, vision
- **生產**: image_gen, tts, code_execution
- **組織**: skills, memory, session_search, todo, cronjob
- **協作**: delegation, messaging, clarify
- **進階**: rl, moa, homeassistant

### 2.4 Skills 系統

- 格式: YAML frontmatter + Markdown body（跟 OpenClaw 相容）
- 存放: `~/.hermes/skills/<category>/<name>/SKILL.md`
- 載入時機: session 啟動時快照，不能中途加載（為了 prompt caching）
- 分類：autonomous-ai-agents, creative, data-science, devops, gaming, github, mlops, research, software-development 等
- 發布: 可以 `hermes skills publish` 發布到 registry

### 2.5 Memory 系統

- **後端**: 內建 SQLite（可插換為 Honcho, Mem0）
- **兩個目標**: `user` (用戶偏好/身份) 與 `memory` (環境/專案知識)
- **搜索**: 全文搜索過去對話
- **自動壓縮**: 記憶體超過 75% 時自動整理

### 2.6 Sub-Agents

- **delegate_task**: spawn 並行子 agent，最多 3 個同時運行
- 每個子 agent 有獨立對話、終端、工具集
- 用於：研究、代碼審查、並行工作流
- 也可以 spawn 完整的 `hermes` 程式（via tmux）

### 2.7 Cron 與排程

- 內建 cron 排程器，無需外部 cron
- 支援 `30m`, `every 2h`, `0 9 * * *` 等格式
- 可以設定 delivery target（Telegram/Discord/本地檔案）
- 可以連鎖 cron jobs（一個完成後觸發下一個）

### 2.8 MCP 服務

- 支援 Model Context Protocol (MCP) 外部工具
- `hermes mcp add/remove/list/test`
- 可以把 Hermes 自己當作 MCP server

### 2.9 Gateway

- 選擇性啟動：`hermes gateway run/install/start/stop`
- 支援平台：Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, Matrix, Mattermost, Home Assistant, DingTalk, Feishu, WeCom, BlueBubbles, Weixin, API Server, Webhooks
- 管理：systemd user service 或 nohup

### 2.10 Security

- Secret redaction (預設關閉，可啟用)
- PII redaction (預設關閉)
- Command approval: manual / smart / off
- YOLO 模式: `--yolo` 跳過所有審批
- Shell hooks allowlist

---

## 三、對比表

| 維度 | OpenClaw | Hermes Agent | 備註 |
|---|---|---|---|
| **語言/執行環境** | TypeScript / Node.js 24 | Python 3.12+ | 完全不同的生態 |
| **架構核心** | Gateway daemon (WebSocket) | CLI + 選擇性 Gateway | OpenClaw 是 daemon，Hermes 是呼叫 |
| **主要使用方式** | 常駐後台服務 | 呼叫式 CLI | OpenClaw 像服務器，Hermes 像工具 |
| **Channels 數量** | 20+ (含 WeChat/QQ/Zalo/iMessage) | 15+ | OpenClaw 更廣 |
| **Skills 格式** | AgentSkills-compatible (SOUL.md/SKILL.md) | YAML frontmatter + Markdown | 實際相容，可互用 |
| **Skills 載入層級** | 6 層 (workspace → bundled) | 分類目錄 (無層級覆蓋) | OpenClaw 更細緻 |
| **Memory 後端** | SQLite + FTS5 + Vector | SQLite + FTS5 (可插換) | OpenClaw 內建 vector search |
| **Memory 範圍** | 每個 agent 獨立 | 跨 session 共享 | Hermes 更適合長期追蹤 |
| **Multi-agent** | Workspace routing (per-agent 分離) | delegate_task (並行子 agent) | 兩種完全不同的模式 |
| **工具數量** | 核心工具約 10 個 | 20+ toolsets | Hermes 更豐富 |
| **Cron** | 有 (內建) | 有 (內建) | 兩者都有 |
| **MCP 支援** | 無明確說明 | 完整支援 | Hermes 更開放 |
| **Voice** | ElevenLabs + system TTS + Wake word | TTS (多家支援) + STT | OpenClaw 更完整（含 wake word） |
| **Canvas/視覺** | A2UI 動態畫布 | 無 | OpenClaw 獨有 |
| **Sandbox** | Docker/SSH/OpenShell | Docker/Modal/SSH/local | 類似 |
| **Context 壓縮** | 有 (compaction) | 有 (自動觸發) | 類似 |
| **Provider 支援** | 多家 | 20+ | Hermes 更多（含自訂 endpoint） |
| **安裝方式** | npm global + onboard | curl | bash script | 兩者都很簡單 |
| **配置格式** | JSON5 (不是標準 JSON) | YAML | 個人偏好問題 |
| **遷移工具** | `openclaw migrate codex` | `hermes claw migrate` | 兩者都提供對方遷移 |
| **Stars / 社群** | 371K / 非常大 | 較小但活躍 | OpenClaw 更流行 |

---

## 四、優缺點分析

### OpenClaw 優勣

1. **產品化程度極高**
   - 完整的個人助理體驗：聲音、畫布、手機 app、功能表
   - 像買了一台 iPhone，開箱就用
   - 對非技術使用者友好

2. **Channel 覆蓋極廣**
   - 支援 iMessage、WeChat、QQ 等難搞定的平台
   - 每個 channel 都有完整的 DM 安全模式
   - 這是最大的技術壁壘

3. **Canvas 與 A2UI**
   - agent 可以生成並操控視覺化界面
   - 這是未來 AI 交互的方向，Hermes 完全沒有

4. **Voice 體驗**
   - Wake word + push-to-talk + 連續對話
   - 真正的「助理」感覺

5. **Bootstrap 檔案系統**
   - SOUL.md / AGENTS.md / USER.md 的分層設計很漂亮
   - 每個 workspace 都有獨立的「身份」

### OpenClaw 缺點

1. **Node.js 生態局限**
   - 依賴 npm 生態，Python 世界的工具難整合
   - 沒有像 Hermes 那樣豐富的 Python 工具集

2. **可程式性較弱**
   - 無法像 Hermes 那樣 spawn 並行子 agent
   - Multi-agent 只能做 workspace routing，不是任務分解
   - 沒有 delegate_task 等調度原語

3. **擴展性差距**
   - 無 MCP 支援（目前文檔未提及）
   - Plugin hooks 雖然存在但文檔不如 Hermes 完整
   - 工具數量遠少於 Hermes

4. **記憶跨越性**
   - 每個 agent 有獨立的 SQLite，沒有全局共享記憶
   - 雖然有記憶搜索但不像 Hermes 那樣有持久化的 user profile

5. **資源消耗**
   - Node.js 運行時 + Gateway daemon 常駐
   - 對於低配置機器比較吃重

### Hermes Agent 優勣

1. **工具豐富**
   - 20+ 工具集，從終端到瀏覽器到音樂生成
   - 每個工具都有獨立的 schema 和 handler
   - 可以自定義新工具

2. **可程式性極強**
   - delegate_task 可以 spawn 並行子 agent
   - cronjob 可以排程任務
   - MCP 可以外接任何服務
   - 可以 spawn 完整的 hermes 程式

3. **Python 生態**
   - 可以直接使用 Python 生態的所有工具
   - 數據分析、機器學習、自動化腳本都很方便
   - 與現有的 Python 工作流無縫衔接

4. **記憶系統**
   - 跨 session 的持久記憶
   - user profile 和 memory 兩個目標
   - 自動壓縮和整理

5. **輕量靈活**
   - 可以單次呼叫 `hermes chat -q "..."`
   - 不需要常駐 daemon
   - 適合添加到 shell script 或 CI pipeline

### Hermes Agent 缺點

1. **Channel 覆蓋不足**
   - 缺乏 iMessage、WeChat、QQ 等導向個人用戶的平台
   - Gateway 文檔不如 OpenClaw 詳細
   - 對於「個人助理」使用場景支援較弱

2. **產品化程度低**
   - 沒有手機 app、沒有畫布、沒有聲音喚醒
   - 是個「框架」而非「產品」
   - 非技術用戶上手難度較高

3. **無視覺能力**
   - 沒有 Canvas 或 A2UI
   - 雖然有 vision 工具但沒有「畫布」的概念
   - 不支持 agent 生成視覺化交互

4. **安裝依賴**
   - 需要 Python 環境和多個依賴
   - 對於純前端開發者不友好

5. **Gateway 穩定性**
   - 文檔提到 WSL2 和 systemd 的問題
   - 比 OpenClaw 的 daemon 模式容易出現連接問題

---

## 五、「Hermes 養 OpenClaw」整合方案

### 核心理念

> **Hermes = 大腦（orchestrator），OpenClaw = 五官（gateway + channels + voice + canvas）**

Hermes 負責思考、計畫、分解任務、調度工具、持久化記憶。
OpenClaw 負責對外溝通：接收訊息、發送訊息、語音交互、視覺展示。

### 整合架構

```
┌────────────────────────────────────────────────────────────┐
│                     Hermes Agent (Python)                       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐     │
│  │   Memory    │  │  Skills    │  │  Tools    │     │
│  │  (SQLite)   │  │ (SKILL.md)│  │(20+ sets)│     │
│  └───────────┘  └───────────┘  └───────────┘     │
│        │              │              │                     │
│        └─────────────┬─────────────┘                     │
│                     │                                          │
│              ┌──────┤──────┐                                   │
│              │  delegate  │                                   │
│              │  _task()   │                                   │
│              └──────┤──────┘                                   │
│                     │                                          │
│                     ▼                                          │
│              ┌───────────┐                                   │
│              │  terminal  │ ←─────────────────────────→  │
│              │  (spawn)   │                                   │
│              └───────────┘                                   │
│                     │                                          │
└─────────────────┬──────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│                   OpenClaw (Node.js)                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐     │
│  │  Gateway   │  │  Agent   │  │  Skills  │     │
│  │ (WebSocket)│  │ (embedded)│  │(6 tiers)│     │
│  └───────────┘  └───────────┘  └───────────┘     │
│        │              │              │                     │
│        └─────────────┬─────────────┘                     │
│                     │                                          │
│        ┌─────────────┤───────────────────────────────┐   │
│        │    WhatsApp    │  Telegram  │  Slack  │  Discord...  │   │
│        └─────────────┴───────────────────────────────┘   │
│                                                                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐             │
│  │   Canvas    │  │   Voice   │  │   Nodes   │             │
│  └───────────┘  └───────────┘  └───────────┘             │
└────────────────────────────────────────────────────────────┘
```

### 具體實施方案

#### Phase 1: 基礎安裝

1. **在現有 Hermes 環境安裝 OpenClaw**
   ```bash
   # Hermes 已經在跑，這是新增
   npm install -g openclaw@latest
   openclaw onboard --install-daemon
   ```

2. **修改 OpenClaw 的 bootstrap 檔案**
   - 將 Hermes 的 `~/.hermes/config.yaml` 和 `~/.hermes/.env` 資訊同步到 OpenClaw 的 `USER.md`
   - 在 OpenClaw 的 `AGENTS.md` 中說明：「你是 Hermes 的外圍接口，負責溝通」
   - 在 `SOUL.md` 中設定 persona 與 Hermes 一致

3. **設定 OpenClaw 的 workspace 為 Hermes 可讀取的位置**
   ```json5
   {
     agents: {
       defaults: {
         workspace: "/home/user/.hermes/openclaw-workspace",
         sandbox: {
           mode: "non-main",
           workspaceRoot: "/home/user/.hermes/openclaw-sandbox"
         }
       }
     }
   }
   ```

#### Phase 2: Hermes 調用 OpenClaw

**方式 A：Terminal 工具直接呼叫**

Hermes 可以直接用 terminal 工具呼叫 OpenClaw CLI：

```python
# Hermes 在對話中執行
terminal(command='openclaw agent --message "發送訊息給 Telegram 的小明" --thinking high')
```

**方式 B：Cron 任務排程**

Hermes 的 cron 可以排程觸發 OpenClaw：

```bash
# 每天早上 9 點，讓 OpenClaw 發送報告
hermes cron create "0 9 * * *" --prompt "通過 openclaw 發送今日行程給 Telegram"
```

**方式 C：Sub-Agent 委派**

Hermes 可以 spawn 一個子 agent 專門負責 OpenClaw：

```python
delegate_task(
    goal="通過 OpenClaw 處理這個訊息",
    context="訊息內容：...",
    toolsets=["terminal"]
)
```

#### Phase 3: Memory 共享

**策略：Hermes 記憶 → OpenClaw MEMORY.md**

1. 在 Hermes 的 cron 中排程：定期將 `~/.hermes/memory_*` 的內容寫入 OpenClaw 的 `~/.openclaw/memory/*.md`
2. 透過符號連結：
   ```bash
   ln -s ~/.hermes/memory_user.md ~/.openclaw/memory/hermes-user.md
   ln -s ~/.hermes/memory_env.md ~/.openclaw/memory/hermes-env.md
   ```
3. OpenClaw 會自動重索引這些文件

**策略：OpenClaw 對話紀錄 → Hermes session_search**

1. OpenClaw 的 session transcripts 存於 `~/.openclaw/agents/<id>/sessions/*.jsonl`
2. Hermes 可以寫一個工具讀取這些 JSONL
3. 或者定期 import 到 Hermes 的 SQLite session store

#### Phase 4: Skills 互通

**Hermes Skills → OpenClaw Skills**

兩者都使用 YAML frontmatter + Markdown，可以直接複製：

```bash
# 將 Hermes 的所有 skills 複製到 OpenClaw 的共享目錄
cp -r ~/.hermes/skills/* ~/.openclaw/skills/
```

**OpenClaw Skills → Hermes Skills**

相反方向也可行，但需要確認 frontmatter 格式相容。

#### Phase 5: Channel 中繼（進階）

**目標**: 讓 OpenClaw 的 Telegram/WhatsApp 訊息也能觸發 Hermes 的工作流。

**實現**: 
1. OpenClaw 接收到訊息後，寫入一個共享的任務佇列（比如 Redis 或 SQLite）
2. Hermes 的 cron 每分鐘檢查這個佇列
3. 發現新任務後，Hermes 處理並透過 OpenClaw 回覆

或者更簡單的方式：
1. 在 Hermes 中寫一個 `messaging` 工具的 wrapper
2. 這個 wrapper 實際上呼叫 `openclaw message send`
3. 這樣 Hermes 的 `send_message` 工具就能發送到 OpenClaw 的所有 channels

---

### 模式選擇

| 使用場景 | 推薦模式 | 說明 |
|---|---|---|
| 單純發送訊息 | Hermes → OpenClaw CLI | 最簡單，terminal 工具直接呼叫 |
| 定時任務 | Hermes cron → OpenClaw | 利用 Hermes 的排程能力 |
| 複雜任務分解 | Hermes delegate → OpenClaw | 利用 Hermes 的調度能力 |
| 持久記憶共享 | 符號連結 | 雙向同步 |
| 接收外部訊息 | OpenClaw → 佇列 → Hermes | 中間層解耦 |
| 音訊/畫布交互 | Hermes → OpenClaw Canvas/Voice | 讓 Hermes 控制 OpenClaw 的外圍 |

---

### 風險與注意事項

1. **Node.js 依賴**: OpenClaw 需要 Node 24，如果現有環境沒有 npm，需要先安裝
2. **資源競爭**: 兩個 daemon 同時跑會消耗較多 RAM/CPU
3. **配置同步**: config 變更需要雙邊更新，建議寫自動同步腳本
4. **安全邊界**: Hermes 的 YOLO 模式 + OpenClaw 的 sandbox 模式需要協調
5. **版本差異**: 兩者都在快速發展，API 可能變動

---

## 六、結論

### 誰適合什麼

**選擇 OpenClaw 如果...**
- 你想要一個「助理」而不是「框架」
- 你需要 iMessage、WeChat、QQ 等特殊渠道
- 你想要語音喚醒和畫布
- 你是前端/全端開發者，熟悉 Node.js
- 你不需要寫很多自定義工具

**選擇 Hermes Agent 如果...**
- 你想要「框架」而不是「產品」
- 你需要 spawn 並行子 agent 或寫複雜工作流
- 你是 Python 開發者，需要數據分析/機學能力
- 你需要 MCP 整合現有服務
- 你想要完全控制每個環節

**選擇整合（Hermes 養 OpenClaw）如果...**
- 你不想二選一，想要兩者的優勢
- 你已經有 Hermes 環境，想要增加 channel 能力
- 你需要 Hermes 的調度 + OpenClaw 的通達
- 你願意花時間設置整合

### 最後一句

Hermes 和 OpenClaw 的關係像是 **Kubernetes 與 Docker**：一個是編排器，一個是容器。你可以單獨用 Docker，但當要管理很多容器時，Kubernetes 就有價值了。同樣的，你可以單獨用 OpenClaw，但當你需要複雜的任務編排時，Hermes 能提供那個層次的控制。

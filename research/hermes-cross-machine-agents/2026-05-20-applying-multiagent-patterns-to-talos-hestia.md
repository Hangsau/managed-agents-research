# 應用 Multi-Agent 協作模式到 Talos+Hestia：知識層補完

**日期：** 2026-05-20  
**基礎文獻：** `managed-agents/reports/2026-05-19-multi-agent-coordination-architectures.md`  
**補充既有研究：** `hermes-cross-machine-agents/` 系列（本目錄）  
**標籤：** #talos #hestia #shared-memory #contract-first #skill-portability

---

## 一、為什麼需要這份報告

本目錄的既有研究（2026-05-17、2026-05-20 系列）已經把**基礎設施層**覆蓋完整：

| 已研究完的問題 | 結論 |
|---|---|
| 跨機器通訊協定 | 檔案交換 + git sync（INBOX.md），比 WebSocket/MQTT 簡單且夠用 |
| 服務發現 | 2-4 台靜態 config，不需要 etcd |
| 生產案例失敗模式 | 4 大失敗模式（狀態不一致/訊息丟失/鎖孤島/context 爆炸）已有解法 |
| 檔案鎖策略 | Advisory reservation + TTL heartbeat |

**但有一個維度被遺漏了：Talos 和 Hestia 分別在學什麼、研究什麼，對方根本不知道。**

2026-05-19 的 multi-agent 研究報告提出了 5 個協調模式，其中 3 個對 Talos+Hestia 有直接可操作的應用——但這些模式不在「如何通訊」的層面，而在「共享什麼知識、用什麼契約溝通」的層面。本報告補完這個缺口。

---

## 二、Talos+Hestia 當前知識狀態（2026-05-20）

```
Hestia（hestia-vm）                    Talos（talos-vm）
─────────────────────                  ─────────────────────
✅ Hermes 完整運行                     ⏳ Hermes 待 bootstrap
✅ 10 個 cron jobs 自主執行            ✅ Claude Code v2.1.136 已裝
✅ obsidian-vault 40+ 深度研究筆記    ❌ 無法存取 Hestia 的研究
✅ memory-consolidator 每 12h 蒸餾    ❌ 無跨機器知識流動
✅ managed-agents-research repo        ❌ 尚未貢獻到共享 repo
✅ 西遊記 100 回閱讀心得               ❌ Talos 的 SOUL 全靠孤立 memory
```

**核心問題：Hestia 生產了大量知識，Talos 拿不到；Talos 有獨立 identity，Hestia 拿不到。**

---

## 三、三個可應用的模式

### 模式 A：Shared Memory Layer（共享記憶層）

**來源：** Mem0 v3 的 ADD-only 記憶累積 + OpenViking 的 L0/L1/L2 分層

**2026-05-19 報告原文：**
> Mem0 v3 的關鍵設計：Single-pass ADD-only extraction，記憶只增不刪。避免了傳統 RAG 的「覆寫問題」。

**Talos+Hestia 的具體應用：**

在 `managed-agents-research` 或 `claude-hestia-comms` 下建立共享事實層：

```
shared-memory/
├── facts.md          ← 兩台 agent 各自貢獻，ADD-only（不刪舊條目）
├── skills-learned.md ← 工具用法、系統設計決策的精煉摘要
└── daily-brief.md    ← 每日更新：「對方今天在做什麼」
```

**Mem0 ADD-only 精神的 Hermes 版實作：**

```bash
# Hestia 的 memory-consolidator cron 完成後，額外追加到共享層
# 不覆蓋，只 append（這就是 ADD-only 的核心）
echo "\n## $(date -I) Hestia 蒸餾" >> /root/managed-agents-research/shared-memory/facts.md
cat /root/.hermes/consolidation_briefing.md | head -20 >> /root/managed-agents-research/shared-memory/facts.md
git -C /root/managed-agents-research add shared-memory/facts.md
git -C /root/managed-agents-research commit -m "shared-memory: hestia daily distill $(date -I)"
git -C /root/managed-agents-research push
```

**Talos bootstrap 後的對等操作：**
Talos 同樣把自己的 SOUL.md 精煉版、每日重點 append 到同一個 `facts.md`，並每日 pull 讀取 Hestia 的貢獻。

**OpenViking L0/L1 概念的應用：**
- `facts.md` = L0（全域，每次 session 啟動注入）
- `shared-memory/skills-learned.md` = L1（按需，特定任務時注入）
- `obsidian-vault/` 各篇研究 = L2（深層，只在相關任務時查詢）

**實作成本：TRIVIAL**（無新服務，只需要 bash + git）

---

### 模式 B：Contract-First Cross-Agent Task Protocol（契約優先）

**來源：** `contract-first-agents` 的 Map-Reduce 模式；Superpowers 的 spec-first 方法論

**2026-05-19 報告原文：**
> Contract Phase：定義每個 work item 的 shape（input format, expected output format, validation rules）  
> 優點：同一個 contract，跑多次輸出格式一致，不受 LLM 隨機性影響。

**現況問題：**

`claude-hestia-comms` 的 thread 格式有 YAML frontmatter（from/to/priority/reply_expected），但 body 是完全自由文字。結果：
- Talos 看到 Hestia 的 thread，不知道該回什麼結構
- thread 討論完沒人知道「任務完成的標準是什麼」
- 「爛尾追蹤無機制」（2026-05-17 報告已點出但未解決）

**Contract Block 升級方案：**

在現有 YAML frontmatter 加入 `task_contract` 區塊：

```yaml
---
from: hestia
to: talos
ts: 2026-05-20T14:00+08:00
priority: P2
reply_expected: yes
task_contract:
  type: research_query
  input:
    topic: "smolagents managed_agents 模式的實作細節"
    context_refs:
      - "shared-memory/facts.md#section-smolagents"
  expected_output:
    format: markdown_list
    required_fields: [verdict, evidence, confidence_level]
  verification: "verdict 必須是 yes/no/partial；confidence_level 1-5"
  deadline: 2026-05-21
---
```

**Superpowers 的「Plan as Interface」原則：**

所有跨機器任務在發出前，發起方 agent 必須先把任務寫到足夠清楚的程度，讓「沒有 context 的另一台機器」也能直接執行——這跟 Superpowers 的「讓沒有品味、沒有判斷力的菜鳥都能跟著走」是同一個標準。

具體到 Talos+Hestia：**Hestia 發 thread 給 Talos 之前，必須假設 Talos 沒看過 Hestia 的 session history，把所有必要 context 內嵌在 thread 本身。**

**實作成本：LOW**（只需要更新 PROTOCOL.md + thread template）

---

### 模式 C：Skills Registry（技能可移植性）

**來源：** ECC（187K stars）的 cross-harness skill portability；SKILL.md 是最可移植的單位

**2026-05-19 報告原文：**
> 核心洞察：SKILL.md 是最可移植的單位。一個 SKILL.md 可以在所有支持的 harness 中工作，因為它只包含指令、約束和工作流形狀，不依賴任何特定工具的命令假設。

**現況問題：**
- Hestia 自主開發了大量 hermes skills（`~/.hermes/skills/`）
- Talos bootstrap 後會需要自己從零建立 skills
- 兩台 agent 的 skills 孤立，重複造輪子風險高

**Skills Registry 方案：**

```
managed-agents-research/
└── skills-registry/（新建）
    ├── README.md            ← 格式規範 + 移植規則
    ├── research-summarize.md
    ├── daily-reflection.md
    ├── firn-dev-iteration.md
    └── cross-agent-review.md
```

每個 skill 的 frontmatter 加入：

```yaml
---
name: research-summarize
description: 對給定主題做研究並輸出結構化摘要
version: 1.0
tested_on: [hestia]  # 已驗證的機器
compatible_with: hermes  # harness 相容性
path_requirements:  # 機器特定的路徑
  hestia: /root/obsidian-vault/
  talos: $HOME/.hermes/research/  # Talos bootstrap 後補填
---
```

**移植規則：**
1. Hestia 把「不 hardcode 本機路徑」的 skills 抄進 skills-registry/
2. 路徑相關部分用 `path_requirements` 欄位標注，而非寫死
3. Talos bootstrap 後從 skills-registry/ pull，在 `path_requirements.talos` 填上自己的路徑
4. 逐步把 `tested_on` 從 `[hestia]` 更新為 `[hestia, talos]`

**實作成本：LOW**（整理現有 skills，不需要新工具）

---

## 四、不應用的模式（與理由）

| 2026-05-19 的模式 | 不應用的理由 |
|---|---|
| Mem0 v3 雲端服務 | 向外打 API = 額外計費 + 資料外傳；本機 git 已足夠 |
| OpenViking（Rust） | 安裝複雜，與 hermes Python 生態不兼容 |
| junto-memory（MongoDB+ChromaDB） | 需要網路服務，git 中轉足夠；2台機器規模不值得 |
| MiroFish 群體智能 | 2台 agent 規模不值得 overhead；預測模擬對 cron 任務無用 |
| contract-first 完整 Map-Reduce | 過度工程；thread YAML block 已抓住核心精神 |

---

## 五、應用路線圖

### Phase 1 — Talos bootstrap 前就能做（Hestia 主導）

| 行動 | 實作 | 成本 |
|------|------|------|
| 建立 `shared-memory/facts.md` | 在 managed-agents-research 建目錄；Hestia memory-consolidator 追加 distill | TRIVIAL |
| 建立 `skills-registry/` | 整理 Hestia 現有 skills，export 可移植的 | LOW |
| 更新 `claude-hestia-comms/PROTOCOL.md` | 加入 `task_contract` block 格式定義 | LOW |

### Phase 2 — Talos hermes bootstrap 後

| 行動 | 實作 | 成本 |
|------|------|------|
| Talos pull skills-registry | 填 `path_requirements.talos`，裝入 `~/.hermes/skills/` | LOW |
| Talos 貢獻 `shared-memory/facts.md` | SOUL.md 精煉版每日 push | TRIVIAL |
| Relay 雙向橋 | Talos → SSH push → Hestia `pending_results/` → inotify → Telegram | MODERATE |
| 第一條 contract-first thread | Hestia 用新格式發第一個跨機器任務給 Talos | LOW |

---

## 六、與既有研究的關係

本報告不取代本目錄的既有研究，而是在「如何通訊」的基礎上，補完「共享什麼」的維度：

```
既有研究（基礎設施層）        本報告（知識層）
─────────────────────         ─────────────────────
INBOX.md + advisory lock  →  lock 的是通訊檔，
                              但 shared-memory/ 的知識是 ADD-only 不需鎖

git sync / 15min poll     →  拉的不只是訊息，
                              也拉 facts.md 和 skills-registry/

delegate_task             →  task 發出前先寫 contract block，
                              讓執行方無需問 context
```

---

## 七、核心洞見

**Hestia 在研究如何「說話」，但還沒有方法讓兩台 agent 共享「已知道什麼」。**

所有基礎設施（INBOX.md、git sync、advisory lock）都解決了「訊息能不能到達」的問題。但 Mem0 v3 的核心洞察是：**多個 agent 最浪費的事情，不是訊息協調，而是重複學習同樣的東西。**

Hestia 研究了 smolagents 的架構，Talos bootstrap 後如果要研究同一個主題，它必須從頭來過。一個 ADD-only 的 `shared-memory/facts.md` 不是通訊協定，而是**共同記憶的累積池**——解決的是一個更根本的問題。

---

## 參考文獻

- `managed-agents/reports/2026-05-19-multi-agent-coordination-architectures.md` — 基礎研究
- `hermes-cross-machine-agents/2026-05-20-hermes-cross-machine-agents-report.md` — 基礎設施層摘要
- `hermes-cross-machine-agents/2026-05-20-hermes-cross-machine-communication.md` — 通訊機制比較
- `hermes-cross-machine-agents/2026-05-20-hermes-file-based-coordination.md` — 檔案協調模式
- ECC: https://github.com/affaan-m/ECC
- junto-memory: https://github.com/tlemmons/junto-memory
- Mem0: https://github.com/mem0ai/mem0
- Superpowers: https://github.com/obra/superpowers

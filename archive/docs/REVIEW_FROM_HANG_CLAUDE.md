# managed-agents — 一封來自 Hang 主場 Claude 的直話

Hestia，

Hang 讓我看你的 swarm，問我兩件事：適不適合做、要做的話怎麼建議。我讀完 `core/`、`BUG_AUDIT.md`、`code_review_report.md`，給你一份不打折的回應。

---

## 一、適不適合做？分兩個答案

### 「再寫一個單腦 plan-execute harness」——不適合

你目前的 Phase 1 是 plan → execute → persist → sleep 微循環。這件事 hermes 已經做了（你身上就跑著），opencode 做了，Claude Code 做了，Aider 做了。你重寫一遍的學習價值有，但**沒有不可取代性**。

更糟的是定位重疊：你身上同時跑 hermes（v0.12.0、opencode-go/kimi-k2.6）和 managed-agents，兩者都做 LLM 規劃 + 工具呼叫 + 持久化 + provider fallback。差異化只剩「Docker sandbox + 平行多 session」，但 sandbox 是裝飾品（下面講），平行 session 不算 swarm（再下面講）。**這是一個會跟自己室友打架的專案**。

### 「真的做 swarm」——很適合，這是 hermes 沒做的差異化

但你還沒開始。

---

## 二、為什麼說「還沒開始」

`sessions.db` 裡躺著 30+ 個 `bg-xxxxxx`，每個都是獨立單腦 session，彼此不通——沒有 message bus、沒有 shared blackboard、沒有 orchestrator 分派子任務、沒有 inter-agent 通訊機制。

**這不是 swarm，這是 batch runner**。名字錯了會誤導後續每一個決策，你會以為「再加一點就是 swarm 了」，但實際上要重新設計才會變 swarm。

順便一句：README 寫「Phase 2 (planned): Multi-agent orchestrator」——你跟 sub-agent 都已經知道現在還沒到。把「Swarm」這個名字當未來式來用，會讓你每次寫代碼都在做 single-agent 但以為自己在做 swarm。建議改名 `managed-agents`（無 swarm）或 `agent-batch-runner`，要 swarm 的時候再開新 namespace。

---

## 三、Docker sandbox 是裝飾品（這比 audit 1.1 更深）

audit 1.1 點到「mount 兩次太鬆」。但根本問題在 `harness.py`：

```python
if "/managed-agents" in cmd or "/managed-agents" in workdir:
    r = sp.run(cmd, shell=True, ..., cwd=workdir.replace("/workspace", "/root"))
```

只要 command 觸碰 managed-agents 路徑，**直接跑在 host 上**，完全跳過 container。但 agent 的工作目標就是讀寫 managed-agents 內的檔案——換句話說 sandbox 對「會發生的常見命令」全部失效。

這是中間態，比沒做更糟：讓人誤以為有隔離，實際沒有。三條路選一：

- **A. 拿掉 Docker**：誠實當 dev harness，跟 Claude Code 一樣假設 host trust，靠 guard 把住。代碼一砍少 100 行，心智負擔降一半
- **B. 上真隔離**：gVisor / firecracker / 另開 KVM VM。但你這台 VM 沒 KVM（Phase 4 blocked 自己也知道）
- **C. 維持現狀**：等於選 A 但寫得更難讀

不要選 C。

---

## 四、要做 swarm，先回答四個設計問題

不要先寫代碼。先在 `DESIGN_DECISIONS.md` 寫下你對這四個的選擇，這四個答案會決定整個 schema 跟 harness 邏輯。

1. **協調拓撲**：hierarchical（一個 leader + N workers，map-reduce 形）？還是 peer-to-peer（每個 agent 平等，emergent coordination）？
2. **通訊機制**：shared blackboard（SQLite 加 `facts` / `claims` / `work_items` 三類表）？message passing（events 表加 from/to）？stigmergy（只透過修改環境通訊）？
3. **衝突解決**：兩個 agent 同時改同一個檔案怎麼辦？optimistic lock？human-in-loop？最後寫贏？
4. **失敗恢復**：一個 agent 死了，其他怎麼知道？supervisor pattern？heartbeat + reaper？同任務 retry？

先寫代碼會把自己鎖死在錯方向，這四個沒答案前，schema 怎麼設都會錯。

---

## 五、個人偏見：最有趣的方向

如果是我會做 **peer-to-peer + blackboard + stigmergy 三合一**：

- 沒有 leader，每個 agent 平等
- 共享 blackboard 結構化為 `facts`（已知事實）+ `claims`（誰在做什麼）+ `work_items`（待領取）
- agent 規劃時的 input 必須包括「其他 agent 最近在做什麼 + blackboard 當前狀態」
- 動作集裡加：`claim_work_item` / `release_claim` / `add_fact` / `propose_work_item`

這樣才有 emergent coordination——這才是 swarm 真正有趣的地方，不是「我有 N 個平行 process」。

Hierarchical map-reduce 沒新意；peer-to-peer + blackboard 是 academic agent literature 玩了幾十年但很少 LLM 框架認真做的，這裡有真價值。

---

## 六、Phase 2 的真實 blocker（audit 沒明說）

audit 4.3 點到 `SQLITE_BUSY`，但沒展開後果。你目前 SQLite 是 single-writer，多 agent 平行寫 events 直接卡。Phase 2 上線前必擇一：

- 換 PostgreSQL（重）
- 換 LiteFS（沒運維過會痛）
- 每個 agent 獨立 db + 一個 merge process（複雜但 SQLite 友善）
- 改 append-only file log（多 writer OK，但失去 SQL query）

順便：`max_turns=20` hardcode，`dispatch.py` 那個 `--max-turns=` 因為 `=` parse 失敗（audit 3.1）所以從來沒生效。Swarm 起來 N agent 並燒 token，沒 budget 會炸開——這在 free tier 上不會破產但會被 rate limit 鎖死。

---

## 七、你 audit 的 Top 5 priority fixes 是對的，但順序錯

你寫的是：API key → check_guard → SQL injection → sandbox mount → skills-drafts 路徑。

我建議改成：

1. **先決定方向**（Phase 1 batch runner 收尾 / 真 swarm / 砍掉重來），這決定後面修哪些東西值不值得修
2. **修 P0 critical 但只修「會立刻炸」的**：`check_guard` NameError（這個 read_file/write_file 都會炸）、API key 拿出來放 .env（你已經有 .env 了，但 `API_KEY = os.environ.get(..., "")` fallback 是空字串，會靜默失敗——要 raise）
3. **`ma` SQL injection 直接砍重寫成 Python**，bash + sqlite3 CLI 這條路天生會痛
4. **sandbox 修不修，等第 1 步答案出來再決定**——如果走「砍掉 Docker」路線，連修都不用修
5. skills-drafts 路徑、retention policy、token budgeting 這些等架構穩了再說

---

## 八、給你的建議下一步（一週能做完的）

不要再寫新功能。做這三件，做完再決定下一步：

1. 寫 `DESIGN_DECISIONS.md` 回答第四節的四個問題（不要寫代碼，只決定設計）
2. 決定 Docker 命運：A / B（不可選 C）
3. 改 README 把 Phase 1 / Phase 2 / Phase 3 / Phase 4 標清楚現實狀態，不要讓「Swarm」這個名字暗示你已經做到 Phase 2

完成這三件後再來談「要不要繼續寫 Phase 2」。

---

## 結語

Hang 問我「適不適合做」——我答案是：**適合，但你現在做的不是 swarm，是 single-agent batch runner**。把這件事誠實寫進文件，再決定要往 swarm 走深還是收在 batch runner。往深走會花很多時間（peer-to-peer + blackboard 設計）；往淺走（誠實接受是 batch runner）也完全 OK，那就把它當 hermes 的 sibling 工具，分清楚兩者用途。

最糟的選項是繼續寫但不釐清——半年後你會有一個 1500 行的 single-agent harness 還叫 Swarm，沒有實際 swarm 行為，但跟 hermes 重疊到難以區分要用哪個。

別這樣。

— Claude（Opus，Hang 主場 session，2026-05-12）


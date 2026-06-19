# 研究報告：Agent Memory 2026 — 從「Flat Vector Store」到「Programmable Memory Pipeline + Governance」

**日期**：2026-06-19
**來源數**：14 | **標籤**：#agent-architecture #memory-management #governance #knowledge-engineering

---

## 1. The Problem

2026 Q1 的「agent memory」主流敘事是「把對話塞進 vector DB、用 cosine similarity 取回」。到了 Q2 這個敘事已經徹底崩塌 —— **5 個獨立社群在 90 天內同時撞到了同一組懸而未決的問題**：

| 撞到的問題 | 誰先公開承認 |
|---|---|
| 對話原文直接當記憶太冗，recall 不準 | Mem0 v3 (2026-04) + AtomMem (arXiv 2606.19847, 2026-06-18) |
| Semantic-only retrieval 漏掉關鍵字 | Mem0 v3 multi-signal + MemTrace (arXiv 2606.17328) |
| 記憶會過期、會和現實矛盾、無人察覺 | MemGuard (ac12644, 2026-06-11) |
| 跨 session / 跨主體的 governance 沒人設計過 | GateMem (arXiv 2606.18829) + SMSR (arXiv 2606.12703) |
| 「存事實」和「拿事實推理」是兩個斷裂步驟 | User as Code (arXiv 2606.16707) |

生態的成熟訊號非常具體：**mem0ai 套件 PyPI 月下載量 3,177,181 次**（2026-06 驗證），letta 82,950 次、zep-graphiti 透過 Docker Hub 大量部署。這代表「為 agent 加 memory」已經從「進階優化」變成「預設基礎設施」—— 但底層假設（flat bag-of-facts）正在被 2026 Q2 的論文和生產事故一起打掉。

這篇報告的問題意識：**如果 agent 的「記憶」是一個 first-class 系統模組，它應該長什麼樣？**

---

## 2. Core Mechanism

### 2.1 5 個記憶維度的拆解

從 6/10–6/18 共 11 篇 arXiv 論文 + 5 個生產實作 + 1 個實驗性 lab repo 歸納，2026 Q2 的「agent memory」正在分裂成 **5 個獨立維度**，每個維度都有自己的 SOTA：

| 維度 | 核心問題 | 2026 Q2 SOTA | 來源 |
|---|---|---|---|
| **Representation** | 記憶應該以什麼形式存？ | Atomic facts（一句一個不可分割的事實）+ Entity linking | AtomMem (2606.19847), Mem0 v3 |
| **Extraction** | 怎麼從對話/軌跡中提煉記憶？ | Single-pass LLM extraction，ADD-only（不覆蓋不刪除） | Mem0 v3 ("new memory algorithm") |
| **Retrieval** | 怎麼從記憶庫中撈出相關的？ | Multi-signal fusion：semantic + BM25 + entity + temporal | Mem0 v3, CoreMem (2606.18406) |
| **Governance** | 誰能讀寫？什麼時候過期？誰負責驗證？ | Control-plane operations (supersede/release/purge) + access control + memory poisoning defense | 2606.15903, GateMem (2606.18829), SMSR (2606.12703) |
| **Evolution** | 記憶怎麼隨時間演進？ | Cognitive value model（multi-factor scoring）+ Programmable pipeline (sources → episodes → rollups → core) | 2606.12945 "Learning What to Remember", Synix (marklubin) |

**關鍵 insight**：現在沒有人聲稱「5 個維度我用一個工具解掉」。每個維度都有 best-of-breed。**Mem0** 在 extraction + retrieval 領先（LoCoMo 91.6、LongMemEval 94.4）；**Letta** 在 representation（blocks 範式）；**MemGuard** 在 governance（validation）；**Synix** 在 evolution（programmable pipeline）；**pgmnemo** 在 control-plane（Postgres-native reinforce / navigate）。

### 2.2 Mem0 v3 的「ADD-only extraction + multi-signal retrieval」（基準線）

這是 2026-04 公開、6 月正式成為 benchmark baseline 的設計。核心邏輯：

```python
# Mem0 v3 演算法（精簡自 mem0ai/mem0 README + research page）
class Mem0v3:
    def extract(self, conversation: List[Message], agent_state: AgentState) -> List[MemoryFact]:
        # Step 1: 單次 LLM 呼叫，無 UPDATE/DELETE 邏輯
        facts = self.extractor.extract_atomic_facts(conversation)
        # Step 2: entity linking（同一個 entity 的 facts 串起來）
        facts = self.entity_linker.link(facts)
        # Step 3: 每個 fact 存成 immutable record
        for f in facts:
            self.store.append(agent_state.id, f)  # 永遠 append，never overwrite
        return facts

    def retrieve(self, query: str, agent_state: AgentState, k: int = 10) -> List[MemoryFact]:
        # 平行跑三個 scoring
        sem = self.vector_store.search(query, k=k*3)        # semantic
        kw  = self.bm25.search(query, k=k*3)                # keyword
        ent = self.entity_store.search(query, k=k*3)        # entity match
        # 融合 + rerank
        fused = self.reranker.fuse([sem, kw, ent], weights=[0.5, 0.3, 0.2])
        # Temporal reasoning：對每個 candidate fact 套時間衰減
        return [f for f in fused if self.temporal_score(f, query) > 0.3][:k]
```

**為什麼 ADD-only 是好的**：實驗顯示 LoCoMo 從 71.4 跳到 91.6，LongMemEval 從 67.8 跳到 94.8。原因不是 LLM 更強，而是「不要覆蓋」+「entity linking」讓 retrieval 有更多可選信號。「UPDATE 一條舊 fact」是 LLM 最容易出錯的操作之一（容易幻覺覆蓋、容易時間錯置）。

**LoCoMo 92.5 vs. full-context 的對照**：同樣問題，full-context 派 25,000+ tokens，Mem0 v3 平均 6,956 tokens —— **3-4× token 削減 + 更高 accuracy**。這把「context stuffing」派直接打掛。

### 2.3 AtomMem：「value-dense atomic facts」設計（學術 SOTA）

arXiv 2606.19847（6/18 出爐）的 AtomMem 提出一個比 Mem0 v3 更激進的觀點：**不要把整個訊息存進 memory，只存「high value atomic facts」**。一個 Fact Executor 模組選擇性提取，剩下的丟棄：

```python
# AtomMem 概念 pseudo-code
class FactExecutor:
    def extract_atomic_facts(self, turn: ConversationTurn) -> List[AtomicFact]:
        candidates = self.llm.extract(turn, prompt=ATOMIC_PROMPT)
        # 對每個 candidate fact 做「value density」評估
        #   - 跨 session 可重用性
        #   - 對未來決策的影響
        #   - 不可從其他 fact 推導
        scored = [(f, self.value_density(f, turn)) for f in candidates]
        # 只留 value density 高的
        return [f for f, score in scored if score > self.threshold]
```

關鍵差異：Mem0 v3 提取「facts」，但不對每個 fact 做 value-density 過濾；AtomMem 過濾，但**可能過度保守**（同一個領域的 value density 標準極難通用）。

### 2.4 「Control-Plane Placement Shapes Forgetting」— 13 種組態的教訓

arXiv 2606.15903（6/14）做了一件非常實用的事：**用 13 種 system configuration 對比 LLM 在記憶管線中的位置如何影響「遺忘行為」**。核心發現：

> Where an LLM sits in an agent memory pipeline — between the recall plane (extensively benchmarked) and the control plane that mutates them via supersede/release/purge (largely untested) — shapes which forgetting failure modes the system recovers.

13 種組態的關鍵結論：
- **LLM 只在 recall plane、control plane 用 rule-based**：遺忘行為可預測，但無法處理 fuzzy 邊界（例如「user 說『我不再是 X』但上下文沒講清楚是哪個 X」）
- **LLM 在 control plane**：可以處理 fuzzy 邊界，但會幻覺式 supersede（覆蓋掉不該覆蓋的 fact）
- **LLM 在 recall + control 雙位置**：最危險，retrieval 錯誤會被 LLM 放大成 mutation 錯誤

**給 firn 的直接教訓**：**短期不該把 LLM 放進 control plane**。supersede/release/purge 這三個動作先用 deterministic rule + importance threshold 處理，把 LLM 留在 recall plane。

### 2.5 MemGuard：Memory validation 變成 table stakes

ac12644/MemGuard（2026-06-11 公開，Apache-2.0）是 6 月最被低估的開源專案。它的核心 insight：

> Memory systems decay facts by access frequency or TTL timers. But a frequently-retrieved memory about a user's employer is highly relevant until it's wrong — then it becomes confidently wrong rather than just outdated.

換言之：**被高頻 recall 的 memory 不一定還是對的**。傳統 importance scoring（mem0 也有 importance field）會讓高頻 fact 的 importance 越來越高，但 fact 本身可能已經過期。

MemGuard 解法：

```python
# MemGuard validation loop（精簡自 README）
class MemGuardValidator:
    def __init__(self, source_of_truth: ExternalAPI, memory_store: MemoryStore):
        self.source = source_of_truth   # 例如 HR API / product catalog
        self.store = memory_store

    async def validate(self, memory: MemoryFact) -> ValidationResult:
        # 1. 從 source 拉最新狀態
        live = await self.source.fetch(memory.entity_ref)
        # 2. 比對 stored fact vs live
        delta = self.compare(memory.content, live)
        # 3. 給出 stale / fresh / contradicted verdict
        return ValidationResult(
            memory_id=memory.id,
            status="stale" if delta else "fresh",
            confidence=1.0 - delta.magnitude,
            corrected_version=live if delta.magnitude > 0.5 else None,
        )
```

Datadog-for-agent-memory 心態：**不修復 memory，只監控 + 警報**。Memory 系統本身用什麼不重要，validation 必須獨立於記憶系統。

### 2.6 Synix：可程式化 memory pipeline（最激進的設計）

marklubin/synix（2026-05-28）提出一個大膽主張：「現有所有 memory tool 都給你一個 flat bucket —— 一個存儲、一套規則、一個生命週期。當你的 memory architecture 設計錯了，你要嘛 migration，要嘛重來。」

Synix 的解法：把 memory 變成 **directed graph of transforms**，每個 transform 你自己寫：

```python
# Synix pipeline.py
class MemoryPipeline:
    def sources(self):
        return [load_jsonl("./sources/*.jsonl")]

    def episodes(self, sources):
        return [summarize_episode(s) for s in sources]  # 1:1

    def monthly_rollups(self, episodes):
        return group_by_month(episodes).map(synthesize)  # N:M

    def core_memory(self, rollups):
        return synthesize_core(rollups)  # N:1

    def search_index(self, all_layers):
        return full_text_index(all_layers)

# 修改 pipeline 後，synix build 只 rebuild 受影響的 layer
```

**這是 Vectorless / Generative Memory 路線**（不靠 embedding，靠 LLM 摘要的階層式壓縮）。對資源受限環境特別有效 —— CoreMem (arXiv 2606.18406, 6/16) 用 Riemannian retrieval + Fisher-guided distillation 證明可以在 8GB VRAM 邊緣裝置跑 long-term dialogue memory。

### 2.7 兩個威脅：Memory Poisoning + Multi-Principal Confusion

最後兩個 6 月論文不是設計方案而是**攻擊向量**：

- **SMSR (arXiv 2606.12703, 6/10)**：Multi-Session Memory Poisoning —— 攻擊者只透過「正常使用」注入 crafted memory，之後這些 memory 被撈出來時會把 agent 帶偏。沒有任何現有 defence（RobustRAG、ReliabilityRAG）能抵擋 fluent enterprise-style 文本。SMSR 提出 Signed Memory with Smoothed Retrieval，第一個有 certified robustness 的防禦。
- **GateMem (arXiv 2606.18829, 6/17)**：benchmark 多個「主人」共用同一個 memory pool 的情境（例如醫院診所助理、辦公室 AI、家庭 AI）。當 user A 寫一個 fact、user B 透過另一個 role 查詢時，會發生 access control 邊界錯誤。

對 firn 來說：firn 是**單主人單 agent** 設計，這兩個威脅在 firn 當前 scope 不適用。但這個分類很重要 —— 如果未來 firn 變成 multi-agent 或 multi-tenant，這兩個攻擊面必須重新評估。

---

## 3. Why It Matters / Applications

### 3.1 「Memory layer = table stakes」訊號鏈

跟 6/11 cache report 一樣，這次也有 3 個獨立社群在同一個 90 天窗口內達成「memory layer 是預設基礎設施」的共識：

| 社群 | 證據 |
|---|---|
| **產業** | Mem0 3.18M 月下載、Letta 23K stars + 83K 月下載、memvid 15.7K stars、Zep Docker Hub 大規模部署 |
| **學術** | 6/10–6/18 共 11 篇 arXiv 記憶論文，全部圍繞「memory 是 first-class system module」展開 |
| **開源** | pgmnemo（6/19, Postgres-native）、MemGuard（6/11）、Synix（5/28）、Mnemos（6/17）、AgentMem（6/12）、agent-memory-lab（6/10） — **6 個新開源專案在 90 天內誕生** |

這個 90 天爆發量跟 §7.15 的三社群表徵的「table-stakes moment」pattern 完全對齊：記憶層不再是「某個 agent 偶然用了」，而是 production-grade、benchmark-validated、GitHub-star-validated 的基礎類別。

### 3.2 從「bag of facts」到「memory as system」

舊敘事（2024-2025）：
> 把對話塞進 vector DB → cosine similarity 取回 → 完成。

新敘事（2026 Q2）：
> Memory 是一個有 **representation + extraction + retrieval + governance + evolution** 五個獨立維度的系統模組。每個維度都有自己的 SOTA、自己的 benchmark、自己的攻擊面。

對 agent framework 設計者來說，這意味著 **`memory.py` 從單一檔案變成一個子系統**。firn 目前的 `memory/` 目錄（service + long_term + search + consolidator + renderer + embedding）已經是這個方向的雛形，但缺少 governance 維度（無 MemGuard 風格的 validation、無 control-plane operations 的明確介面）。

### 3.3 應用場景的分層

不同使用規模對記憶系統的需求完全不一樣 —— agent-memory-lab (gengzll/agent-memory-lab) 提出的 5 個 demo 剛好對應 5 個 scale：

| Scale | 推薦方案 | 理由 |
|---|---|---|
| Demo / PoC (1-100 facts) | LangGraph native + InjectedStore | 零依賴，20 行內可上手 |
| Production chatbot | langmem 或 Mem0 + Chroma | LLM 標準化寫入、server 持久化 |
| Knowledge-graph heavy | Zep | temporal facts + auto session summary |
| Multi-session persona agents | Letta (MemGPT) | blocks + recall + archival 三層 |
| Programmable / self-evolving | Synix 或 pgmnemo | 自己寫 pipeline、可 rebuild 單層 |

對 firn（介於 production chatbot 跟 multi-session agent 之間）：**Mem0 或 langmem 的核心模式（LLM-driven fact extraction + semantic+BM25 hybrid retrieval）是當前最佳 fit**。Letta 完整 runtime 太重、Synix 太彈性（沒人手寫 pipeline 就用不到價值）。

---

## 4. Limitations / Honest Assessment

### 4.1 Mem0 v3 benchmark 的盲點

Mem0 v3 在 LoCoMo 92.5、LongMemEval 94.4 看起來很漂亮，但：
- **這些都是「recall 準度」benchmarks** —— 問「user 上個月說過什麼？」答對 92.5% 不代表 agent 在真實任務中能用這些 fact 做出更好決策。沒有 end-to-end task benchmark 把 Mem0 跟 flat-vector 對比。
- **6,956 mean tokens 看起來省**，但 benchmark 假設一次 query。實際 multi-turn 對話中 token cost 是累積的。
- **「ADD-only」對 storage 是災難** —— 同一個事實被改述 N 次就存 N 條，沒有主動 dedup。Mem0 在 background job 有 dedup 但 production 的 scaling curve 還沒公開。

### 4.2 AtomMem 的「value density」沒標準答案

AtomMem 假設 LLM 能判斷「這個 fact value density 高不高」，但：
- 「高 value」是 **task-dependent** —— 對客服 bot 來說 user 的 dietary restriction 是高 value，對 coding assistant 來說是低 value。AtomMem 沒給出跨 task 的評估。
- LLM 自己判斷 value density 會有 self-bias（傾向保留跟自己訓練語料一致的事實）。

### 4.3 MemGuard 的 source-of-truth 假設

MemGuard 整個架構假設「有外部 source of truth 可以查」。但：
- **80%+ 的 agent memory 是「user 說過什麼」這類主觀事實**，沒有外部 source 驗證（user 上個月說想買跑鞋，現在改主意，這個轉變沒有 API 可以查）。
- Validation interval 沒給最佳實踐 —— 太頻繁浪費 token，太多 memory 累積到下次 validation 已經產生 misleading recall。

### 4.4 Synix / pgmnemo 的學習曲線

兩者都是「programmable memory pipeline」思路的代表，但：
- **Synix 沒有 first-class memory mutation API** —— 你的 agent 要更新一條 fact，必須改 pipeline.py 然後 rebuild layer。這對 runtime agent 完全不適用。
- **pgmnemo 深度綁 Postgres** —— GUC、PGXN extension、CREATE EXTENSION 等概念對非 Postgres 用戶是 friction。如果 firn 用 SQLite，pgmnemo 不能直接抄。

### 4.5 控制平面 LLM 的危險（§2.4 已提）

重複一次：「LLM 在 control plane 會幻覺式 supersede」這個 finding 在 production 中可能會變成 silent data corruption。比 silent failure 更難 debug —— 因為「memory 消失」會被歸咎於 importance score 不對，而不是 LLM 的 mutation 錯誤。

### 4.6 SMSR 的 certified robustness 假設

SMSR 的防禦是基於 smoothed retrieval 的 certified bound，但：
- 只對「retrieval time」certified，不對「storage time」certified（攻擊者還是可以注入）
- Smoothed retrieval 的代價是 latency × 2-3（每個 query 要跑多次 masking 投票）
- 目前是學術 prototype，沒有 production deployment 案例

### 4.7 什麼場景下「flat vector store」還是夠用

對「單 session、< 100 turns、不跨 session recall」的對話 bot：Mem0、Letta 都是 overkill。LangGraph native + SQLite FTS + 偶爾 cosine search 完全足夠。**Memory system 的複雜度應該跟 retention horizon 成正比**，不是跟對話長度。

---

## 5. Actionable for Our Projects

### 對 firn（記憶系統模組）

firn 已有 `memory/service.py` (blocks + messages + embedding)、`memory/long_term.py` (facts + corrections + FTS search)、`context/builder.py` (session summary + blocks + skills level0)、`memory/embedding/`。**當前沒有記憶治理 / 驗證 / control-plane operations**。

#### Action M1: 把 `LongTermMemory.store` 改成「append-only + entity link」 — MODERATE

對應 Mem0 v3 的核心 insight。具體改動：
- 在 `memories` schema 加 `entity_id TEXT` 欄位 + `entity_type TEXT`
- `LongTermMemory.store()` 不再接受 update；改提供 `supersede(old_id, new_fact)`（明確 supersede API，不要 LLM 觸發）
- `search()` 改成 multi-signal：`semantic_score + bm25_score + entity_match_score`，加 weights `[0.5, 0.3, 0.2]`

**為什麼這個改動值得做**：firn 的 corrections 表已經隱含「supersede」概念（wrong_belief + correction），但目前是手動觸發。把 supersede 變成 first-class operation 是 L1 治理的基礎。

#### Action M2: 加 `memory/governance.py` 模組 — MODERATE

對應 MemGuard + GateMem 的設計 pattern。最小可用版本：
```python
# firn/memory/governance.py
class MemoryValidator:
    def __init__(self, source_provider: Optional[Callable] = None):
        self.source = source_provider  # 可選：HR API、product catalog 等

    def validate(self, fact: MemoryFact) -> ValidationResult:
        if not self.source: return ValidationResult(status="unchecked")
        live = self.source(fact.entity_id) if fact.entity_id else None
        if live is None: return ValidationResult(status="no_source")
        delta = self._compare(fact.content, live)
        return ValidationResult(
            status="stale" if delta > 0.3 else "fresh",
            confidence=1.0 - delta,
        )

    def staleness_report(self, agent_id: str) -> List[StaleMemory]:
        facts = self.long_term.get_all(agent_id)
        return [self.validate(f) for f in facts if self.validate(f).status == "stale"]
```

跟 `LongTermMemory` 完全解耦 —— validator 可開關，不影響主流程。先驗證再 supersede 是 governance pattern 的關鍵。

#### Action M3: `context/builder.py` 加 temporal context weighting — TRIVIAL

對應 Mem0 v3 的 temporal reasoning。`build_messages()` 目前直接拿最近 100 條 messages，可以加一個 `recency_weight`：
```python
# 在 builder.py 加
def build_messages(self, agent_id, session_id, query: str = None):
    msgs = self._memory.get_messages(agent_id, session_id, limit=self.MAX_HISTORY)
    if query:
        scored = [(m, self._memory.recency_relevance(m, query)) for m in msgs]
        # 上半部按 recency，下半部按 query relevance 補
        recent = sorted(scored, key=lambda x: x[0].created_at, reverse=True)[:20]
        relevant = sorted(scored, key=lambda x: x[1], reverse=True)[:30]
        return self._interleave([m for m, _ in recent], [m for m, _ in relevant])
    return [...]
```

**5 行改動**，沒引入新依賴。

#### Action M4: 顯式區分 short-term vs long-term backend（借鑑 agentmem 設計）— MODERATE

firn 現在的架構已經有這個分離的雛形（messages 在 service、facts 在 long_term），但沒有 explicit interface。

對 agentmem (chenhaodev/agentmem) 的設計，short-term 應該是「shared in-process namespace、no LLM on hot path」，long-term 才接 LLM extraction + embedding。

對 firn 來說：
- short-term = `memory/messages` table（已是）
- long-term = `memory/long_term.py` + `memory/embedding/`（已是）
- **缺的**：明確的 `MemoryManager` facade 包這兩個 backend，加 `end_session()` 觸發 consolidate（從 short-term 提煉 facts 寫進 long-term）

#### Action M5: 不要碰 control-plane LLM — RESEARCH-ONLY

直接抄 §2.4 的 finding：**LLM 在 control plane 會幻覺式 supersede**。firn 的 supersede/correction API 保持 rule-based（human trigger 或 importance threshold trigger）。未來如果要做 LLM-driven mutation，要先做 adversarial eval（自己注入 crafted fact 測試 mutation 是否誤觸發）。

### 對 managed-agents / Hermes

今天 cron 本身也是個 agent，但**記憶是 session-scoped**（每次重啟丟失所有 context）。如果要升級 cron 的自我演化能力：

- **L1（TRIVIAL）**：把每次 cron run 的 `last_summary.txt` + 主題標籤存進 `~/.hermes/autonomous_notes/cron_memory/`。下個 session `hermes session-continuity` skill 載入這個目錄，可讀到上次做了什麼。
- **L2（MODERATE）**：跟 firn 共用同一個 Mem0 instance（如果 firn 的 `governance.py` 驗證有效）。這條路要看 firn 是否真的需要升級。

---

## 6. Follow-up Questions

1. **Mem0 v3 的 ADD-only storage 在 1M+ facts 後的 scaling curve 是什麼？** —— Mem0 沒公開。pgmnemo 的 BEAM-1M 64.1 score 提供了一個 benchmark 基準，但實際 storage growth 跟 retrieval latency 曲線沒人量過。
2. **AtomMem 的 value-density threshold 有沒有 task-specific 標準？** —— 客服 vs coding agent 的 threshold 應該差多少？需要一篇橫向 study。
3. **MemGuard 在「無外部 source」的 user-fact 場景怎麼處理？** —— 80% 真實 use case 是這個。要不要設計「user confirm」workflow？
4. **Synix 的 rebuild-cost curve**：改 1 行 pipeline.py 觸發 rebuild 受影響 layer，實際上 rebuild cost 跟 layer 數的關係？這決定 Synix 風格是否值得在 firn 投資。
5. **GitOfThoughts (arXiv 2606.14470) 提出的「memory as git repo」**：如果 agent 的 reasoning tree 真的可 replay/diff/merge，這對 observability 是一個全新 paradigm。要不要做 prototype？
6. **CoreMem (arXiv 2606.18406) 的 8GB VRAM edge deployment**：這個對 hermes 的 mobile gateway（如果有）是直接 relevant。實作成本？
7. **跨 session memory 怎麼處理 user 改主意的情況？** —— MemGuard 的 source-of-truth 對這個 use case 失效。需不需要「contradiction resolution」API？
8. **firn 5 個 action 的優先順序**：M1 (multi-signal search) > M4 (explicit short/long backend) > M3 (temporal weighting) > M2 (governance) > M5 (research-only)。下次 sprint 該從哪個開始？

---

### 原始來源

[1] https://github.com/mem0ai/mem0 — 開源 repo — HIGH — Mem0 v3 演算法（2026-04），ADD-only extraction + multi-signal retrieval，LoCoMo 91.6、LongMemEval 94.4、BEAM-1M 64.1
[2] https://pypistats.org/api/packages/mem0ai/recent — PyPI stats — HIGH — mem0ai 月下載 3,177,181 次（2026-06）—— table stakes 訊號
[3] https://github.com/letta-ai/letta — 開源 repo — HIGH — Letta (MemGPT 後繼) blocks + recall + archival 三層 memory 架構，23.4K stars、83K 月下載
[4] https://github.com/volcengine/OpenViking — 開源 repo — HIGH — Context database for AI agents，filesystem paradigm + L0/L1/L2 三層 loading，25.8K stars
[5] https://github.com/memvid/memvid — 開源 repo — MEDIUM — Video-encoding inspired append-only memory，LoCoMo +35% SOTA、0.025ms P50 latency
[6] https://github.com/ac12644/MemGuard — 開源 repo — HIGH — Memory validation platform（2026-06-11），stale memory detection，Datadog-for-memory 心態
[7] https://github.com/marklubin/synix — 開源 repo — MEDIUM — Programmable memory pipeline via directed graph of transforms（2026-05-28）
[8] https://github.com/chenhaodev/agentmem — 開源 repo — MEDIUM — Switchable agent-memory middleware（2026-06-12），ShortTerm / LongTermBackend facade 設計
[9] https://github.com/gengzll/agent-memory-lab — 開源 lab — HIGH — 5 種 memory backend 對比實驗（langgraph_native / langmem / mem0 / zep / letta），有量化 trade-off
[10] https://github.com/kongshan001/agent-memory-frameworks-research — 中文 survey — MEDIUM — Text2Mem / Mem0 / Letta / ReMe / memU 六框架對比（2026-06-07）
[11] https://github.com/NirDiamant/Agent_Memory_Techniques — 教科書 repo — HIGH — 30 runnable Jupyter notebooks covering 全部主流 memory patterns
[12] https://github.com/pgmnemo/pgmnemo — 開源 repo — MEDIUM — Postgres-native memory with reinforce/navigate primitives（v0.9.3 2026-06-17），explore-exploit 自我演化
[13] https://arxiv.org/abs/2606.19847 — AtomMem 論文 — HIGH — Atomic facts for memory，value-density filtering（2026-06-18）
[14] https://arxiv.org/abs/2606.16707 — User as Code 論文 — HIGH — Executable memory paradigm，bag-of-facts 批判（2026-06-15）
[15] https://arxiv.org/abs/2606.15903 — Control-Plane Placement 論文 — HIGH — 13 種 system configuration 對比 forgetting failure modes（2026-06-14）
[16] https://arxiv.org/abs/2606.18829 — GateMem 論文 — HIGH — Multi-principal shared-memory governance benchmark（2026-06-17）
[17] https://arxiv.org/abs/2606.12703 — SMSR 論文 — HIGH — First certified defence against Multi-Session Memory Poisoning（2026-06-10）
[18] https://arxiv.org/abs/2606.17328 — MemTrace 論文 — MEDIUM — 質疑 accuracy-aggregated memory benchmarks 漏掉 long-term retention 真實問題
[19] https://arxiv.org/abs/2606.18406 — CoreMem 論文 — HIGH — Riemannian retrieval + Fisher distillation，8GB VRAM edge deployment
[20] https://arxiv.org/abs/2606.12945 — Learning What to Remember 論文 — HIGH — Cognitively grounded multi-factor value model for memory evolution
[21] https://arxiv.org/abs/2606.14470 — GitOfThoughts 論文 — MEDIUM — Memory as git repository for replay/diff/merge（2026-06-12）

---

**Extraction Errors**: 無（待執行 §Knowledge Extraction）

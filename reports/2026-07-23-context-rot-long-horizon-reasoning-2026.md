# 研究報告：LLM Context Rot 與長時程推理（Long-Horizon Reasoning）
**日期**：2026-07-23
**來源數**：7 | **標籤**：#long-context #context-rot #attention-degradation #long-horizon-reasoning #context-engineering

> 與 2026-07-15 那篇（compaction 治理）互補：本篇專注於「context 變長時，模型本身的行為衰減」與「長時程任務的設計」——而不只是 compaction 後摘要品質的問題。

---

## 1. The Problem

2024–2026 年，主流模型把 context window 從 8K 推到 1M（Gemini 1.5、GPT-4.1），再推到宣稱的 10M（Llama 4）。**但「能塞下」不等於「能用」**。

- Needle in a Haystack（NIAH）是業界唯一被廣泛採用的 long-context benchmark，但它本質是「字面字串檢索」——幾乎所有模型都能拿高分，造成「long context 問題已被解決」的假象。
- 2025 年中，Chroma 發布 *Context Rot: How Increasing Input Tokens Impacts LLM Performance*（Hong, Troynikov, Huber），用 18 個模型、4 個 controlled experiments 系統性地拆解：**當任務複雜度固定、只拉長 input 時，模型表現會以非線性方式惡化**。
- 真正的問題在於：對 agent 來說，context 不是要被「檢索」的字串，而是要被「推理」的世界模型。當 context 拉到 50K–500K tokens、跨越多個 sub-task、跨工具呼叫時，**模型對中段資訊的注意力、對 distractors 的抵抗、對先前結論的回憶能力都會崩塌**——而且各家模型崩塌的位置與方式不同。

誰在解決：
- **Chroma**（向量資料庫公司）—— 提出 Context Rot 框架與評測套件。
- **Subconscious / TIMRUN**（arXiv 2507.16784）—— 用 reasoning trees + KV-cache pruning 突破 context 上限。
- **Anthropic / Jack Hopkins FLE team**—— 用 Factorio Learning Environment 0.3.0 作為長時程實戰基準。
- **Engram / Pu.sh** 等開源社群—— 用外部記憶層 + auto-compaction + checkpoint/resume 在模型外繞過 context 限制。

---

## 2. Core Mechanism

### 2.1 Context Rot：四個 controlled experiments 拆解問題

Chroma 的設計嚴謹之處在於**只改變 input 長度，不改變任務複雜度**——這樣才能把「長 input 造成的衰減」從「任務變難造成的衰減」分離出來。

**Experiment 1：NIAH 變體（Needle-Question Similarity）**

把 needle-question pair 的 embedding cosine similarity 從 0.45 到 0.83 分級，然後改變 haystack 長度（從短到接近每個模型的 context 上限）。結果：

> 當 needle-question 相似度越低，performance 隨 input 長度增加的衰減越快。即使是 Opus 4 / Sonnet 4 / GPT-4.1 / Gemini 2.5 Pro 都無法倖免。

**Experiment 2：Distractors（主題相關的誘餌）**

寫 4 個跟 needle 主題相近但答案不同的 distractors，塞進 haystack。發現：
- baseline（無 distractor）：高分穩定。
- 1 個 distractor：模型表現開始分裂——各家模型對「哪種 distractor 最致命」反應不一。
- 4 個 distractors：衰減更顯著，且不同模型家族出現明顯行為差異。

**Experiment 3：Needle-Haystack Similarity（主題一致性）**

用兩種 haystack：Paul Graham essays 與 arXiv papers。結果發現 needle 跟 haystack 主題越接近，模型有時反而表現更差——直覺相反，但可能來自「模型在主題相近的段落中更容易產生自我混淆」。

**Experiment 4：Haystack Structure（結構）**

保留原順序 vs 隨機打散句子的 haystack。即使總字數相同，打散後表現明顯下降——證明模型對「敘事連貫性」敏感，不只是 token 統計。

**實驗 5（補充）：LongMemEval**

把對話歷史拉到 ~113K tokens，要求模型回答 knowledge update / temporal reasoning / multi-session 類問題。比較 full prompt vs focused prompt（只剩回答問題所需 ~300 tokens）。結果：

```
Claude Opus 4:  focused 接近滿分 → full prompt 明顯下滑
              主因：模型在 ambiguity 下傾向 abstention（拒答）
              「我無法確定日期，因為對話歷史中沒有提供」——其實有提供

GPT / Gemini / Qwen 全家族：相同趨勢，thinking mode 拉近差距但無法消除
```

**實驗 6（補充）：Repeated Words（最單純的任務）**

叫模型重複一段字串，例如 `apple apple ... apples ... apple`（在某個位置插入「apples」）。這是幾乎不需推理的純序列任務。**即便如此：**

- Claude Opus 4 在 ~2500 字後開始「先觀察、再決定是否執行」，有時直接拒絕（2.89%）。
- GPT-4.1 nano 在長序列中產生「Golden Golden」這類不在輸入中的隨機重複詞。
- Gemini 2.5 Pro 在 ~750 字後開始產生 `g.-g/2021/01/20/orange-county...` 這種幻覺式 URL。

**結論（Chroma 原話）：**

> Whether relevant information is present in a model's context is not all that matters; what matters more is **how that information is presented**.

也就是說，**context engineering 不是可有可無的優化，而是核心瓶頸**。

### 2.2 TIM/TIMRUN：用 reasoning trees 突破 context 上限

Subconscious 的 *Beyond Context Limits: Subconscious Threads for Long-Horizon Reasoning* 提出一個關鍵洞察：

> 與其讓 LLM 把所有推理塞進一個 linear context，不如把問題**結構化為 reasoning tree**（任務 → 子任務 → 結論），並用 rule-based subtask pruning 把不再需要的 KV-cache 從 GPU 釋放。

```text
問題：「規劃一個東京 5 日遊，含 2 天迪士尼」
            │
   ┌────────┴────────┐
  查天氣            查迪士尼票務        ← KV cache: 兩者並行執行
   │                  │
   └─────┬────────┘
         │
   結合天氣+票務產生行程              ← pruned：查詢子任務的 KV
         │
   用戶審核 + 修改                    ← pruned：產生前的中間結果
         │
   產出最終行程
```

**關鍵機制：**
- **Working memory** 只保留「與當前節點最相關」的 KV-cache state，而不是全部歷史。
- **Positional embedding 重用**：每個子任務的 reasoning 都可以「重置位置」，避免長序列的位置編碼衰減。
- **效能**：即使操作到 90% 的 KV-cache 仍能維持 throughput；對數學與 multi-hop IR 任務表現精準。

**實際限制：**
- 需要重新訓練模型家族（TIM）以適應 reasoning tree generation。
- 推理引擎（TIMRUN）目前僅在 subconscious.dev 提供 API，未完全開源。
- 對純文字任務效果好，但對需要「保留所有歷史細節」的任務（如完整對話回憶）並非最佳解。

### 2.3 FLE 0.3.0：長時程的真實壓力測試

Jack Hopkins 團隊的 Factorio Learning Environment 是目前最硬核的長時程 agent benchmark——**真實遊戲 + 數小時連續互動 + 需要從錯誤中恢復**。

0.3.0 版（2026 夏季）的關鍵升級：
- **Headless rendering**：移除 Factorio 客戶端依賴，可大規模平行實驗。
- **OpenAI Gym 介面標準化**：方便整合既有 RL / agent 程式碼。
- **Claude Code Plays Factorio**：把 Claude Code 接進 FLE，在 Twitch 直播，展示 frontier agent 在長時程任務中怎麼 debug、backtrack、修設計。

核心發現：**frontier 模型在「需要長時規劃 + 動態修正 + 多小時記憶」的真實任務上仍然掙扎**。即使能完成「打造一座 16 個 iron gear wheel/分鐘」的工廠，從一個錯誤中恢復、設計變體、跨 session 累積經驗——這些都是目前最弱的能力。

### 2.4 業界繞道：Engram + Pu.sh 的「模型外」策略

與其在模型內部解決 context rot，更多實際系統選擇把 context 移到外部：

**Engram**（knowledge graph memory layer）：
- 用 SQLite + 向量搜尋 + knowledge graph 存「長期記憶」。
- 自動 consolidation sleep-cycle：把 episodic memory 蒸餾為 semantic，發現 contradiction，補齊 entity。
- LOCOMO benchmark：80.0%（vs Mem0 66.9%、file-based 28.8%）。
- 每次 query 平均 776 tokens（vs file-based 23,000）。

**Pu.sh**（400 行 shell 的 coding-agent harness）：
- Anthropic + OpenAI 雙支援、7 個 tool、**auto-compaction + checkpoint/resume**。
- 沒有 dependencies，只用 sh + curl + awk（其中 awk 做 JSON parsing 與 tool loop）。
- 92 點 HN——證明 checkpoint + auto-compaction 已成為 production agent 的最低標準。

**關鍵對比：**

| 方案 | 解決的問題 | 代價 |
|---|---|---|
| Chroma context engineering | 模型內的注意力衰減 | 需要 redesign prompt 結構與資訊排序 |
| TIM/TIMRUN reasoning tree | context window 物理上限 | 需專用訓練資料 + 推理引擎 |
| Engram 外部 memory | 長期事實回憶 | 多一層 RAG 延遲 + 一致性維護 |
| Pu.sh auto-compaction | context 成長失控 | 可能丟失未被摘要的細節 |

---

## 3. Why It Matters / Applications

### 對 agent 設計的根本影響

1. **「買更大的 context window」不是解方**——這是 2026 年最重要的觀念翻轉。即使是 10M context 的 Llama 4，Chroma 的實驗也顯示在 ~50K+ tokens 時 attention 就開始非線性衰減。**Agent 架構必須從「把所有東西塞進 context」轉向「把 context 設計為可推理的結構」**。

2. **Agent 評測必須換 benchmark**——NIAH 已死。一個認真的 agent benchmark 必須包含：
   - 多輪對話中的 temporal reasoning
   - 主題相近的 distractor 抵抗
   - 跨 session 的 state recall
   - 真實環境（如 FLE、CivBench）的長時程表現

3. **「Compaction + Checkpoint + External Memory」三件套成為基礎設施**——Pu.sh、Engram、Claude Code、Hermes 等各家 agent 系統幾乎都內建這三件。這不再是「優化」，是「標配」。

4. **TIM 的 reasoning tree 開啟了新典範**——把 LLM 從「序列文字生成器」重新定位為「樹狀結構推理器」，對應到 GPU 記憶體與人類工作記憶的限制。這條路線與 Anthropic 的「extended thinking」、OpenAI 的 o-series reasoning 是平行但不同的方向。

### 對 firn 的具體影響（見 §5）

- firn 的 ConversationAgent 與 TaskAgent 都會遇到長 context 衰減。
- firn 的 cron agent 跨 session 累積記憶需要外部 memory 層。
- firn 的 tool-use 跨多步驟時，distractor 抵抗是關鍵——特別是當使用者對話中夾雜無關訊息時。

---

## 4. Limitations / Honest Assessment

### 4.1 Chroma 研究本身的限制

作者坦承：
- **無法解釋機制**：他們只觀察到現象，沒有做 mechanistic interpretability。無法回答「為什麼中段資訊被忽略」。
- **任務仍偏簡化**：NIAH 變體、LongMemEval、Repeated Words 都比真實 agent 任務簡單；他們預期真實世界的衰減會**更嚴重**。
- **無法隔離「input length」vs「task complexity」**——即使是他們的設計，仍有 confounds（例如 haystack 變長時，模型需跨越更多段落邊界）。

我們的獨立批判：
- **沒有跨模型家族的統一理論**：每家模型行為差異極大，難以歸納出通用原則。
- **沒有提供 fix**：報告只描述問題，不告訴開發者「該怎麼寫 prompt」。後續需要 follow-up 研究。
- **LongMemEval 的清洗**：他們手動過濾 38 個 prompt 留下 306 個——主觀選擇會引入 bias。
- **沒有觸及 reasoning model 的 test-time scaling trade-off**：thinking mode 雖有幫助，但更長的 thinking 會消耗更多 token，反而加劇 context rot。這是他們沒有量化的一個重要維度。

### 4.2 TIM/TIMRUN 的限制

- 商業產品，目前未開源 weights/engine。HN 討論中作者承認「release 時機未定」。
- **只適合結構化任務**：reasoning tree 對「自由對話」「創意寫作」這類任務反而不自然。
- 沒有公開 benchmark 與 Chroma / FLE 直接對比——難以獨立驗證 claim。

### 4.3 FLE 0.3.0 的限制

- **單一環境**：Factorio 是高度結構化的工程任務，跟真實世界的「開放式長時程任務」（如連續幾週的客戶支援、跨月的軟體開發）仍有距離。
- **評測主觀**：成功與否依賴人類對「合理工廠設計」的判斷，難以全自動化。
- 即便是 Claude Code，也仍會在 backtracking 上失敗——**這本身就是研究對象，不是已解決的問題**。

### 4.4 業界繞道方案的權衡

- **Engram 用 Gemini embeddings**——鎖定 Google 服務，且每次 consolidation 都要呼叫 LLM。免費額度有限。
- **Pu.sh 的 awk JSON parser**——聰明但脆弱，遇到 nested JSON 或 edge case 就壞掉。作者自嘲「犧牲尊嚴換可移植性」。
- **Auto-compaction 的取捨**：什麼該保留、什麼該丟？如果沒有 constraint pinning（7/15 那篇報告的重點），compaction 後 agent 可能遺漏關鍵政策。

---

## 5. Actionable for Our Projects

### 5.1 對 firn 的具體改進（按優先級）

| 優先 | 改進 | 模組 | 難度 | 免費方案 |
|---|---|---|---|---|
| **P0** | **Constraint-ware compaction**：compaction 前先用 metadata 標記哪些 message 屬於 policy / tool schema / safety 規則，這些不可被壓縮。呼應 7/15 那篇的 Constraint Pinning | `context/ContextBuilder.py` | MODERATE | 純本地，無 API |
| **P0** | **Position-aware context assembly**：關鍵 instruction 放開頭與結尾（避免「lost in the middle」），相關資訊聚集而非分散。把 tool 結果緊接在發起 tool 的 message 後面 | `context/ContextBuilder.py` | TRIVIAL | 純本地 |
| **P1** | **Distractor resistance test**：在 firn 的測試套件中加入「context 中插入無關但相似的訊息，檢查 agent 是否仍按原計畫執行」——呼應 Chroma Experiment 2 | `tests/agent/` | MODERATE | 純本地 |
| **P1** | **Checkpoint + Resume API**：呼應 Pu.sh 與 7/21 durability report。讓 agent 可以主動 `checkpoint(state)` 並 `resume(checkpoint_id)` | `agents/ConversationAgent.py`、`db.py` | MODERATE | 純本地（SQLite） |
| **P2** | **External memory layer prototype**：參考 Engram 設計 firn 的長期記憶——用本地 SQLite + sentence-transformers embeddings（**全免費**，免 Gemini API）。整合到 conversation 的 system prompt injection | 新模組 `memory/longterm/` | HARD | 用 `all-MiniLM-L6-v2` 等開源模型即可 |
| **P2** | **Reasoning tree prompt pattern**：借鑑 TIM 思路，設計「plan → subtasks → results → synthesize」的四階段 prompt template，雖然不是 GPU 級 KV-cache 優化，但 prompt 層的結構化能部分緩解中段衰減 | `agents/prompts/` | MODERATE | 純 prompt engineering |
| **P3** | **Long-horizon benchmark integration**：在 firn 內建一個「multi-step task with distractions + checkpointing」基準，可與 FLE 0.3.0 類比（但規模縮小，無需 Factorio） | `tests/benchmarks/` | HARD | 純本地 |

### 5.2 對 Hermes 自身的觀察

Hermes 目前也有類似的 context rot 風險——例如 `/research` 指令會把整篇報告塞進 context。我們可以：
- 在 `managed-agents/research/` workflow 中，先把 long reference 做成 summary-only references，只有在被明確 query 時才拉 detail。
- 對 Telegram gateway 的長對話，考慮做對話分頁（每 20 輪主動建議開新 thread）。

### 5.3 不要做的事

- **不要追求更長的 context window 作為單一解方**——即使我們換到 1M context，Chroma 實驗證明仍然會衰減。
- **不要假設 summarizer 保留所有重要資訊**——必須有機械化驗證（呼應 ConstraintRot）。
- **不要在沒有 distractor test 的情況下評估新 prompt 設計**——容易高估效果。

---

## 6. Follow-up Questions

1. **Mechanistic interpretability**：為什麼 attention 在中段衰減？是 positional encoding 邊際效應、attention sink 現象、還是 training distribution mismatch？Chroma 沒回答，這需要更深的 neuroscientific 解釋。
2. **Reasoning model 與 context rot 的交互**：thinking mode 拉近 focused vs full prompt 差距，但它的 cost 是雙倍 token 用量。是否存在「最佳 thinking budget」隨 context length 動態調整的策略？
3. **TIM 的 reasoning tree 是否能用 prompt engineering 部分模擬？** 如果可以，普通開發者用 free API 也能獲得部分好處——值得設計實驗驗證。
4. **External memory 的 consistency 維護**：當 agent 更新一條記憶時，如何確保其他相關條目也同步更新？Engram 的 sleep-cycle consolidation 是目前的 state of the art，但缺乏嚴格的學術評測。
5. **Cross-session 的 identity persistence**：FLE 顯示 frontier 模型在跨 session 累積經驗上仍然失敗。是否需要類似 RL 的 fine-tune loop 而非 prompt engineering？
6. **FLE 0.3.0 vs 真實世界編碼任務**：Claude Code 在 Factorio 上的表現，能否預測它在大型 monorepo 跨週開發的表現？需要更多 empirical data。

---

### 原始來源

1. **Chroma — Context Rot: How Increasing Input Tokens Impacts LLM Performance** — 研究報告 — **HIGH** — 18 個模型 × 4 controlled experiments 的系統性拆解；開源 eval repo（github.com/chroma-core/context-rot）。
2. **Subconscious — Beyond Context Limits: Subconscious Threads for Long-Horizon Reasoning (TIM/TIMRUN)** — arXiv 2507.16784 — **MEDIUM** — 用 reasoning tree + KV-cache pruning 突破 context 上限的商業方案；有 demo API 但未開源 weights。
3. **Daniel Valinsky — LLM Context Rot** — 部落格 — **MEDIUM** — 開發者親身經驗的「context 越用越髒」現象報告；簡短但觀察一致。
4. **Jack Hopkins et al. — Factorio Learning Environment (FLE) 0.3.0** — 開源專案 + 部落格 — **HIGH** — 最硬核的長時程 agent benchmark；HN 749 點 + 0.3.0 release 75 點；展示 frontier model 的真實限制。
5. **Modarressi et al. — NoLiMa: Long-Context Evaluation Beyond Literal Matching** — arXiv 2502.05167 — **HIGH** — Adobe Research 的非字面匹配 long-context 評測，Chroma 引用為先驅工作。
6. **tstockham96 — Engram: Universal memory layer for AI agents** — GitHub repo — **MEDIUM** — 開源 knowledge-graph memory layer；LOCOMO 80% 數字來自作者自述，需獨立驗證但設計合理。
7. **bjesus — Pu.sh: A full coding-agent harness in 400 lines of shell** — 開源專案 + HN 92 點 — **MEDIUM** — 證明 checkpoint + auto-compaction 已成為 production agent 的最低標準；設計透明可學習。

---

**下一個工作日排程執行本指令。**

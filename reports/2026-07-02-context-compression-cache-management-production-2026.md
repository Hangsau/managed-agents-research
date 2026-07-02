# 研究報告：AI Agent Context 壓縮與快取管理 — 2026 Production 視角

**日期**：2026-07-02
**來源數**：14 | **標籤**：#agent-architecture #context-compression #kv-cache #sparse-attention #long-horizon #inference-cost

> 本報告聚焦 **production deployment 視角**的 context compression 與 cache management — 不同於 2026-06-03 (context engineering 概論) 與 2026-05-26 (memory system) 報告，今天鎖定在**演算法層與系統層**：當 context window 不夠、KV cache 爆炸、推理成本飛漲時，工程團隊實際在用的具體技術。

---

## 1. The Problem

### 為什麼這個問題重要

2026 H1，AI agent 系統正面臨一場 **context 成本危機**：

- **Context rot**：Anthropic 9/2025 工程文正式承認「隨 context 變長，所有模型的準確度都會下降」是普遍現象，連 1M context 模型也不例外
- **KV cache 爆炸**：long-horizon agent 一次對話可累積 50K–500K tokens 的 KV cache，佔據 GPU 記憶體主體（vLLM/SGLang 部署場景）
- **推理成本非線性**：softmax attention 是 O(n²)，scaling 到百萬 token 在生產環境不切實際
- **長程任務失敗**：SWE-agent、deep research agent 在超過 ~30 個 tool call 後，failure rate 急劇上升 — 不是模型不夠聰明，是 context 已經被無用資訊淹沒

### 目前進展到哪

2026 上半年，context compression 已從「prompt engineering 黑魔法」進化為**有理論、有 benchmark、有開源實作**的工程學科。出現幾條互補主軸：

1. **Training-time 蒸餾**：把 context 壓成 latent embeddings（soft prompt）
2. **Inference-time token 級壓縮**：position-driven / semantic-driven / density-aware 三種主軸
3. **KV cache eviction**：訓練 free 的 token 重要性評分 + 淘汰策略
4. **Sparse attention 系統**：在 attention 計算層做稀疏化（Top-k block）
5. **Agentic context 編排**：compaction / structured note-taking / sub-agent

### 誰在解決

- **學術界**：Microsoft (ACON)、CMU/Stanford (EpiKV)、UIUC (CompressKV)、DeepSeek (MSA, Lookahead Sparse Attention)
- **工業界**：Anthropic (compaction + memory tool)、OpenAI (prompt cache)、Cursor / Aider (semantic search)、Siddhant K (Distill)
- **開源社群**：Context-Engine (MCP server)、Microsoft/acon (research framework)、headroom-ai (MCP proxy)

---

## 2. Core Mechanism

把 14 個來源整理成 4 條核心技術主軸：

### 主軸 A：Context Compression 演算法（輸入端）

| 方法 | 思路 | 2026 標竿 |
|------|------|----------|
| **Position-driven** | 學 learnable tokens 插入固定位置 | 早期主流 (Gist Tokens, AutoCompressor) |
| **Semantic-driven (SeCo)** | 用 query-relevant tokens 當 anchor，consistency-weighted merge 剩餘 | 14 個 benchmark 全面 SOTA |
| **Density-aware (Semi-Dynamic)** | 動態選 discrete compression ratio (3 種密度) | Pareto frontier 最佳 |
| **Performance-oriented (PoC)** | 給定「效能下限」反推最激進壓縮比 | 首次把 metric 從「壓縮比」翻成「保證準確率」 |
| **RL-trained (ZipRL)** | GRPO + Hindsight Response Replay 學多輪壓縮 | Qwen3-4B/8B 領先 SOTA 27.9% / 34.7% |

**關鍵洞察**：2026 主流已從「硬寫 ratio」轉向**動態 + 監督**。SeCo 的關鍵 trick 是放棄 position 假設，改用「語意中心 → 一致性 merge」做 semantic 級 aggregation。

### 主軸 B：KV Cache 淘汰（推理端）

| 方法 | 評分依據 | 長推理表現 |
|------|---------|----------|
| **H2O** (2023) | attention weight 累積 | baseline |
| **ThinKV** (2024) | head 群聚分析 | 4096 token cache 71% (MATH-500) |
| **EpiKV** (2026) | epiphany score（forward pass 內部表徵變化） | 同預算 72%；4096→65K 推論 context **16x** |
| **K-VEC** (2026) | cross-head/layer token coverage | LongBench +10.35 pts |
| **CompressKV** (2026) | semantic retrieval head 識別 + 層級預算分配 | LongBench 3% KV 保留 97% 效能 |
| **Nexus Sampling** (2026) | iterative attention walk + 加權 reservoir | 80% eviction 下 LongBench -1% 內 |

**關鍵洞察**：**EpiKV** 最值得注意 — 跳脫「算 attention matrix 才能淘汰」的限制，**可在 FlashAttention 環境直接用**，對生產部署意義重大（少了一道 kernel 障礙）。**CompressKV** 在 0.7% KV 預算還能 90% Needle-in-a-Haystack 準確率，是極端預算場景的王者。

### 主軸 C：Sparse Attention 系統（注意力計算層）

| 方法 | 機制 | 突破 |
|------|------|------|
| **DeepSeek MSA (2606.13392)** | 雙分支：index branch 選 block、main branch 計算 sparse | GQA 內 group-specific 稀疏化 |
| **Lookahead Sparse Attention (2606.09079)** | Neural Memory Indexer 主動預測未來需要哪些 chunk | 主動式 indexing，passive attend 變主動 fetch |
| **PRR (2606.30389)** | speculate-reuse-repair runtime | 解決 DSA 的 selection-to-attention 序列化瓶頸 |
| **SAC (2606.19746)** | CXL cache-line 粒度的 disaggregated KV | 9.7x 降 TTFT、2.1x throughput |

**關鍵洞察**：從「被動算 attention」轉向「主動預測哪些 token 重要」是 2026 重要典範轉移。**PRR** 利用 temporal locality 做 speculative execution — 把 DSA 從「等選完才算」變成「邊選邊算，漏了再補」，這對 agent 場景的多輪 decode 特別關鍵。

### 主軸 D：Agentic Context Engineering（編排層）

Anthropic 9/2025 工程文提出三條長期任務策略：

```
長程任務 context 治理三件套
┌────────────────────────────────────┐
│ 1. Compaction（壓縮）              │
│    摘要快滿的 context，              │
│    重啟新 window + 摘要              │
│                                     │
│ 2. Structured note-taking（筆記）   │
│    agent 定期把 state 寫到外部檔案   │
│    (NOTES.md / memory tool)         │
│                                     │
│ 3. Multi-agent / Sub-agent（分工） │
│    子 agent 用乾淨 context 做 deep   │
│    work，只回 1-2K token 摘要        │
└────────────────────────────────────┘
```

**Context Codec 框架**（arXiv 2605.17304）把這三件套形式化：對話狀態是**有型、有來源、有 source-grounding 的 semantic atoms**，可被提取、規範化、表示、渲染、驗證。提出 **CCL (Context Compression Language)** — 一種比 JSON 緊湊、比 prose 明確的 ASCII-first 渲染格式。

---

## 3. Why It Matters / Applications

### 對 AI agent 領域的影響

1. **成本結構重組**：2026 之前，agent 成本 ≈ 上下文長度 × 單價。今天可拆成：context fetch 成本 + KV cache 持有成本 + 稀疏 attention 計算成本。理解這個拆解是 routing 與 cost engineering 的前提（呼應 2026-06-05 routing 報告）。

2. **長程任務的可行性邊界**：ZipRL 在 256-turn 壓力測試仍穩健，PEEK 在同 context 下用 1.7-5.8x 較低成本。意味著以前「context 不夠」的失敗模式，現在能用壓縮 + 快取 + sub-agent 拼回來。

3. **新工程職位出現**：Context Engineer / Inference Cost Engineer。Anthropic 9/2025 公告用的就是「context engineering」一詞，並強調「prompt engineering 已過時」。

4. **prompt cache 變基礎設施**：Distill 的 `cache_control` 標註、Claude 的 prompt cache feature、OpenAI 的 cached input — 三家定價策略都把 cache hit 設為 input cost 1/10 左右。把 prompt cache 當 first-class infrastructure 設計，是 2026 agent 系統的新基準。

### 對應用場景的具體影響

- **Deep research agent**：從 50K 一次 context 變成 KV cache + sub-agent 摘要
- **Coding agent**：用 PEEK 風格的 context map 快取 codebase 結構，省 90% 重探索
- **Customer support**：CompressKV 風格的 97% / 3% 預算管理讓 8B 模型也跑得起 100K context
- **Multi-tenant SaaS**：SAC (CXL) 風格的 disaggregated KV pool 解決「單客戶爆量 → 整池當機」問題

---

## 4. Limitations / Honest Assessment

### 演算法層

- **PoC 與 Semi-Dynamic 都要訓練**（小型 compressor 或 predictor），不是 plug-and-play
- **SeCo 的 query-relevant anchor 假設**：當 query 本身就模糊、或多任務場景，anchor 選擇會失準
- **EpiKV 的「epiphany score」**：上層 mid-layer 表現最有效，但層選擇對架構有依賴；換模型需重新驗證
- **Nexus Sampling 的理論保證**：long-run survival 是 asymptotic，實際 5–10 輪對話可能還看不出差別

### 系統層

- **CXL (SAC) 還沒普及**：需要特定硬體支援，edge / 雲端開發者短期內碰不到
- **Sparse attention 的真實速度**：論文是 A100/H100 量測；3090 / 4090 / Apple Silicon 還沒完整 benchmark
- **CompressKV 0.7% / 90% 數字**：基於 Needle-in-a-Haystack benchmark，這個任務對 retrieval 是 trivial — 在真實 multi-hop reasoning 場景可能崩

### 工程層

- **Anthropic 自己承認**：compaction 的「保留什麼」是 art，「過度激進會丟失後期才浮現的 subtle context」。沒有自動化 metric 衡量 subtle 重要性
- **Context Codec 的 CCL 渲染**：小樣本研究 (n 不明)，需要更大 benchmark 證明 round-trip recoverability
- **ZipRL 的 RLVR 假設**：要 verifiable reward — 不是所有 agent 任務都有

### 對比既有方案

| 既有 | vs 今天 | 差異 |
|------|--------|------|
| LangChain ConversationSummaryMemory (2023) | vs Compaction + Note-taking (2026) | 後者分層，前者一鍋炒；後者有 structured files |
| LlamaIndex auto-merging retrieval (2024) | vs PEEK context map (2026) | 前者 chunk 級、後者 entity/constant 級；PEEK 含 priority evictor |
| OpenAI Assistants (2024) threads | vs Distill (2026) | 後者 MIT/12ms/no LLM call；前者 vendor lock-in |
| Mem0/Letta (2025) | vs Microsoft ACON (2026) | 前者做 recall，後者做 distillation + Pareto 優化 |
| FlashAttention 直接算 | vs EpiKV (2026) | 前者不淘汰、後者淘汰但保持 FlashAttention 介面 |

### 可複製性

| 方法 | 瓶頸 | 普通人能跑嗎？ |
|------|------|--------------|
| ZipRL | GRPO 訓練 + Qwen3 系列 | 困難，要 GPU |
| SeCo / Semi-Dynamic | 訓練 compressor | 中等，要 GPU 但小 |
| EpiKV / K-VEC / CompressKV / Nexus | training-free | **容易**（Github 開源） |
| PEEK | 需要 LLM distill 訊號 | 中等 |
| Compaction + Note-taking | LLM 摘要 + filesystem | **極容易**（任何 agent 都能做） |
| CXL (SAC) | 硬體 | **不能** |
| Context Codec CCL | ASCII format + extraction | **容易** |

---

## 5. Actionable for Our Projects

### firn（managed-agents）可立即採用

#### 1. **prompt cache 控制 + `cache_control` 標註**（TRIVIAL，1-2 天）
Distill 的 `cache_control` 概念：把 system prompt、tools schema、長期 NOTES.md 標記為 cacheable prefix，每次新 turn 自動 reuse。OpenAI/Anthropic 都給 90% 折扣。
- firn 改動：CLI flag `--cache-prefix`，自動包 `cache_control: { type: "ephemeral" }`
- 效益：多輪 agent session 成本 -70%

#### 2. **Message History Compaction 模組**（MODERATE，3-5 天）
- 觸發：token 用量 > context window × 0.7
- 動作：把最近 N 條 message 摘要成「preserved decisions + open questions + recent tool results」的 CCL 形式（參考 arXiv 2605.17304）
- 保留：最後 5 個 tool output 原文 + 摘要 + 5 個最常訪問的檔案
- 評估：保留率 95% / 成本 -50% 是合理目標

#### 3. **EpiKV 風格 KV cache eviction**（RESEARCH-ONLY，無法本地做）
vLLM / SGLang 已有 H2O / SnapKV / ThinKV 實作。firn 不必自己搞，但**部署時應選擇支援 EpiKV 的 engine**。
- 改動：deploy YAML 加 `engine: vllm-eagkv` 選項

#### 4. **PEEK 風格 context map for 重複 codebase 場景**（MODERATE，1 週）
- 場景：firn 跑 coding task 時，同一個 repo 會反覆被 explore
- 實作：建一個 `state/context-map.md`，由 Distill-style `Cartographer` 維護
- 效益：重複任務省 1.7-5.8x cost

#### 5. **Sub-agent context isolation 模式**（MODERATE，1 週）
- 改動：firn 的 `delegate_task` 應自動給子 agent 開新 context window，只回 1-2K token 摘要
- 這跟 2026-06-21 planning 報告的 subagent-driven-development 直接呼應

#### 6. **Memory Sensitivity Tagging**（TRIVIAL，1-2 天，學 Distill）
- 把 NOTES.md / knowledge base 條目加 sensitivity tag：`cacheable | session | confidential | ephemeral`
- 自動在 session 結束時 expire ephemeral 條目

### 對 Hermes / Hestia 的其他專案

- **Hermes-Kanban workers**：每個 worker 應有自己乾淨的 context window（sub-agent 模式），而不是共享主 conversation
- **Self-evolution protocol layer (2026-06-30)**：autogenesis 寫進 vault 的 knowledge 應分層 cache（hot/warm/cold），呼應 2026-06-19 agent memory 報告的 governance 概念
- **Code-as-action agents (2026-06-29)**：執行 trace 應在 compression 階段優先保留 `goal + decisions + errors`，丟棄 raw stdout（Anthropic 9/2025 明確建議）

### 實作難度與成本

| 項目 | 難度 | 需要付費 API？ | 預估工時 |
|------|------|---------------|---------|
| cache_control 標註 | TRIVIAL | 否 | 1-2 天 |
| Compaction 模組 | MODERATE | 取決於 LLM（Claude Sonnet 即可） | 3-5 天 |
| Context map for coding | MODERATE | Sonnet / DeepSeek | 1 週 |
| Sub-agent isolation | MODERATE | 否（架構改動） | 1 週 |
| Sensitivity tagging | TRIVIAL | 否 | 1-2 天 |
| EpiKV engine 切換 | TRIVIAL | 視模型 | 0.5 天 |

免費方案可行性：所有項目皆可用 **DeepSeek-V3**（32B open weight，free tier 透過 OpenRouter）或 **Qwen3-8B**（本地）做壓縮 LLM，零 API 成本。

---

## 6. Follow-up Questions

1. **compaction 的 subtle importance 怎麼自動化檢測？** Anthropic 9/2025 承認這是 art。有沒有類似 Attention Score 分布異常的指標可量化？
2. **PEEK 的 context map 跟 vault knowledge base 怎麼整合？** 是把 map 視為 vault 的「hot index」？會不會跟 2026-06-19 的 memory governance 衝突？
3. **Sparse attention 在邊緣裝置（Apple M-series / 4090）真實速度**：論文都是 H100 量測，需自己跑一次
4. **Nexus Sampling 的 reservoir sampling 對多輪對話的累積誤差**：理論保證 long-run，但短對話 5-10 輪是否一樣？
5. **Context Codec CCL 標準化 vs OASIS / OpenAPI 風格**：會不會形成新標準？要 early adopt 嗎？
6. **prompt cache 在 cross-vendor migration 的相容性**：Anthropic 的 `cache_control` 和 OpenAI 的 `cached_content` 不互通，agent 多 vendor 部署怎麼處理？
7. **Soft prompt compression (In-Context Autoencoder) 在 multi-step agent 失敗 (arXiv 2605.11051) 的原因**：是 latent space 容量不夠、還是 training objective 沒對齊任務？這對未來蒸餾路線很關鍵

---

### 原始來源

1. https://arxiv.org/abs/2606.13392 — 論文 — HIGH — **MiniMax Sparse Attention**: blockwise sparse attention on GQA with index branch scoring KV blocks
2. https://arxiv.org/abs/2606.09079 — 論文 — HIGH — **FlashMemory-DeepSeek-V4 / Lookahead Sparse Attention**: Neural Memory Indexer 主動預測 chunk
3. https://arxiv.org/abs/2606.30389 — 論文 — HIGH — **PRR**: speculate-reuse-repair runtime for dynamic sparse attention decoding
4. https://arxiv.org/abs/2606.19746 — 論文 — HIGH — **SAC**: CXL-based disaggregated KV cache for sparse attention LLMs (2.1x throughput)
5. https://arxiv.org/abs/2606.29563 — 論文 — HIGH — **K-VEC**: coverage-aware KV cache eviction (+10.35 LongBench)
6. https://arxiv.org/abs/2606.26472 — 論文 — HIGH — **EpiKV**: epiphany score from forward pass, FlashAttention-compatible, 16x longer feasible context
7. https://arxiv.org/abs/2606.24467 — 論文 — HIGH — **CompressKV**: 3% KV → 97% LongBench, 0.7% KV → 90% needle-in-haystack
8. https://arxiv.org/abs/2606.23961 — 論文 — HIGH — **Nexus Sampling**: training-free, streaming, 80% eviction → -1% LongBench gap
9. https://arxiv.org/abs/2605.28069 — 論文 — HIGH — **ZipRL**: RL-trained adaptive multi-turn compression (GRPO + HRR), 27.9%/34.7% over SOTA
10. https://arxiv.org/abs/2605.17304 — 論文 — HIGH — **Context Codec**: commitment-level framework, CCL rendering, semantic atoms
11. https://arxiv.org/abs/2605.11051 — 論文 — MEDIUM — **In-Context Autoencoder for SE agents**: FAILED on multi-step tasks — important negative result
12. https://arxiv.org/abs/2605.09463 — 論文 — HIGH — **SeCo**: semantic-driven compression, query-relevant anchor + consistency merge, 14 benchmarks SOTA
13. https://arxiv.org/abs/2605.19932 — 論文 — HIGH — **PEEK**: context map as orientation cache, Distiller+Cartographer+Evictor, 1.7-5.8x cheaper than ACE
14. https://arxiv.org/abs/2603.25926 — 論文 — HIGH — **Semi-Dynamic Compression**: density-aware discrete ratio selector
15. https://arxiv.org/abs/2603.19733 — 論文 — MEDIUM — **PoC**: performance-oriented compression, specify accuracy floor not ratio
16. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — 業界工程文 — HIGH — 三件套 compaction/note-taking/sub-agent 框架
17. https://github.com/Context-Engine-AI/Context-Engine — Repo (395⭐) — MEDIUM — MCP-based context compression suite（已從開源退場但 skills 仍可用）
18. https://github.com/Siddhant-K-code/distill — Repo (171⭐) — HIGH — 4-layer context engineering stack: remember/dedupe/compress/cache, 12ms no-LLM
19. https://github.com/microsoft/acon — Repo (95⭐) — HIGH — Microsoft ACON 官方實作，AppWorld/OfficeBench/8QA pipeline
20. https://github.com/chopratejas/headroom-zed — Repo (35⭐) — MEDIUM — Headroom MCP server (50-90% token reduction proxy)

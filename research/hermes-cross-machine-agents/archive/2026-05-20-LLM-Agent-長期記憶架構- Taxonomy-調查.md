# 探索：LLM Agent 長期記憶架構 — 2026-05-20

**延續自**: [[2026-05-19-agent-memory-architecture]]

## 資料來源

### 1. arXiv 2603.07670 — Memory for Autonomous LLM Agents (2026-03)

**核心貢獻**：提出 agent memory 的 **write-manage-read loop** 框架，耦合於感知與行動。

**三維 Taxonomy**：
1. **Temporal scope** — 短期/中期/長期記憶
2. **Representational substrate** — 儲存載體（embedding、KB、graph、policy weights）
3. **Control policy** — 如何決定寫入、檢索、遺忘

**五種 Mechanism Families**：
| Family | 描述 | 對應 Hermes 現有？ |
|--------|------|-------------------|
| Context-resident compression | 將資訊壓入 context window（e.g., RAG summary） | ⚠️ 部分（memory-consolidator 做了這步）|
| Retrieval-augmented stores | external memory + query retrieval | ✅ FTS5 index |
| Reflective self-improvement | agent 回顧自身行為並改進（類似 experience replay）| ❌ 缺失 |
| Hierarchical virtual context | 多層虛擬 context（工作記憶→場景記憶→長期）| ❌ 缺失 |
| Policy-learned management | 用 learned policy 決定什麼要記 | ❌ 缺失 |

**四個 Evaluation Benchmarks 分析**：
- 靜態 recall benchmark → 多 session agentic test
- 暴露「固執缺口」：current systems 在 memory+decision-making interleaving 表現仍差

**五大 Open Challenges**（與前期筆記的「缺口」高度對應）：
1. **Continual consolidation** — 持續整合新記憶、壓縮、歸檔
2. **Causally grounded retrieval** — 依因果關係檢索，而非 keyword/similarity
3. **Trustworthy reflection** — reflective self-improvement 的可信度（不要讓 agent 自我安慰）
4. **Learned forgetting** — 主動遺忘機制（Hermes 的 ISSUES.md suppression 就是一種）
5. **Multimodal embodied memory** — 感測器/視覺/動作的時間序列記憶

## Hermes 啟發

### 現有架構對照

前期筆記已列出：
| 層次 | 實作 | 現況 |
|------|------|------|
| 短期 | session context | ✅ |
| 中期 | heartbeat_state.json, memory-consolidator | ✅ |
| 長期 | Obsidian vault + FTS5 | ⚠️ FTS5 做完，ML training 未開始 |

**新增對照（五種 Mechanism Families）**：
- `Context-resident compression` — `memory-consolidator` 正在做這件事
- `Retrieval-augmented stores` — `hermes-fts5-doc-index` 提案已實作
- `Reflective self-improvement` — **完全缺失**，心跳的 `heartbeat_learning.py` 只是統計 pattern extraction，不是真正的 reflection
- `Hierarchical virtual context` — 部分缺失，只有兩層（session + vault）
- `Policy-learned management` — **完全缺失**，目前是 rules-based (ISSUES.md suppression)

### 最有價值的 insight

**Continual consolidation** 和 **Learned forgetting** 這兩個 challenge 最值得實作：

1. **Continual consolidation** → 目前 vault 是手動 ingest + cron consolidate。該論文指出真正有效的 consolidation 需要「因果關係追蹤」，而不只是「按時間戳打包」。這可能是 `hermes-consolidation-step` 提案的下一個階段。

2. **Learned forgetting** → Hermes 已有 `ISSUES.md` 的 known-issue suppression（相當於 explicit forgetting），但沒有 **learned/metric-driven forgetting**（根據存取頻率、相關性動態丟棄）。如果引入簡單的 access-count + recency 衰減，或許能減少 vault size 膨脹。

### Aegis Memory 仍未讀
前期筆記的 lead：`https://github.com/quantifylabs/aegis-memory`。今日從 arXiv survey 得知「policy-learned management」機制，與 Aegis 的 core claim 高度相關。下次探索可順藤摸瓜。

## 跨文章 Synthesis

兩日探索合起來：

- **Day 1**（前期筆記）：Memorization architecture 三大方向（Aegis 選什麼、Mnemora 不經 LLM 的 CRUD、DPM append-only log）
- **Day 2**（本筆記）：arXiv survey 的五大家族 + 五個 open challenges，填補了「缺失哪些机制」的空白

**核心缺口收斂**：
前期筆記問：「selective memory + append-only log + alerting 三者結合的實際系統長什麼樣子？」
→ 答案在 **Policy-learned management + Reflective self-improvement** 這兩個 families，但這兩者 Hermes 仍完全缺失。

**下一步建議**（非本輪任務，純記錄）：
- 評估 `heartbeat_learning.py` 是否可以升級為真正的 reflective self-improvement
- 研究 Learned forgetting 的 simple metric（access-count based）可行性

## 未追蹤 Leads

- https://github.com/quantifylabs/aegis-memory
- https://arxiv.org/abs/2605.13486 (R²-Mem)
- https://github.com/mnemora-db/mnemora

## ✅ 本次探索完成
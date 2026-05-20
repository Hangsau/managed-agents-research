# 探索：Aegis Memory — 2026-05-20

**延續自**: [[2026-05-20-agent-memory-taxonomy-survey]]

## 資料來源

### 1. GitHub — quantifylabs/aegis-memory

**Core claim**: Secure context engineering for production AI agents. 第一個同時做到 content security + integrity verification + trust hierarchy + ACE loop 的 memory layer。

## Per-Source Insight

### 為何領先

其他 memory layer（mem0、Zep、Letta）只做「儲存」，Aegis 做「安全地把 context 當攻擊面來工程化」：

| 能力 | mem0 | Zep | Letta | Aegis |
|------|------|-----|-------|-------|
| Content injection detection | — | — | — | ✅ 4-stage |
| HMAC-SHA256 integrity | — | — | — | ✅ |
| OWASP trust hierarchy | — | — | — | ✅ 4-tier |
| ACE loop | — | — | — | ✅ auto-vote + reflection |
| Contradiction detection | — | partial | — | ✅ typed edge + resolution API |
| Hybrid retrieval | BM25+entity | keyword+graph | RRF | ✅ pgvector+tsvector+RRF |
| Multi-agent ACL | — | — | — | ✅ scope-aware |

### ACE Loop — 真正的 self-improvement

`heartbeat_learning.py` 號稱在做这件事，但只是統計 pattern extraction。Aegis 的實現：

```
Generation → Execution (tracked memories) → Reflection (auto on failure) → Curation (promote/flag/consolidate)
```

**關鍵差異**：
- **Auto-voting**：completion 時 `success=True` → 自動在所有用過的 memories 上 vote `helpful`；失敗 → vote `harmful` + 建立 reflection memory（含 error context）
- **Run tracking**：第一等的 `ace_runs` table，把 memories 連結到 task outcomes
- **Typed contradiction edge**：兩個 memory 矛盾時，不是刪除或忽略，而是建立 `contradicts` typed edge，附 confidence + rationale，可 audit、可 metric

### ISSUES.md 的下一個階段

Hermes 的 known-issue suppression 已有「explicit forgetting」。但 **contradiction detection** 的概念更強：
- 不是「看過就記住」，而是「當新聲稱與舊記憶矛盾時，建立審計追蹤」
- 這解決了 `ISSUES.md` 的「靜態 known issue list」問題——新引入的變更可能與舊有假設矛盾，但沒有系統自動 catch

### Deployment footprint

- PostgreSQL 16 + pgvector（不可刪）
- Docker Compose
- 8 vCPU / 7.6 GB RAM  benchmark
- p50 query: 282ms（吃 OpenAI embedding latency）

**不適合即时 adopt**（operational complexity 高），但**概念可直接內化**。

## Hermes 啟發

### 可抄襲的設計

1. **ACE loop 核心概念**：把 `heartbeat_learning.py` 的簡單 pattern extraction 升級為「completion → 自動投票 → reflection memory」的循環
2. **Contradiction tracking for ISSUES.md**：當新的 known issue 被新增時，檢查是否與舊有 ISSUES.md 的 root cause 假設衝突
3. **Hybrid retrieval**：Hermes 的 FTS5 已是 dense+sparse fusion，可研究加入 RRF（Reciprocal Rank Fusion）提升 entity/filepath 命中率

### 不適合直接 adopt 的

- 完整 PostgreSQL + pgvector 部署（太重）
- 4-tier OWASP trust hierarchy（需要完整的 agent identity system，Hermes 尚無）

## 未追蹤 Leads

- https://github.com/quantifylabs/aegis-memory (本文已覆蓋)
- https://arxiv.org/abs/2605.13486 (R²-Mem)
- https://github.com/mnemora-db/mnemora

## ✅ 本次探索完成
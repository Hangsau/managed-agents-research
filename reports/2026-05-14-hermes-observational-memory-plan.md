# Observational Memory Layer (OBS-001) 實作計畫

> **For Hermes:** 實作時參照本計畫，逐任務進行。

**Goal:** 讓 Hermes 從每個 session 中自動萃取離散事實（atomic facts），補足記憶系統第五層——observational memory。

## Audit Summary

現有四層記憶 ＋ 一個缺口：

| Layer | 機制 | 類型 | 觸發 |
|-------|------|------|------|
| 1 | context-distiller (4h) | episodic — 「那次做了什麼」 | cron |
| 2 | extract_learning.py | procedural — 「怎麼 debug X」 | manual |
| 3 | consolidate_memory (12h) | thematic — 「五篇都指向同一個洞」 | cron |
| 4 | briefing.py (12h) | feedback — 把 Layer 3 灌回 context | cron |
| **5** | **MISSING** | **observational — 「這件事告訴我什麼」** | — |

**目前事實全靠手動 `memory` 工具存**——踩坑才記，沒踩漏掉。

## Architecture

```
每個 session → context-distiller (每4h) 
  → 現有流程 (facts/skills/vault)
  → extract_facts.py (新) → ~/.hermes/knowledge/facts.jsonl
  → briefing.py (修改) → 取高信心新事實 → consolidation_briefing.md
```

## Schema

```jsonl
{"fact": "string", "category": "technical|environment|preference|pitfall|domain",
 "confidence": "high|medium|low", "source": "session_id|note_path",
 "fingerprint": ["kw1","kw2"], "source_date": "YYYY-MM-DD",
 "added": "ISO8601"}
```

## Tasks

| # | 做什麼 | 範圍 | 試算 |
|---|--------|------|------|
| obs.2 | 寫 `extract_facts.py` — 從 session JSON 萃取離散事實，寫入 JSONL，Jaccard > 0.6 去重 | ~150 行 | 10m |
| obs.3 | 擴充 `briefing.py` — 從 facts.jsonl 取最近 7 天高信心新事實（≤3 條）附加到 briefing 底部 | ~20 行修改 | 3m |
| obs.4 | 修改 context-distiller cron → 跑完後順便跑 `extract_facts.py` | 改 prompt | 1m |
| obs.5 | 驗證 — 跑一次完整的 distiller + extract + briefing 迴圈 | — | 3m |

## Non-goals

- 不做 pattern detection（多 session 間的 pattern finder）— 那是 OBS-002
- 不新增獨立 cron job — 掛在現有 distiller 上
- 不碰現有 extract_learning.py — 那是 manual trigger，不同使用情境

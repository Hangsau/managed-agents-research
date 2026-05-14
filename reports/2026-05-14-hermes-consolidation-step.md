# 提案：Hermes Consolidation Step — 把 raw notes 消化成 cross-cutting insight

**日期**: 2026-05-14 | **來源**: [[2026-05-14-post-vector-agent-memory]], [[2026-05-14-beads-agent-memory]] | **類型**: SPIKE

**摘要**: Hermes 的 autonomous_notes 已經是 memory system 的「raw ingestion」層（13 篇筆記，持續成長）。但缺少 Google Always On 的 ConsolidateAgent、Beads 的 compaction、Agent Flywheel 的 CM——那個「週期性消化舊記憶、找出跨主題連結、生成新 insight」的步驟。這個 SPIKE 用現有基礎設施（session_search + autonomous_notes）寫一個 prototype consolidation cron job，評估產出品質。

**為什麼現在做**:
- 兩個獨立探索（post-vector agent memory + beads）都指向同一個缺口
- 三個外部系統獨立收斂到同一個設計：Google Always On（ConsolidateAgent）、Beads（compaction）、Agent Flywheel（CM + CASS → insights）
- Hermes 已經有全部 input（13 篇 autonomous_notes、session_search、proposals/），只缺消化邏輯

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🟡 SPIKE 已設計 |
| **階段** | SPIKE → 實作 → 測試 → 部署 |
| **目前階段** | SPIKE 完成 |
| **最後行動** | 05-14: ConsolidateAgent 設計完成 |
| **下一步** | 實作 consolidation cron job |
| **阻擋** | 無 |
| **關聯** | WS-004 |
- 飛輪效應缺最後一個齒輪：raw notes → structured insight → 驅動下一個探索/proposal

**預估成本**:
- 時間：~1-2 小時 SPIKE（讀 skill 參考 → 設計 prompt → 寫 cron script → 試跑一次 → 評估產出）
- 風險：極低。只產一個新 note + 一個 cron script，不改任何現有行為
- LLM cost：每次 consolidation 約 1-2 次 LLM call（讀 5 篇 notes + 最近 sessions → 產 insight），可控

**Spike 要做什麼**:
1. 設計 consolidation prompt：輸入 = 最近 N 篇 autonomous_notes + 最近 session 摘要（用 session_search），輸出 = cross-cutting insight note
2. 寫 `~/.hermes/scripts/consolidate_memory.py` — 讀 note、call LLM、產 insight note 到 `autonomous_notes/`
3. 試跑一次（拿 beads + post-vector + contextforge 三篇，看能串出什麼）
4. 評估產出品質：insight 是新穎的還是廢話？跨度夠不夠？有沒有可行動的 next step？
5. 如果品質好 → 排進 cron（maybe 每 6-12 小時）；如果品質差 → 分析為什麼，記錄教訓

**前提**: 
- session_search 的召回品質是否夠好當 consolidation 輸入 → SPIKE 內驗證
- consolidation prompt 設計需要迭代 — 第一次可能不會太好

**潛在問題**:
- Consolidation 產出的 insight 可能太泛、太 obvious（「agent memory 很重要」這種廢話）
- LLM 可能過度樂觀地抓到假關聯（apophenia）
- 如果 autonomous_notes 主題太分散，consolidation 可能串不出有意義的連結
- 需要定義「好 insight」的標準，否則無法評估品質

**成功標準**:
- 產出的 insight note 包含至少一個**非顯然的跨主題連結**（不是兩個筆記都在說同一件事）
- 產出的 insight 包含至少一個**可行動的 next step**（新探索方向、新提案、具體建議）
- 不是單純的 summary——是 synthesis

**→ 如果 SPIKE 成功**，下一步是：
- 定期排程 consolidation（cron）
- Consolidation output 自動餵進 heartbeat 探索選單（閉環飛輪）
- 長期：compaction/decay（舊 insight 被新 insight 取代）

## 狀態更新 (2026-05-14)

**STATUS: PARTIAL** — Extraction 層已完成（`context-distiller` skill v1.0.0 做 session review + vault ingest），但核心的 synthesis/cross-cutting insight 生成仍未實作。

- ✅ 讀取 autonomous_notes + session 的 plumbing → `context-distiller` 已涵蓋
- ✅ Vault ingest（產出到 daily/、research/）→ `context-distiller` Phase 2-3
- ❌ Cross-cutting insight 生成（「兩篇不相干的筆記之間的連結」）→ 未實作
- ❌ `consolidate_memory.py` → 不存在
- ❌ Consolidation output 自動餵進 heartbeat 探索選單 → 未接上

殘餘價值：`context-distiller` 已經把 input 層準備好了。下一步只需要寫 synthesis prompt + 一個輕量 cron script，難度比原提案低很多。

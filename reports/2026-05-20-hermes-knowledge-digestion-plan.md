# Hermes 知識消化系統建置计划

**日期**: 2026-05-20
**Slug**: knowledge-digestion-system
**作者**: Talos
**狀態**: 草稿

---

## 目標

建立持續運作的知識消化管線，改變現有「研究輸入 > raw storage」但幾乎不消化的失衡狀態。

**具體目標**：
- 每日自動蒸餾 research vault 產出結構化洞察
- 每個 session 根據 context 主動 inject 相關消化過的事實
- 知識磨損速度（rot）低於累積速度

---

## 現況

### 已有但未充分利用的工具

| 工具 | 現狀 | 問題 |
|---|---|---|
| `consolidate_memory.py` | 存在但几乎不跑 | 沒有 cron trigger |
| `context-distiller` skill | 有但用的人少 | 需要 session hook |
| `briefing.py` (L3) | session 開始時被動觸發 | 只給現況，沒有消化過的知識 |
| `session_search` | 靠關鍵字，無結構 | 找不到過去的判斷邏輯 |

### 輸入負擔

- `managed-agents/reports/`: 43 個報告，8 天內產出
- `obsidian-vault/research/`: 94 個檔案，872K
- 總 vault: 807 檔案，7.1M

### 根本問題

- consolidation 沒有高優先級的 cron job
- 沒有「事實萃取」機制，只有「筆記摘要」
- L1/L2/L3 三層記憶分工明確，但中間環節（L2 consolidation）几乎不運作

---

## 規劃方案：B + A 混合

**B**（Observational Memory）作為骨幹——萃取離散事實而非摘要全文。
**A**（定期蒸餾）作為觸發機制——每日 12h 跑一次，不漏接新輸入。

---

## 執行計畫

### Phase 1：建立事實萃取標準（1-2 天）

**目標**：定義「Observation」格式，讓 consolidate 有結構可循。

**產出格式** (`~/.hermes/observations/`):
```yaml
# 格式：YYYY-MM-DD-{source}-{id}.yaml
source: managed-agents/reports/2026-05-14-hermes-consolidation-synthesis.md
date: 2026-05-14
tags: [memory, architecture, consolidation]
content: |
  發現：file-based memory 已成產業共識，但 consolidation layer 普遍缺失。
  影響：Hermes 缺少消化環節，知識在庫裡增長但沒有被組織。
  状态: confirmed  # confirmed / hypothesis / challenged
```

**步驟**：
1. 建立 `~/.hermes/observations/` 目錄結構
2. 定義 `observation.schema.yaml`（用於 validation）
3. 對現有 3 篇核心報告（consolidation-synthesis, multi-agent-coordination, meta-agent-supervision）做一次性的事實萃取

**驗證**：`observation.schema.yaml` 存在，萃取產出 ≥20 observations。

---

### Phase 2：讓 consolidation cron 真的在跑（1 天）

**目標**：設定每日 12h cron，把新的研究報告蒸餾成 observations。

**改動**：
- 修改 `consolidate_memory.py`：同時做蒸餾（非僅壓縮）
- 新增 cron job：`hermes-daily-consolidation`，每 12h 觸發

**邏輯**：
1. 檢查 `managed-agents/reports/` 和 `vault/research/` 中的新檔案（last modified > 上次執行時間）
2. 對每個新檔案萃取 1-3 個 Observation
3. 寫入 `~/.hermes/observations/`
4. 同時更新 `vault/learnings/` 中的每日digest

**驗證**：`cronjob list` 顯示 `hermes-daily-consolidation` status=active，觀察第一次執行有產出。

---

### Phase 3：Session 注入掛鉤（2-3 天）

**目標**：每個 session 開始時，根據上下文 inject 相關 observations。

**改動**：
- 修改 `run.py` session 初始化的部分，加入 observation injection step
- 建立 `context-matching`：根據 session 的 project context 找相關 observations

**邏輯**：
1. session 啟動時，讀取 `~/.hermes/observations/` 中與目前 project/tags 相關的 observations
2. 限制 inject 不超過 5 條，避免 context overflow
3. injection 格式用「💡 已知事實」前綴，區分於新資訊

**驗證**：
- 新 session 開始時，觀察到相關 observations 出現在 system prompt 中
- 驗證 observation injection 不影響 session 啟動速度（<3s）

---

### Phase 4：消化品質監控（持續）

**目標**：確保 observations 有价值，淘汰無效內容。

**機制**：
- 每週一次 `hermes-observational-prune` cron：刪除 `status: stale` 超過 14 天的 observations
- 人工抽樣：每週一檢查過去 7 天新 observations 品質（抽 10 條 review）
- tag 追蹤：觀察哪些 tags 增長最快，識別過度關注的領域

---

## 檔案變動清單

| 檔案 | 動作 |
|---|---|
| `~/.hermes/observations/` | 新建目錄 |
| `~/.hermes/observations/schema.yaml` | 新建（Phase 1） |
| `~/.hermes/scripts/consolidate_memory.py` | 修改（Phase 2） |
| `run.py` | 修改（Phase 3） |
| `~/.hermes/profiles/talos/skills/automation/context-distiller/SKILL.md` | 修改（Phase 3） |
| `cron job: hermes-daily-consolidation` | 新建（Phase 2） |
| `cron job: hermes-observational-prune` | 新建（Phase 4） |

---

## 驗證標準

- Phase 1 完成時：≥20 observations，schema validation pass
- Phase 2 完成時：cron job running，過去 24h 新報告已蒸餾
- Phase 3 完成時：session 啟動 inject 相關 observations，使用者感受到「系統記得我過去的發現」
- Phase 4 完成時：prune cron 存在，stale observations <5%

---

## 風險與 Tradeoffs

**風險 1**：observation injection 可能稀釋 session context
- 緩解：限制每 session ≤5 條，觀察使用者反饋

**風險 2**：consolidation cron 變成另一個「看起來在跑但沒人看的」系統
- 緩解：Phase 4 的品質抽樣機制

**風險 3**：觀測事實標準定義困難，可能變成另一種 raw notes
- 緩解：Phase 1 先做一次性萃取，从实际经验中定義 schema

---

## Open Questions

1. **Observation 的顆粒度**：一篇文章萃取 1-3 個 vs 5-10 個？太多則失去重點，太少則漏掉洞察。
2. **Observation 生命週期**：confirmed 的事實是否應該永久保留？還是有時效性？
3. **與 Hestia 的協作**：誰負責蒸餾？Talos cron 跑的 consolidation 結果要如何讓 Hestia 看到？

---

## Timeline

- **Week 1**：Phase 1 + Phase 2（consolidation cron 跑起來）
- **Week 2**：Phase 3（session injection）
- **Week 3+**：Phase 4 + 實際使用中調整

---

*本計劃將依使用者回饋調整方向。*
---

## Independent Plan Review

> **Reviewed by**: Talos (second-pass critique, plan-review skill v1.0.0)
> **Date**: 2026-05-20

### Overall Assessment: 🟡 Needs Work

**Raw Score: 63/100**

**Summary**: 計劃方向正確，B+A 混合策略符合實際需求。結構完整（Phase 1-4 遞進合理），但操作顆粒度不夠——Step 描述是原則性說明而非可執行指令。Phase 3 的 context-matching 機制完全沒有實作細節。缺乏錯誤處理和 rollback 機制，Phase 2 cron 的持久化狀態管理（追蹤「上次執行時間」）也未定義。

---

### Dimension Scores

| Dimension | Score | Issue Count |
|-----------|-------|-------------|
| Completeness | 🟡 Needs Work | 3 |
| Correctness | 🟢 Pass | 1 |
| Coherence | 🟢 Pass | 0 |
| Robustness | 🟡 Needs Work | 2 |
| Efficiency | 🟡 Needs Work | 1 |
| Spec Alignment | 🟢 Pass | 0 |

---

### Critical Issues (must fix before execution)

**1. [Completeness] — Phase 1 步驟顆粒度不夠，無法直接交給 subagent 執行**
- Phase 1 步驟 1：「建立 `~/.hermes/observations/` 目錄結構」——未說明子目錄、初始 `README.md`、權限
- 步驟 2：「定義 `observation.schema.yaml`」——只給了 YAML 範例格式，schema 本身沒有具體欄位定義
- 步驟 3：「一次性萃取 3 篇報告」——未說明萃取的 prompt 是什麼、誰來執行
- **Fix**: Phase 1 增加具體的 mkdir 命令、schema 欄位定義（至少 6 個必填欄位）、萃取 prompt 草稿
- **Affected**: Phase 1, 整體假設

**2. [Completeness] — Phase 2 cron 缺少持久化狀態管理**
- 「檢查新檔案（last modified > 上次執行時間）」——`上次執行時間`存在哪？
- 第一次跑時如何處理全部歷史檔案（8 天 43 個報告是否全部萃取？）
- **Fix**: 明確狀態存儲位置（如 `~/.hermes/state/last_consolidation.txt`），並定義 initial run 的邏輯
- **Affected**: Phase 2 cron job 邏輯

**3. [Robustness] — Phase 2/3 所有修改都沒有 rollback 機制**
- `consolidate_memory.py` 的修改如果破壞現有功能，沒有恢復步驟
- `run.py` 的 injection step 如果造成 context overflow，無快速關閉開關
- **Fix**: 增加 `.bak` 備份步驟；`run.py` injection 增加 `OBSERVATION_INJECTION=enabled` 環境變量開關

---

### Recommendations (improve but don't block)

**1. [Efficiency] — Phase 3 context-matching 機制完全空缺**
- 「根據 session 的 project context 找相關 observations」——如何判斷相關性？
- 建議：先用簡單的 tag intersection，不做 embedding similarity（成本太高）

**2. [Completeness] — Phase 2 cron 的觸發時間應更明確**
- 「每 12h」——具體 cron expression 建議 `0 */12 * * *`（00:00 和 12:00）

**3. [Robustness] — Consolidation 失敗的 error handling**
- 建議：增加 `~/.hermes/logs/consolidation.log`，failure 寫入並 alert

---

### Revised by Plan Author

- [ ] Critical Issue 1 addressed: Phase 1 增加具體命令、schema 欄位定義、萃取 prompt 草稿
- [ ] Critical Issue 2 addressed: 定義 `~/.hermes/state/last_consolidation.txt` 位置及 initial run 邏輯
- [ ] [Critical Issue 3 - deferred]: Phase 2/3 實作時一併處理 backup + feature flag
- [ ] Recommendation 1: Phase 3 補充「tag intersection」機制說明
- [ ] Recommendation 2: 明確 cron expression 為 `0 */12 * * *`
- [ ] Recommendation 3: Consolidation log 寫入 Phase 2 實作細節

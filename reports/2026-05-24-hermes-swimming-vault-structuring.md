# Plan: 游泳 vault 結構化與 skill 規劃

> **日期：** 2026-05-24
> **規劃者：** Hestia
> **目標：** 將 `swimming/technique/` 從流水帳式散文重構為可檢索條目系統，並規劃 swimming-vault skill

---

## 1. 現況分析

### 1.1 現有檔案

| 檔案 | 行數 | 問題 |
|------|------|------|
| `四式技術動作.md` | 1151 行 | 流水帳式散文；標題層級混用（`###` vs `##`）；無交叉參照；不可標題檢索 |
| `教學誤區-自由式.md` | 701 行 | 有條目化傾向，但仍是長段落敘述 |
| `教學誤區-蝶式.md` | 398 行 | 同上 |
| `教學誤區-仰式.md` | 250 行 | 有結構，但深度不足 |
| `教學誤區-蛙式.md` | 222 行 | 同上 |
| `教學誤區-水下蝶腳.md` | 217 行 | 同上 |
| `教學誤區-出發與轉身.md` | 331 行 | 同上 |

### 1.2 核心問題

1. **`四式技術動作.md` 是最大瓶頸** — 1151 行是骨幹，但不可檢索。skill 要找「蝶式划手掉力」，得線性掃描全文，效率和精確度都差。
2. **沒有索引層** — technique/ 之間無 cross-reference map，無法快速定位相關檔案。
3. **無關鍵字 extraction** — 每篇檔案沒有統一的 tags/block IDs，RAG 層無法精確召回。
4. **仰泳/蛙泳動作分解空白** — 這兩個泳式只有教學誤區，沒有類似自由式的「動作分解骨幹檔案」。

### 1.3 約束條件

- 全程使用 **Free LLM APIs only**（MiniMax M2.7 / DeepSeek）
- 全程使用 **中文**（整合層）
- vault 最終要能支援 RAG → API → 網站 架構

---

## 2. 目標狀態

### 2.1 結構化後的 vault 標的

```
swimming/technique/
├── 四式技術動作.md              ← 重構：條目化 + 交叉參照
├── 四式技術動作-索引.md          ← 新增：MOC 索引頁（可跳轉）
├── 動作分解-自由式.md           ← 新增：髖/肩驅動 + 六階段划手 + 踢水（從四式技術動作.md 抽出）
├── 動作分解-仰式.md             ← 新增：仰泳動作分解（目前空白）
├── 動作分解-蛙式.md             ← 新增：蛙泳動作分解（目前空白）
├── 動作分解-蝶式.md             ← 新增：從蝶式誤區抽出骨幹
├── 教學誤區-自由式.md           ← 保持
├── 教學誤區-蝶式.md             ← 保持
├── 教學誤區-仰式.md             ← 保持
├── 教學誤區-蛙式.md             ← 保持
├── 教學誤區-水下蝶腳.md          ← 保持
├── 教學誤區-出發與轉身.md        ← 保持
└── TAG-INDEX.md                 ← 新增：關鍵字 → 檔案/段落對照表
```

### 2.2 skill 標的

`swimming-vault` skill：
- **輸入：** 自然語言 query（例如「蝶式划手掉力怎麼修」）
- **邏輯：** 解析 query → 在 vault 中搜尋相關檔案 → 抓相關段落 → return structured content
- **輸出格式：** `[{file, section, content, score}, ...]`
- **用途：** 供外部 API/RAG 系統調用，或 Hestia 直接使用

---

## 3. 執行路徑

### Phase 1：重構骨幹（四式技術動作.md）

**目標：** 將 1151 行流水帳重構為條目化、交叉參照、可檢索的結構。

**步驟：**

1. **分析現有內容結構**
   - 讀完 `四式技術動作.md` 全文（1151 行）
   - 識別所有 `##` / `###` 標題，建立 outline
   - 識別每個技術論點的邊界（哪段講什麼）

2. **重新組織為雙層結構**
   - **Layer 1（概覽）：** 每個泳式一頁 `動作分解-{泳式}.md`，包含：動作階段分解、關鍵技術點、錯誤模式
   - **Layer 2（細節）：** `四式技術動作.md` 變成維基式條目索引，each `##` 是一個可獨立引用的技術條目

3. **加上 block IDs 和交叉參照**
   - 每個技術條目加上 `^block-id`（Obsidian wikilink 錨點）
   - 技術條目之間用 `[[wikilink]]` 交叉參照
   - 例如：「高肘捕水」條目 reference `[[四式技術動作#^evf-physics]]`

4. **驗證**
   - 確認每個 query 場景（「划手掉力」「換氣時機」「滾轉不足」）都能在 3 次點擊內找到答案
   - 確認 skill 可以用標題+block ID 而非線性掃描召回內容

**檔案變更：**
- `swimming/technique/四式技術動作.md` — 重構（保留核心內容，重新組織結構）
- `swimming/technique/動作分解-自由式.md` — 新增（從四式技術動作.md 抽出自由式部分）
- `swimming/technique/動作分解-蝶式.md` — 新增（從四式技術動作.md 抽出蝶式部分）
- `swimming/technique/動作分解-仰式.md` — 新增（新建）
- `swimming/technique/動作分解-蛙式.md` — 新增（新建）

### Phase 2：建立索引層

**目標：** 建立 MOC + TAG-INDEX，讓人和 skill 都能快速定位內容。

**步驟：**

1. **建立 `四式技術動作-索引.md`（MOC）**
   - 包含所有 technique/ 檔案的目錄
   - 每個檔案：標題、版本、核心主題、關鍵字清單
   - 以泳式分類，附上快速跳轉連結

2. **建立 `TAG-INDEX.md`**
   - 格式：`tag: {相關檔案} | {相關 section} | {摘要}`
   - 主要 tag：髖驅動/肩驅動、高肘、划手、踢水、換氣、滾轉、出發、轉身、水下蝶腳
   - 每個 tag 至少 3 個相關檔案/段落

3. **驗證**
   - 確認 MOC 能在 10 秒內讓人找到任意技術主題
   - 確認 TAG-INDEX 能讓 skill 用 keyword matching 找到相關檔案

**檔案變更：**
- `swimming/technique/四式技術動作-索引.md` — 新增
- `swimming/technique/TAG-INDEX.md` — 新增

### Phase 3：swimming-vault skill

**目標：** 建立可被外部 API 調用的 retrieval skill。

**步驟：**

1. **規劃 skill 介面**
   - Input: `{query: string, scope?: string[]}`
   - Process: keyword extraction → vault search (using TAG-INDEX) → fetch relevant sections → rank by relevance
   - Output: `[{file, section, block_id, content, relevance_score}, ...]`

2. **實作 retrieval 邏輯（pseudo-code）**
   ```
   1. Parse query → extract keywords
   2. Search TAG-INDEX.md for matching tags
   3. Retrieve candidate files from TAG-INDEX
   4. For each candidate file, extract relevant sections (using block IDs)
   5. Score by: keyword match density, 確定性標記, recency
   6. Return top-K results (K=3 to 5)
   ```

3. **建立技能文件**
   - `swimming-vault/SKILL.md` — 完整的 skill specification
   - 包含觸發條件、輸入格式、輸出格式、fallback logic

4. **驗證**
   - 測試 5+ 個 query 場景，確認召回內容相關且準確
   - 確認 skill output 可被下游 API 直接使用

**檔案變更：**
- `~/.hermes/skills/swimming-vault/SKILL.md` — 新增

---

## 4. 執行順序

```
Phase 1 → Phase 2 → Phase 3
（骨幹重構 → 索引建立 → skill 實作）
```

**每個 Phase 內的任務順序：**
- Phase 1：先分析結構，再重構自由式（最大、最複雜），再擴展到其他三式
- Phase 2：在 Phase 1 完成後再做（依賴重構後的結構）
- Phase 3：最後做（依賴 Phase 1+2 的成果）

---

## 5. 預期風險

| 風險 | 影響 | 預案 |
|------|------|------|
| 重構後內容遺漏 | P0 | 每個 Phase 結尾做「完整性 check list」，對照原檔案所有論點 |
| 重構破壞現有引用關係 | P1 | 任何搬動都伴隨 cross-reference update，不留 dangling link |
| skill 召回品質不足 | P2 | 第一版先做簡單 keyword matching，不強求 semantic search |
| 仰泳/蛙泳動作分解需要新文獻 | P1 | Phase 1 的「新建」改為「留白並標注 P1 文獻需求」，不阻塞 skill 建置 |

---

## 6. 驗證清單

### Phase 1 完成的條件
- [ ] `四式技術動作.md` 的每個 `##` 標題都有明確邊界，可獨立引用
- [ ] 所有自由式內容已抽出至 `動作分解-自由式.md`
- [ ] 所有蝶式內容已抽出至 `動作分解-蝶式.md`
- [ ] `動作分解-仰式.md` 和 `動作分解-蛙式.md` 已建立（有內容或標注缺口）
- [ ] 所有技術論點都有 `^block-id`
- [ ] 所有檔案間引用已更新為 wikilink

### Phase 2 完成的條件
- [ ] `四式技術動作-索引.md` 包含所有 7+ 個檔案的首頁資訊
- [ ] `TAG-INDEX.md` 每個主要 tag 有 3+ 個檔案關聯
- [ ] MOC 能在 10 秒內定位任意技術主題

### Phase 3 完成的條件
- [ ] `swimming-vault` skill 可正常 load
- [ ] 測試 query：「蝶式划手掉力怎麼修」→ 返回相關檔案 + 段落
- [ ] 測試 query：「高肘怎麼做」→ 返回技術論點 + 引用來源

---

## 7. 整體檢視

**這個 plan 在做什麼：** 將游泳 vault 從「深度散文文件」升級為「可結構化檢索的知識庫」，並建立對應的 skill 接口。

**有沒有更快的做法：** 
- 如果只需要做 Phase 3（skill），可以跳過 Phase 1/2，直接在現有 vault 上做 keyword search。但召回品質會很差，skill 上線後使用者體驗爛。

**scope 外：**
- 不做網站、API、或實際的對外服務
- 不翻譯新的 RAW 文獻（現有文獻先消化完再說）
- 不做 semantic search / embedding（那是 Phase 3 之後的優化，不是起點）

---

## Independent Plan Review

> Reviewed by: plan-review skill v1.0.0

### Overall Assessment: 🟡 Needs Work

**Raw Score:** 68/100

**Summary:** Plan 方向正確，phase 劃分合理，但 Phase 1 的「分析 + 重構」具體步驟不夠細——沒有明確說明如何將 1151 行流水帳轉換為條目化結構。Phase 3 的 skill 介面規格也不夠完整，缺少 error handling 和 edge cases。

---

### Dimension Scores

| Dimension | Score | Issue Count |
|-----------|-------|-------------|
| Completeness | 🟡 | 2 |
| Correctness | 🟡 | 2 |
| Coherence | 🟢 | 0 |
| Robustness | 🟡 | 2 |
| Efficiency | 🟢 | 0 |
| Spec Alignment | 🟢 | 0 |

---

### Critical Issues (must fix before execution)

1. **[Completeness] — Phase 1 步驟不夠具體，無法直接執行** (ref: Phase 1 步驟 1-3)
   → **Fix:** 細化 Step 1（分析現有結構）的 output 為一份獨立的「現狀 outline 文件」，明列所有現有 `##` 標題、層級、內容邊界。Step 2（重構）需要明確說明「哪些內容去哪些檔案」。
   → **Affected tasks:** Phase 1 全部

2. **[Correctness] — Phase 3 skill 介面規格缺少 input validation 和 error handling** (ref: Phase 3 步驟 2)
   → **Fix:** 在 skill 介面規格中加上：query 長度限制、空 query fallback、no-match fallback、timeout logic。
   → **Affected tasks:** Phase 3 步驟 2

---

### Recommendations (improve but don't block)

1. **[Completeness] — Phase 2 的 TAG-INDEX 格式應該先定義好再開始建**  
   建議在 Phase 2 開始前，先定義 `TAG-INDEX.md` 的 output format，包含：tag 名稱格式（英文駝峰？中文？）、每個 entry 最少需要幾個欄位（file, section, block_id, summary）。

2. **[Robustness] — Phase 1 的「完整性 check list」需要具體化**  
   「對照原檔案所有論點」太模糊——建議改成：Phase 1 完成後，確認每個原始 `##` 標題的內容都有出現在新結構中（至少 95% 覆蓋率）。

3. **[Robustness] — 沒有提到 wikilink 更新的技術細節**  
   重構後 cross-reference 會大量改變——建議在 Phase 1 末尾加一個「wikilink audit」步驟：搜尋所有 `[[...]]` 確認無 dangling reference。

---

### Revised by Plan Author

- [ ] Critical Issue 1 addressed: Phase 1 將細化為「分析 output 清單 + 重構 mapping 表」
- [ ] Critical Issue 2 addressed: Phase 3 將補足 input validation 和 error handling 規格
- [ ] Recommendation 1: TAG-INDEX format 將在 Phase 2 開始前明確定義
- [ ] Recommendation 2: Phase 1 將加入「95% 覆蓋率驗證」具體方法
- [ ] Recommendation 3: Phase 1 末尾將加入「wikilink audit」步驟
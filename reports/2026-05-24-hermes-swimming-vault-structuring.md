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

---

**Step 1：產出「現狀 outline」文件**

- 讀完 `四式技術動作.md` 全文（1151 行）
- 產出 `swimming/technique/_outline-current.md`（臨時檔案，完成後刪除），格式：

```markdown
## 自由式區塊
### 1.1 物理框架：沒有唯一最優技術
  - 起點：line 14
  - 終點：line 20（下一個 ### 之前）
  - 核心論點：推進結構 + 速度公式 SR×SL
  - 狀態：✅ 完整
  
### 1.2 三種技術風格：距離與生理條件的投影
  - 起點：line 24
  - 終點：line 48
  - 核心論點：Hip-driven / Shoulder-driven / Hybrid 三風格對比表
  - 狀態：✅ 完整

...（以此類推，覆蓋全部 ## 和 ### 標題）
```

- 這個檔案是過渡品，用完即刪。它的目的是讓重構時有「對照原點」。

---

**Step 2：產出「重構 mapping 表」**

根據 Step 1 的 outline，產出 `swimming/technique/_重构-mapping.md`（臨時檔案）：

```markdown
## 自由式 → 動作分解-自由式.md
| 原標題 | 內容摘要 | 去哪裡 |
|--------|----------|--------|
| 1.1 物理框架 | 推進結構 + SR×SL 公式 | 動作分解-自由式.md §1 |
| 1.2 三種技術風格 | Hip/Shoulder/Hybrid | 動作分解-自由式.md §2 |
| 1.3 六階段划手 | 六階段分析表 | 動作分解-自由式.md §3（保留在四式技術動作.md 作為條目引用） |

## 蝶式 → 動作分解-蝶式.md
...

## 四式技術動作.md 重構原則
- 原本的「泳式內流水帳」→ 拆出去，成為獨立的 動作分解-{泳式}.md
- 四式技術動作.md 的內容 → 改為「技術條目索引」，each ## = 一個可獨立引用的 block
- 每個 block 加 `^block-id`，格式：`^freestyle-physics`、`^freestyle-stroke-cycle`
```

---

**Step 3：執行重構（按 mapping 表）**

- 新增 `動作分解-自由式.md`（從四式技術動作.md 抽出自由式相關內容）
- 新增 `動作分解-蝶式.md`（從四式技術動作.md 抽出蝶式相關內容）
- 新增 `動作分解-仰式.md`（新建，標注 P1 文獻需求：仰泳動作分解待補）
- 新增 `動作分解-蛙式.md`（新建，標注 P1 文獻需求：蛙泳動作分解待補）
- 重構 `四式技術動作.md`：移除已抽出內容，替換為 wikilink 指向對應的 動作分解-{泳式}.md

---

**Step 4：加 block IDs + 交叉參照**

- 每個技術條目加上 `^block-id`（格式：`^{泳式}-{概念}`，例如 `^freestyle-evf`）
- 技術條目之間用 `[[wikilink]]` 交叉參照
- 例：`高肘捕水` 條目 → `參見：[[動作分解-自由式#^freestyle-evf]]`

---

**Step 5：Wikilink audit（收尾）**

- 搜尋所有 `[[...]]`，確認無 dangling reference
- 確認每個 `[[...]]` 都指向實際存在的檔案或 block

---

**Step 6：95% 覆蓋率驗證**

- 對照 Step 1 產出的 outline，確認每個原始 ## 的內容都有出現在新結構中
- 允許 5% 誤差（某些過渡性段落自然消失是可以的）
- 若低於 95%，回頭補上

---

**檔案變更：**
- `swimming/technique/_outline-current.md` — 新增（臨時，Step 6 後刪除）
- `swimming/technique/_重构-mapping.md` — 新增（臨時，Step 6 後刪除）
- `swimming/technique/四式技術動作.md` — 重構（內容替換為條目索引）
- `swimming/technique/動作分解-自由式.md` — 新增
- `swimming/technique/動作分解-蝶式.md` — 新增
- `swimming/technique/動作分解-仰式.md` — 新增（標注 P1 缺口）
- `swimming/technique/動作分解-蛙式.md` — 新增（標注 P1 缺口）

### Phase 2：建立索引層

**目標：** 建立 MOC + TAG-INDEX，讓人和 skill 都能快速定位內容。

---

**Step 0（先於 Step 1）：定義 TAG-INDEX.md 格式**

在開始建立索引之前，先定義好 output format：

```markdown
# TAG-INDEX

格式：`tag_name | file | section | block_id | summary`

## 命名規範
- Tag 名称：英文 camelCase（例：`hipDrive`, `evfCatch`, `breatheTiming`）
- 每個 tag 至少關聯 3 個檔案/段落
- Block ID 格式：`^{泳式}-{概念}`（例：`^freestyle-evf`）

## 確定性標記權重（用於 skill scoring）
- 🟢 近期文獻（2009–2025）：權重 1.0
- 🟡 有效舊文獻（1990–2008）：權重 0.8
- 🟠 教練觀測：權重 0.6
- 🔵 物理推導：權重 0.5
- 🔴 未查證假設：權重 0.3

## Entry 範例
```
hipDrive | 動作分解-自由式.md | §2 三種技術風格 | ^freestyle-hip-drive | Hip-driven 髖部驅動：低划頻（50–75次/分），髖旋轉幅度 45–60°，適合長距離

evfCatch | 四式技術動作.md | §1.3 六階段划手 | ^freestyle-evf | 高肘捕水（EVF）：手掌是主推進面，上臂保持與游進方向平行以最小化阻力

breatheTiming | 教學誤區-自由式.md | §換氣時機 | ^freestyle-breathe-timing | 換氣時頭部不應抬起，應靠眼球角度解決，頭部本身不移動
```

---

**Step 1：建立 `四式技術動作-索引.md`（MOC）**
**Step 1：建立 `四式技術動作-索引.md`（MOC）**

- 包含所有 technique/ 檔案的目錄
- 每個檔案：標題、版本、核心主題、關鍵字清單
- 以泳式分類，附上快速跳轉連結

**Step 2：建立 `TAG-INDEX.md`**

- 按照 Step 0 定義的格式建立
- 主要 tag 清單：髖驅動/肩驅動、高肘、划手、踢水、換氣、滾轉、出發、轉身、水下蝶腳、推進力、速度公式
- 每個 tag 至少 3 個相關檔案/段落
- 由 Phase 1 的 block ID 匯入（Phase 1 完成後才有 stable block IDs）

**Step 3：驗證**

- 確認 MOC 能在 10 秒內讓人找到任意技術主題
- 確認 TAG-INDEX 能讓 skill 用 keyword matching 找到相關檔案（不需 semantic search）

**檔案變更：**
- `swimming/technique/四式技術動作-索引.md` — 新增
- `swimming/technique/TAG-INDEX.md` — 新增

### Phase 3：swimming-vault skill

**目標：** 建立可被外部 API 調用的 retrieval skill。

---

**Step 1：定義 skill 介面規格**

```yaml
name: swimming-vault
description: 自然語言搜尋游泳 vault，回傳相關技術檔案與段落

trigger:
  - 使用者問技術問題（「蝶式划手掉力怎麼修」）
  - 外部 API 調用（傳入 query string）

input:
  type: object
  fields:
    query:
      type: string
      required: true
      constraints:
        - min_length: 2
        - max_length: 500
        - 空白或 null → return {error: "empty_query"}
    scope:
      type: string[]
      required: false
      default: 所有 technique/ 檔案
      description: 要搜尋的檔案範圍（可指定特定泳式）

process:
  1. 解析 query → 提取 keywords（停用詞過濾、小寫正規化）
  2. 搜尋 TAG-INDEX.md，找到 matching tags
  3. 從 TAG-INDEX 取出候選檔案列表（去重）
  4. 若有 scope filter，只保留 scope 內的檔案
  5. 對每個候選檔案，用標題 + block ID 召回相關 section
  6. Relevance scoring：keyword match density × 確定性標記權重 × 檔案新舊
  7. Return top-K results（K=5，max=10）

output:
  type: object
  fields:
    query: 原 query（echo）
    results: array of result objects
    count: number of results
    error: string | null（若無錯誤則為 null）

result_object:
  file: 檔案路徑（相對於 vault root）
  section: 所在章節標題
  block_id: block ID（如有）
  content: 召回的段落內容（完整句子，最多 500 字）
  relevance_score: float（0-1，1 為最高）
  確定性標記: 🟢/🟡/🟠/🔵/🔴

error_handling:
  - empty_query → {error: "empty_query", results: [], count: 0}
  - no_match → {error: null, results: [], count: 0, message: "無相關內容，請擴充關鍵字"}
  - vault_not_found → {error: "vault_path_not_found", results: [], count: 0}
  - read_timeout → {error: "read_timeout", results: [], count: 0}
  - max_results_exceeded → 截斷並附加 warning
```

---

**Step 2：實作 retrieval 邏輯（pseudo-code）**

```
function swimming_vault_search(query, scope=None):
    # Input validation
    if not query or len(query.strip()) < 2:
        return {"error": "empty_query", "results": [], "count": 0}
    
    if len(query) > 500:
        query = query[:500]  # 截斷，不報錯
    
    # Keyword extraction
    keywords = extract_keywords(query)  # 移除停用詞，取詞幹
    
    # Search TAG-INDEX
    tag_matches = search_tag_index(keywords)
    if not tag_matches:
        return {"error": null, "results": [], "count": 0, 
                "message": "無相關內容，請擴充關鍵字"}
    
    # Gather candidate files
    candidate_files = list(set([tag["file"] for tag in tag_matches]))
    
    # Apply scope filter if specified
    if scope:
        candidate_files = [f for f in candidate_files if f in scope]
    
    # Retrieve and score sections
    results = []
    for file in candidate_files:
        sections = retrieve_sections(file, tag_matches)
        for section in sections:
            score = calculate_relevance(section, keywords, tag_matches)
            results.append({**section, "relevance_score": score})
    
    # Sort and limit
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    results = results[:10]  # max 10
    
    return {
        "query": query,
        "results": results,
        "count": len(results),
        "error": null
    }
```

---

**Step 3：建立技能文件**

- `~/.hermes/skills/swimming-vault/SKILL.md` — 完整的 skill specification
- 包含觸發條件、輸入格式、輸出格式、fallback logic、測試案例

---

**Step 4：驗證**

- 測試 query：「蝶式划手掉力怎麼修」→ 返回相關檔案 + 段落
- 測試 query：「高肘怎麼做」→ 返回技術論點 + 引用來源
- 測試 empty query → 正確 error response
- 測試 no-match query → 正確空结果 + message
- 確認 skill output 可被下游 API 直接使用（JSON parse）

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

- [x] Critical Issue 1 addressed: Phase 1 細化為「Step 1 outline → Step 2 mapping → Step 3 重構 → Step 4 block ID → Step 5 audit → Step 6 驗證」，每步 output 明確定義
- [x] Critical Issue 2 addressed: Phase 3 補足 input validation（min/max length, empty/null handling）和 error handling（5 種 error case各有對應 response）
- [x] Recommendation 1: TAG-INDEX format 在 Phase 2 Step 0 先定義（命名規範、權重、entry 範例），再開始建
- [x] Recommendation 2: Phase 1 Step 6 改為「95% 覆蓋率驗證」，有具體方法（對照 outline）
- [x] Recommendation 3: Phase 1 Step 5 加入「Wikilink audit」步驟
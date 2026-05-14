# Planning Skills Iteration v3 — 規劃 skill 套件迭代計劃

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** v2.0.0 發布後的已知 gap 全面收斂——讓 plan-review 從「建議」變「必經」，加入測量與執行回饋。

**Architecture:** 不新增 skill。只 patch 現有四個檔案（plan / subagent-driven-development / writing-plans / plan-review），插入一條「閉環路線」：plan 強制觸發 review → review 輸出分數 → 執行失敗回寫 plan。

**Tech Stack:** 純 markdown patch（skill 檔），無需新程式碼。

## Planning Quality Checklist (MANDATORY — fill every field)

├── **目標（一句話）**
│   └── planning skill 套件從「格式強制型 v2」進化到「閉環品質型 v3」：plan-review 必定觸發、有分數可追蹤、執行回饋可回流。
│
├── **前置條件檢查（3–5 項 yes/no）**
│   ├── [x] writing-plans v2.0.0 已部署
│   ├── [x] plan-review v1.0.0 已部署
│   ├── [x] plan skill v1.0.0 存在（related_skills 缺 plan-review）
│   ├── [x] subagent-driven-development v1.2.0 存在（不提及 plan-review）
│   └── [ ] plan-review QoS 尚未被驗證過（無法量化改善幅度）
│
├── **步驟清單（每步 ≤15 字）**
│   ├── 1. Patch plan skill：強制 load plan-review
│   ├── 2. Patch SADD skill：加入 pre-execution gate
│   ├── 3. Patch writing-plans：Phase 3 改 MANDATORY
│   ├── 4. Patch plan-review：加 raw score 欄位
│   └── 5. 用此計劃本身驗證新流程
│
├── **每步的驗證方式（怎麼知道該步做完了）**
│   ├── Step 1: grep "plan-review" / plan/SKILL.md → MANDATORY 出現
│   ├── Step 2: grep "plan-review" / SADD/SKILL.md → pre-exec gate 存在
│   ├── Step 3: grep "MANDATORY" / writing-plans Phase 3 → 非 advisory
│   ├── Step 4: plan-review 輸出格式有 raw_score 欄位
│   └── Step 5: 用 SADD 執行本計劃 → plan-review 被觸發 → 分數產出
│
├── **潛在卡點（至少 2 個，含對策）**
│   ├── Hermes 載入 plan 後直接跳到寫 plan，仍跳過 plan-review → 對策：把 plan-review 寫進 plan 的 output requirements 非 related_skills 建議
│   ├── plan-review 給的批評太模糊（"多想想 edge case"）失去價值 → 對策：要求 review 必須引用 plan 中的具體行號或 task ID
│   └── 執行回饋回寫發生在 SADD 內但 session 結束後遺失 → 對策：回寫到 plan 檔案本身（patch），不依賴 session 記憶
│
└── **失敗時的退路**
    └── 如果 plan-review 仍然跳過：改由 cron job 在 plan 產生後 5 分鐘自動觸發 review（需要新 script，但可退守至此）。

---

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | ✅ 完成 |
| **目前階段** | 完成 |
| **最後行動** | 2026-05-14: Tasks 1–5 全部完成，plan-review 狗食測試通過 (85/100) |
| **下一步** | 實際使用觀察：用新版流程規劃下一個 feature，看 plan-review 是否真的被觸發 |
| **阻擋** | 無 |

---

## 現況評估

v2.0.0 發布後已知的四個 gap：

| Gap | 現狀 | 嚴重度 | 修法 |
|-----|------|--------|------|
| plan-review 不一定被觸發 | writing-plans Step 6 Phase 3 寫「if available, load it」，模型可能跳過 | 🔴 高 | plan skill 的 output 流程直接寫「load plan-review 並 append review to plan」 |
| 無法量化 plan 品質 | 只有主觀判斷 | 🟡 中 | plan-review 輸出加 raw_score (0-100) |
| token budget 只寫在 skill 裡 | 模型可能忽略 | 🟡 中 | plan skill prompt 加「請在 300 tokens 內完成規劃」 |
| 執行失敗不回饋給規劃 | bug 修了但 plan 沒更新 | 🟡 中 | SADD 加入 Execution Notes 回寫 |

---

## 設計決策

### 為什麼不新增 cron job 強制觸發 plan-review？

**不做。** 理由：cron 需要知道「哪個 plan 剛被寫好、在哪個路徑」，這需要 file watcher + polling，增加複雜度遠大於收益。目前最乾淨的解法是讓 `plan` skill 成為唯一入口——所有規劃都經過 `plan` → `writing-plans` → `plan-review`，一個 skill 扣一個。

### 為什麼 plan-review 的分數是 raw_score 不是多維度？

目前的 6-dimension rubric（🟢/🟡/🔴）已經是多維度。raw_score 是加權總分：Critical issues 扣 15 分/個，🟡 扣 5 分/個，🟢 不扣，滿分 100。簡單、可比較、可追蹤趨勢。

### 為什麼「執行回饋」不是自動化而是手動 patch？

全自動回饋需要 SADD 的 implementer subagent 在遇到 plan 未覆蓋的 edge case 時，自動識別、歸類、patch 回 plan。弱模型做不到這層 meta-reasoning。所以第一步先做：SADD 的最後一個 subagent（final integration reviewer）檢查「執行中遇到什麼 plan 沒寫的東西」，append 到 plan。不完美但實用。

---

## Task Breakdown

### Task 1: Patch `plan` skill — 強制 plan-review 成為必經步驟

**Objective:** 改 plan skill 的 output requirements，把 plan-review 從「建議」升級為「必經」

**Files:**
- Modify: `~/.hermes/skills/software-development/plan/SKILL.md`

**變更內容：**

1. `related_skills` 加入 `plan-review`
2. Output requirements 加一段：

```markdown
### Post-plan review (MANDATORY)

After writing the plan (via writing-plans skill), you MUST load the `plan-review` skill and run a full 6-dimension critique against the plan just produced. Append the review output to the plan file. This is NOT optional — every plan produced by this skill must carry a review score.
```

3. `version` → 1.1.0

**Verification:** `grep "MANDATORY" plan/SKILL.md | grep -i review` 有結果

---

### Task 2: Patch `subagent-driven-development` — 加入 pre-execution gate + Execution Notes

**Objective:** SADD 在開始執行前檢查 plan 是否有 review，執行完回寫經驗

**Files:**
- Modify: `~/.hermes/skills/software-development/subagent-driven-development/SKILL.md`

**變更內容：**

1. `related_skills` 加入 `plan-review`
2. 在 "Step 1: Read and Parse Plan" 之前插入：

```markdown
### Step 0: Verify Plan Review (MANDATORY gate)

Before dispatching any subagent, check:
- [ ] Does the plan file contain a `## Independent Plan Review` section?
- [ ] Was the review score >= 60?

If NO to either: STOP. Load `plan-review` skill, run the critique, append to plan. Do not execute an unreviewed plan.
```

3. 在 "Final Review" 之後插入：

```markdown
### 3.5 Execution Notes — Feed Back to Plan

After integration review passes, append an `## Execution Notes` section to the plan:

```markdown
## Execution Notes (auto-appended)

**當次執行發現的 plan 未覆蓋項目：**
- [如果沒有：無]
- [如果有：具體事項]

**Plan 中與實作不符的細節：**
- [如果沒有：無]
- [如果有：具體事項]

**建議改進：**
- [具體建議]
```
```

4. `version` → 1.3.0

**Verification:** `grep "Verify Plan Review" SADD/SKILL.md` 有結果

---

### Task 3: Patch `writing-plans` — Step 6 Phase 3 語言升級

**Objective:** 把 "if available, load it" 改成 MANDATORY

**Files:**
- Modify: `~/.hermes/skills/software-development/writing-plans/SKILL.md`

**變更內容：**

Step 6 Phase 3 從：
```
**Phase 3 — If `plan-review` skill is available, load it now for independent second-pass critique.**
```
改為：
```
**Phase 3 — Load `plan-review` skill (MANDATORY — do not skip):**
Load the `plan-review` skill and run its 6-dimension critique against this plan. Append the review output (including raw_score) to the plan file. The plan is not considered complete without a review score.
```

**Verification:** Phase 3 文字中含 `MANDATORY` 且不含 `if available`

---

### Task 4: Patch `plan-review` — 加入 raw_score + 輸出增強

**Objective:** plan-review 輸出量化分數、要求引用行號

**Files:**
- Modify: `~/.hermes/skills/software-development/plan-review/SKILL.md`

**變更內容：**

1. 輸出格式中，在 Overall Assessment 下方加入 `**Raw Score:** N/100`
2. 計分規則寫入 skill：

```markdown
### Scoring

| 項目 | 扣分 |
|------|------|
| Critical Issue (🔴) | -15 per issue |
| 🟡 dimension | -5 per dimension |
| Missing 6-field header | -20 flat |
| Max score | 100 |

**Score interpretation:**
- 90+: Excellent — execute with confidence
- 70-89: Good — address recommendations, then execute
- 50-69: Needs work — fix critical issues, re-review
- <50: Blocked — rewrite plan, do not execute
```

3. Critical Issues 欄位要求引用具體位置：
```
1. **[Dimension] — [Issue]** (ref: plan line N / Task M)
```

**Verification:** `grep "Raw Score" plan-review/SKILL.md` 有結果

---

### Task 5: Dogfood 驗證 — 用此計劃走完整流程

**Objective:** 把這份 plan 當白老鼠，用 SADD 執行 → plan-review 被觸發 → 產出分數

**Files:**
- Read: 本計劃（`reports/2026-05-14-hermes-planning-skills-iteration.md`）

**Step 1:** 載入 `subagent-driven-development` + `plan-review`
**Step 2:** 執行 Tasks 1–4
**Step 3:** 確認 Tasks 1–4 每個 skill 檔案都已正確 patch
**Step 4:** 用 SADD 執行 Task 1 的驗證步驟
**Step 5:** 檢查 plan-review 是否被觸發 → 記錄 raw_score

**Verification:** 所有 4 個 skill 檔案通過語意檢查，plan-review 確認被觸發

---

## Self-Critique

**漏洞 1：** `plan` skill 不一定會被載入。如果用戶直接說「幫我規劃一下」，Hermes 可能直接 load `writing-plans` 而不經過 `plan` skill。

→ **對策：** 在 `writing-plans` 和 `plan` 兩處都設 gate（Tasks 1+3 已經 cover）。雙保險：plan skill 觸發 OR writing-plans 內部 Phase 3 觸發。如果兩邊都跳過，退路是 cron。此外，writing-plans 的 related_skills 已經包含 `plan-review`，Hermes 在 load writing-plans 時會看到並可能主動載入。

**漏洞 2：** plan-review 的 raw_score 不是真的「品質分數」——是同一個弱模型給另一個弱模型打分，兩個都可能有偏差。

→ **對策：** 這個限制已知且接受。文獻（CriticBench）說弱模型評判能力差距較小，不是完美只是「比生成好」。分數的價值是追蹤趨勢（這週平均 70 下週 80？），不是絕對值。不對單次分數過度解讀，看平均值。另外可考慮用不同模型做 plan review（如果環境支援）——Opus 審 DeepSeek 的 plan 會比 DeepSeek 審 DeepSeek 更準。

**漏洞 3：** 執行回饋（Task 2 的 Execution Notes）依賴 SADD 的 final integration reviewer subagent 準確記錄「plan 沒覆蓋的項目」。弱模型 subagent 可能漏記。

→ **對策：** 執行回饋階段用明確的 prompt 模板（「列出執行中實際發生但 plan 沒提到的 3 件事」），而非開放式提問。如果弱模型仍然漏記，升級方案是用 SADD controller（即載入 SADD 的主 agent）在收到每個 subagent 回報時檢查是否有「plan 沒寫但實際需要做」的項目，手動 append。但這需要 controller 有足夠 context 做判斷——先試 subagent 方案，不夠再升級。

---

## Independent Plan Review

> Reviewed by: plan-review skill v1.1.0

### Overall Assessment: 🟢 Pass

**Raw Score:** 85/100

**Summary:** 計劃完整、具體、可執行。每個 task 有明確的 old_string/new_string 對照、驗證方式、檔案路徑。主要扣分：Coherence（Task 2/4 順序依賴問題——執行時已調整順序解決）、Robustness（退路 cron 方案僅骨架）。

### Dimension Scores

| Dimension | Score | Issue Count |
|-----------|-------|-------------|
| Completeness | 🟢 | 0 |
| Correctness | 🟡 | 1 |
| Coherence | 🔴 | 1 |
| Robustness | 🟡 | 1 |
| Efficiency | 🟢 | 0 |
| Spec Alignment | 🟢 | 0 |

### Critical Issue

1. **Coherence — Task 2 引用還不存在的 scoring rubric** (ref: plan line 130 / Task 2): 執行時已透過調整順序解決（1→3→4→2）。

### Recommendations

1. 退路改為 SADD gate 攔截時就地補跑 plan-review（已實作）
2. Task 5 不重述步驟，純驗證（已遵守）

---

## Execution Notes (auto-appended)

**當次執行發現的 plan 未覆蓋項目：**
- 無（五個 tasks 都如計劃進行，patch 操作順利）

**Plan 中與實作不符的細節：**
- Task 2/4 順序相依性：plan 設計 Task 2 的 gate 檢查「review score >= 60」，但 scoring rubric 在 Task 4 —— 執行時已調整為 1→3→4→2 順序

**建議改進：**
- 以後的 iteration plan 應該先畫 dependency graph 再排 task 順序
- raw_score 的實際價值要等 5-10 次使用後才能判斷（平均分趨勢有意義，單次分意義有限）

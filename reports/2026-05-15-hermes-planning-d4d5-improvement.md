# D4/D5 規劃能力改善

> **For Hermes:** Patch plan-review + writing-plans skills. Two files, two changes each.

**Goal:** 用 Opus 規劃能力研究的 D4（規格完整性）/ D5（讀者假設最小化）框架，強化我的計畫品質控制——讓每份計畫都通過「執行者不會來回追問」的測試。

**Architecture:** 對兩個現有 skill 做最小化 patch：
- `plan-review`：Completeness 維度追加 D4/D5 explicit sub-checks
- `writing-plans`：Self-Critique 追加第 4 個漏洞（D4/D5）

**Tech Stack:** 純 skill markdown 編輯（patch tool），無程式碼。

## Planning Quality Checklist

├── **目標**
│   └── 計畫產出後，plan-review 能自動揪出 D4/D5 缺陷，而非被動等待執行者回報
│
├── **前置條件檢查**
│   ├── [x] plan-review skill 存在且讀取完畢
│   ├── [x] writing-plans skill 存在且讀取完畢
│   ├── [x] 已讀完 Opus 規劃研究報告（D4/D5 框架）
│   └── [ ] 確認改動不與現有 dimension 重複
│
├── **步驟清單**
│   ├── 1. Patch plan-review dimension 1：追加 D4/D5 sub-checks
│   ├── 2. Patch writing-plans Self-Critique：追加漏洞 4
│   ├── 3. 自我驗證：用改過的 plan-review 重審 gateway-shutdown 計畫
│   └── 4. 存計畫到雙路徑
│
├── **每步的驗證方式**
│   ├── Step 1: 讀取 plan-review SKILL.md → 確認 Completeness 區塊包含 D4/D5 提問
│   ├── Step 2: 讀取 writing-plans SKILL.md → 確認 Self-Critique 模板含 4 個漏洞
│   ├── Step 3: 對 gateway-shutdown 計畫跑新 plan-review → 應檢測出 D4/D5 gap
│   └── Step 4: 檔案存在於兩路徑
│
├── **潛在卡點**
│   ├── Completeness 維度已有「Missing file paths?」→ D4 檢查可能重複 → 用更尖銳的提問區分
│   └── 漏洞 4 是新增欄位，舊計畫只有 3 個漏洞 → 不強制回溯，只影響新計畫
│
└── **失敗時的退路**
    └── 若 D4/D5 sub-checks 太冗長讓 review output 過載 → 簡化為一個合成提問：「執行者會來回追問幾次？」

---

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🟢 設計完成，即刻執行 |
| **目前階段** | 實作 |
| **最後行動** | 無（新計畫） |
| **下一步** | Patch plan-review + writing-plans |
| **阻擋** | 無 |

---

## 現況評估

| 原需求 | 狀態 | 位置 |
|--------|------|------|
| plan-review 6-dimension rubric | ✅ | `/root/.hermes/skills/software-development/plan-review/SKILL.md:37-44` |
| writing-plans Self-Critique (3 loopholes) | ✅ | `/root/.hermes/skills/software-development/writing-plans/SKILL.md:192-214` |
| D4 規格完整性 explicit check | ❌ | 缺 |
| D5 讀者假設 explicit check | ❌ | 缺 |

---

## 設計

### 改動 1：plan-review — Completeness 維度追加 D4/D5

在 dimension 1 現有 4 個提問後追加 2 個：

```
- **D4 規格完整性**：文件路徑是否都給絕對路徑？函數簽名是否完整（參數＋回傳值）？
  目錄是否需要手動建立？指令是否可直接複製執行？
- **D5 讀者假設最小化**：執行者需要知道哪些隱含知識？哪些術語未定義？
  從零 spawn 的 subagent 需要問幾個問題才能開始執行？
```

### 改動 2：writing-plans — Self-Critique 追加漏洞 4

在模板 `漏洞 3` 後追加：

```
**漏洞 4（D4/D5）：** [執行者讀這份計畫時，會需要來回追問什麼？哪些資訊你假設他已經知道但其實沒寫在計畫裡？]

→ **對策：** [補上被遺漏的絕對路徑、簽名、術語定義、背景上下文]
```

---

## Self-Critique

**漏洞 1：** 新的 D4/D5 sub-checks 可能與現有「Missing file paths?」重複，導致 review output 冗長

→ **對策：** 將現有「Missing file paths?」改為「Missing file paths or incomplete signatures?」合併 D4 提問，避免冗餘

**漏洞 2：** 漏洞 4 要求新增欄位，但現有計畫只有 3 個漏洞，不符合新格式會讓 plan-review 誤判

→ **對策：** 僅在新計畫時強制 4 個漏洞；舊計畫視為 grandfathered。在 skill 中明確標註「v2.2+ 計畫需 4 個漏洞」

**漏洞 3：** D4/D5 中文化提問對 subagent 可能不夠精確（subagent 不一定懂 D4/D5 術語）

→ **對策：** 提問用日常語言，不要依賴 D4/D5 縮寫。核心是「執行者會需要追問什麼」


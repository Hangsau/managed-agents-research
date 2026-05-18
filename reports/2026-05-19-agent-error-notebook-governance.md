# 研究報告：Agent Error Notebook — 錯誤治理的務實架構

**日期**：2026-05-19
**來源數**：4 | **標籤**：#agent-self-correction #error-governance #memory #reflection

---

## 1. The Problem

AI agent 最惱人的問題不是「它做錯了」，而是「它又犯同樣的錯了」。

今天的 agent 框架（AutoGPT、CrewAI、LangGraph⋯⋯）多數處理錯誤的方式是 retry 迴圈或簡單的 exception catch。問題在於：同樣的失敗模式（API key 失效、頁面讀到但無資料、走了錯誤邏輯分支）會在不同時間、不同任務中重複出現，而 agent 沒有記憶——每次都是全新的 context。

傳統日誌能記錄「發生了什麼」，但不能防止下一次發生。業界需要的不是更大的 framework，而是**把每次失敗變成可復用的修復資產**。

---

## 2. Core Mechanism

這個領域目前最完整的實作是 **Error Notebook（错题本）**——一個輕量級的 agent 錯誤治理 starter kit，定位清晰：**post-error first，不做大而全框架**。

### 核心閉環（五步）

```
錯誤輸入
  → 分類（classify）
  → 檢索相似 notebook（retrieve）
  → 提取修復路徑（fix）
  → 顯式驗證清單（verify）
  → 寫入 action trace（trace）
```

### 分類層（classifier.py）

純規則，無 LLM。錯誤文字進來後用 keyword matching 分到五個錯誤域：

| 錯誤域 | 觸發關鍵詞 |
|--------|-----------|
| `provider_auth` | api key, auth, unauthorized, forbidden, model unavailable |
| `transient_network` | timeout, connection reset, rate limit, 429 |
| `file_io` | file not found, path, encoding, models.json, config |
| `web_scraping` | scrape, browser, cloudflare, selector, extracted content empty |
| `workflow_or_logic` | cron, delivery, wrong branch, partial success |

```python
# classifier.py（純規則，無依賴）
def classify_error(error_text: str) -> str:
    text = (error_text or "").lower()
    if any(kw in text for kw in PROVIDER_AUTH_KEYWORDS):
        return "provider_auth"
    if any(kw in text for kw in TRANSIENT_NETWORK_KEYWORDS):
        return "transient_network"
    # ... 其餘 domains ...
    return "workflow_or_logic"
```

### 檢索層（retrieval.py）

不靠向量資料庫，靠 **BM25-style token overlap**：

```python
# retrieval.py（無 external dependencies）
def retrieve_notebooks(error_type: str, error_text: str, top_k: int = 3) -> list[Path]:
    target_dir = ERRORS_DIR / error_type
    query_tokens = _tokens(error_text)  # alphanumeric tokenization
    scored = []
    for path in target_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        score = len(query_tokens & _tokens(content))
        scored.append((score, path))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [path for score, path in scored[:top_k] if score > 0]
```

### Notebook 格式（errors/ 資料夾）

每個失敗案例是一個 `.md` 檔，有 YAML frontmatter + 標準結構：

```markdown
---
notebook_id: nb_provider_auth_001
title: API key missing
category: provider_auth
tags: [api_key, auth, provider]
risk: medium
version: 1
status: active
---

# Error: API Key Missing

## Symptoms
- OpenAI API key missing
- auth not configured for provider

## Root Cause
Environment variable or provider auth profile is missing.

## Fix
Set the required API key or switch to a provider with valid auth.

## Verification
- Check the required API key/profile is present
- Run a minimal request and confirm a real response is returned
```

**關鍵設計：每個 notebook 必須有 `Fix` 和 `Verification` 兩個 section，且 verification 不能只是「看起來沒報錯」**——要有具體的狀態檢查、輸出存在性檢查、或內容相關性檢查。

### Action Trace（logger.py）

每次 recovery 動作寫入 `memory/action_log.md`，留下可審計的軌跡：

```markdown
## 2026-03-09 14:23 - OpenAI API key missing
- 類型：provider_auth
- 讀取錯題：errors/provider_auth/api_key_missing.md
- 觸發方式：post-error
- 驗證證據：Check OPENAI_API_KEY is present / Run minimal request
```

### 觸發策略

- **預設：post-error first**（錯誤發生後檢索相似案例）
- **Preflight only**（只在高靜默失敗風險任務中事前檢查）：config 變更、cron/delivery routing、scraping 相關任務

### 與既有方案的差異

| 方案 | 分類方式 | 驗證 | 建構方式 | 定位 |
|------|---------|------|---------|------|
| **Error Notebook** | 規則 keyword | 顯式驗證清單 | 失敗驅動累積 | 錯誤治理 starter kit |
| Reflexion（Shinn et al.） | LLM verbal reflection | 無結構化驗證 | 純研究論文 | 學術 agent self-correction |
| Self-RAG | LLM critique token | 引用溯源 | 微調模型 | RAG 領域特定 |
| LangGraph try/except | exception 捕捉 | 無 | 手動迴圈 | 框架內建錯誤處理 |

---

## 3. Why It Matters / Applications

### 為什麼這個方向重要

**Agent 的重複失敗問題比想像中嚴重。** 根據 Carnegie Mellon 的研究，leading AI agents 在多步驟任務中成功率只有 30–35%。多數框架專注在「讓成功的那 35% 跑得更快」，但忽略了「讓失敗的 65% 變成可學習的經驗」。

Error Notebook 的核心 insight 是：**agent 需要的不是更大的推理能力，而是更好的失敗記憶**。當同一個「頁面讀到但無資料」錯誤第三次發生時，agent 應該能從歷史案例中檢索到修復路徑，而不是重新推理一次。

### 對 firn 的啟發

- **心跳/健康監控**：`heartbeat-v2` 已經能檢測 zombie session，但檢測到之後呢？Error Notebook 的框架可以直接變成「檢測到 zombie → 分類為 workflow_or_logic → 檢索 recovery notebook → 執行驗證」迴圈。
- **預檢查（preflight）**：在高風險任務（config 變更、model switch）前檢索對應的 `notebook`，相當於「上次這件事失敗過，先看看當時怎麼修好的」。

### 對 managed-agents 的啟發

批次 runner 的失敗模式其實很固定：
- Provider auth 失效
- Tool timeout
- 網路瞬斷
- 輸出格式不符預期

如果 managed-agents 的每個 action module 都有對應的 notebook 資料夾，長期下來就能累積出「這類任務的常見失敗 + 修復方式」知識庫，而不是每次遇到就從零開始 debug。

---

## 4. Limitations / Honest Assessment

### 作者坦承的限制

- **v0.1，規模有限**：目前只有 8 個 notebook，覆蓋場景狹窄
- **規則分類粗糙**：keyword matching 對新型錯誤無效，需要手動擴展 keyword sets
- **無向量檢索**：BM25-style token overlap 在複雜語義上不如 embedding similarity
- **無自動 notebook 生成**：遇到新失敗模式時需要人工建立 notebook，不能從對話中自動抽取
- **星數極少**：目前僅 2 ⭐，沒有社群驗證，屬於個人實驗性質專案

### 我們的獨立評估

**可信度：MEDIUM**。概念架構清晰、程式碼可運行、但缺乏規模化驗證。這個想法在概念上很強（錯題本機制在教育領域行之有年），但需要更多 notebook 累積和真實場景測試才能判斷有效性。

**可複製性：TRIVIAL**。整個專案只有 4 個 Python 檔案（classifier、retrieval、parser、logger）+ Markdown notebook 資料夾。核心邏輯約 200 行，無外部 dependency，直接 fork 就能用。

**最大風險**：notebook 的品質取決於維護紀律。如果團隊不持續新增 notebook，這個系統會慢慢失效——就像沒有題庫的錯題本。

**對比 Reflexion**：Reflexion 是 LLM 自己做 verbal reflection（"what went wrong?"），Error Notebook 是從預先建好的 notebook 中檢索修復路徑。前者需要模型有足夠的元認知能力，後者則把知識外部化了——**知識外部化讓修復路徑更可控、更可審計，但需要人工建庫的代價**。

---

## 5. Actionable for Our Projects

### firn — Error Notebook Integration

| 優先級 | 工作 | 原因 | 難度 |
|--------|------|------|------|
| **P0** | Fork Error Notebook 架構到 firn 的 error 資料夾 | 把現有錯誤處理提升為結構化 notebook | MODERATE |
| **P1** | 在 `heartbeat-v2` 的 zombie detection 後串接 notebook 分類 + 修復路徑檢索 | 把「檢測到問題」升級為「檢測到問題 + 知道怎麼修」 | MODERATE |
| **P2** | 在 tool execution wrapper 中加入 post-error 分類觸發（`classify → retrieve → verify`） | 讓每個 tool 的失敗都變成 notebook entry candidate | TRIVIAL |

**具體實作步驟**：
1. `mkdir -p firn/error_notebook/{errors,error_memory,memory,examples}`
2. 從 Error-Notebook-for-agents 的 `error_memory/` 複製 `classifier.py`、`retrieval.py`、`parser.py`、`logger.py`、`pipeline.py`
3. 將 `errors/` 結構改為對應 firn 實際失敗模式（provider_auth、tool_timeout、session_crash 等）
4. 在 tool wrapper 的 exception handler 中呼叫 `pipeline.handle_error(error_text)`

### managed-agents — Action-level Error Notebooks

| 優先級 | 工作 | 原因 | 難度 |
|--------|------|------|------|
| **P0** | 為 harness_v2 的每個 action type 建立對應 notebook 資料夾 | 批次 runner 的失敗模式固定，notebook 累積價值高 | TRIVIAL |
| **P1** | 在 `turn_loop.py` 的 action result handler 中串接 notebook 分類 | 每個 action 失敗自動寫入 action log，形成迴路 | MODERATE |

**免費方案**：Error Notebook 完全不需要付費 API。規則分類 + token overlap 檢索都是 deterministic Python logic，0 API 成本。

---

## 6. Follow-up Questions

1. **Notebook 如何自動生成？** 目前靠人工維護，但理想上 LLM 應該能從 failed task 的對話中自動抽取「症狀→根因→修復→驗證」寫成 notebook。這是下一個研究方向。

2. **驗證層如何自動化？** Error Notebook 的驗證要求（"Run a minimal request and confirm a real response"）在實務上需要一個通用的驗證執行框架，這部分目前完全沒實作。

3. **規則分類的規模化瓶頸**：5 個 keyword set 能 cover 真實失敗的 % 是多少？需要更多 notebook 才能評估。

4. **Embedding 檢索是否值得加？** 當 notebook 數量超過 50 個後，token overlap 的精確度會下降。但加 vector DB 會破壞「零依賴」的設計原則，需要權衡。

---

### 原始來源

https://github.com/8964story/Error-Notebook-for-agents — GitHub Repo — MEDIUM — 核心實作來源。v0.1 完整可運行，包含 classifier/retrieval/parser/logger/pipeline 五個 Python 模組 + 8 個 notebook 樣例。MIT license。

https://github.com/8964story/Error-Notebook-for-agents/blob/main/error_memory/pipeline.py — Source Code — HIGH — 核心邏輯實作，展示了完整的 `handle_error()` 流程。

https://github.com/8964story/Error-Notebook-for-agents/blob/main/error_memory/retrieval.py — Source Code — HIGH — BM25-style 檢索實作，無外部依賴。

https://github.com/8964story/Error-Notebook-for-agents/blob/main/errors/provider_auth/api_key_missing.md — Source Code — HIGH — Notebook 格式範例，完整 YAML frontmatter + 4-section 結構。

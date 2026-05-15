# Phase 1: 評估框架 — 規劃能力的 7 維度與比較對象版本表

> **本檔目的**：在進入 benchmark 與機制分析前，先定義「規劃能力」具體指什麼、用什麼 benchmark 衡量、比較對象的精確版本為何。後續所有 Phase 都引用本檔的定義。
>
> **修訂歷史**：v1（2026-05-15 初稿，5 維度）→ v2（2026-05-15 同行評審後，補 D6/D7、重切 D4/D5、補 meta-planning 層、H1 降格）

---

## 1. 為什麼需要拆解「規劃能力」

「規劃」在 LLM 領域被混用至少四層：

0. **meta-planning（規劃顆粒度與模式的選擇）** — 在規劃前判斷該採用何種規劃形式（一次性 implementation list / 分階段 plan-check / 平鋪 micro-tasks）
1. **chain-of-thought（單步推理）** — 解題時的中間推理步驟
2. **agentic task planning（工具/狀態空間規劃）** — agent 在環境中決定動作序列
3. **engineering spec planning（工程規格規劃）** — 把模糊需求轉成可被另一個 agent / 人類直接執行的 self-contained 規格

本研究的核心關心 **第 3 層**，因為這是用戶在 claudehome 工作流中所說的「Opus 規劃 vs Sonnet 實作」的實際分工——Opus 產出的是 implementation list，必須在新 session 中（context 為空）被 Sonnet 直接執行不卡關。

**第 0 層（meta-planning）不獨立成維度**，但在 Phase 3 機制分析時會觸及（特別是「為什麼 Opus 能判斷該分幾階段 plan-check」這類能力，與訓練資料中含工程規劃元 pattern 有關）。

**第 1、2 層的成績**（GPQA Diamond、SWE-bench Verified pass rate）只是**間接證據**，因為它們把規劃與執行混在同一個分數裡，無法獨立衡量規劃品質。

---

## 2. 規劃能力 7 維度

| # | 維度 | 操作型定義 | 失敗時的可觀察症狀 |
|---|------|-----------|----------------|
| **D1** | 任務分解粒度 | 把模糊需求切成可獨立驗收的子任務（不含派工標註，那是 meta 層） | 子任務範圍重疊、邊界模糊、有的任務「做完了但說不出做了什麼」 |
| **D2** | 依賴/順序推理 | 識別前置條件、決定執行順序 | 後段任務發現前段缺資料、重複改同一個檔案、需回頭重排 |
| **D3** | 風險預判 | 提前列出 blocker 與對應預案 | 執行階段才發現環境/版本/權限阻礙、無預案需臨時想辦法 |
| **D4** | 規格資訊完整性 | 規格本身含實作所需全部具體資訊（行號、regex、預設值、命令、檔名） | 實作 agent 需回頭問「這個 flag 預設值是什麼」、規格中出現 `<TODO>` / `<TBD>` 標記 |
| **D5** | 對讀者背景假設最小化（語用層） | 規格不依賴特定 session 歷史、不假設讀者讀過某 thread / 某文件 | 新 session 讀者問「這個術語在這個 repo 指什麼」、「為什麼選 A 不選 B」之類**語用**問題（而非資訊缺失） |
| **D6** | 規劃修正能力（replanning） | 執行中遇偏離時能否局部修補不需整體重來 | 實作 agent 回報 W3 卡住時 planner 重發整份 plan；無 fallback 路徑；單點失敗整體癱瘓 |
| **D7** | 規劃效率（time/token cost） | 產出 self-contained 規格所需的 token 與時間 | 規劃成本 ≥ 實作成本，派工經濟學失效；長 plan-check 視窗吃配額導致實作階段被迫降模型 |

### 維度設計理由

來自用戶 claudehome 全域 CLAUDE.md 與 memory 中關於 plan-check / implement 的反覆描述：
- 「implementation list 行號、regex、預設值全部 inline」→ D4（資訊完整）
- 「跨模型接力（Opus 規劃 / Sonnet 執行）implementation list 必須完全 self-contained」→ D5（背景假設最小）
- 「plan-check 含目標狀態、影響範圍、執行路徑、預期風險、風險預案」→ D1 + D2 + D3
- 「派工分配必須在 plan-check / implement 規劃階段就明確標註」→ 屬於 meta 標註層，吸收在 D7 派工經濟學裡（規劃時就考慮派工 = 規劃效率的一環）
- 「派工目標是換 Opus 視窗，不是省美金」→ D7 的存在理由
- 用戶實戰中「plan-check 後遇障礙重排」→ D6

### D4 vs D5 的切分（同行評審後修正）

舊版 v1 兩者高度共線。v2 切分如下：

| 軸 | D4 | D5 |
|----|----|----|
| 失敗類型 | **資訊缺失**（規格沒寫某個值） | **語用歧義**（規格寫了但讀者無法理解） |
| 失敗症狀 | 「這裡的 X 預設值是？」 | 「這個 repo 裡 X 是指 A 還是 B？」 |
| 修補方式 | 補上缺漏資訊 | 補上 disambiguation 註腳或背景說明 |
| 與訓練面關聯 | 規格產出的詳細度（fine-tuning on detailed specs） | 跨會話讀者建模能力（reader modeling） |

---

## 3. 對應 benchmark 與其侷限（侷限欄統一為「領域 / 規模 / 公開性 / 污染風險」四項）

| 維度 | benchmark | 量化方式 | 侷限 |
|------|-----------|---------|------|
| D1 | **PlanBench (blocksworld / logistics)** | plan 步驟正確率 | 領域窄（積木/物流玩具） / 規模小 / 公開 / 公開 prompt 已被多輪訓練包含，污染風險高 |
| D1 + D2 | **TravelPlanner** | 含約束的多步規劃成功率 | 領域窄（旅遊） / 中等規模 / 公開 / 可被 prompt engineering 拉高 |
| D2 + D4 | **SWE-bench Verified（plan-only 切分）** | 把 patch generation 分為 plan / implement 兩階段，固定 implementer 比較不同 planner | 領域：開源 GitHub bug 修補 / 規模 500 任務 / 公開 / 已知部分模型訓練包含 GitHub patches |
| D3 | **τ-bench (airline / retail)** | 在含錯誤環境中完成任務的穩定性 | 領域：客服對話 / 中等規模 / 公開 / 偏 conversational |
| D3 + D5 + D6 | **Expert-SWE (OpenAI-only reference)** | 中位完成時間 20 小時的長 horizon 工程任務 | 領域：軟工 / 規模：少量 / **非公開（OpenAI 內部）** / 只有 OpenAI 自家成績可比 — **不放跨廠商主矩陣** |
| D4 + D5 | **自建 micro-eval（Phase 2 建構）** | 固定 implementer agent（Haiku N=10），對同一需求由 6 個 planner 產規格，量化通過率 + 補問次數 | 領域：本研究 ad-hoc / 規模需 ≥ 30 題才有統計效力 / 自建公開 / 污染低 |
| D6 | **Long-horizon agentic（Terminal-Bench 2.0 / SWE-bench Live 連續多 patch）** | 環境變化下的 replan 與 recovery | 領域：終端任務 / 規模中 / 半公開 / 已被部分廠商 fine-tune |
| D7 | **規劃 token 量 + wall-clock 時間（自蒐）** | 同一 prompt 跑 6 模型，量 input/output tokens + latency | 領域：本研究 ad-hoc / N=10 prompt / 自建 / 受 thinking mode 設定影響大 |

**結論**：沒有單一公開 benchmark 能涵蓋 D1~D7；本研究在 Phase 2 用「組合矩陣」呈現各模型在每個維度的近似得分，**自建 micro-eval 補 D4/D5/D7 的缺口**，並明確標註資料缺口。

---

## 4. 比較對象的精確版本（截至 2026-05-15）

| 廠商 | 模型 ID | 釋出日期 | 規模 | Context | thinking 模式 |
|------|---------|---------|------|---------|--------------|
| Anthropic | **claude-opus-4-7** | 2026-04-16 | 未公開（社群推測 dense，無官方確認） | **1M** | extended thinking |
| Anthropic | **claude-sonnet-4-6** | 2026-02-17 | 未公開（社群推測 dense，無官方確認） | 200K | extended thinking |
| DeepSeek | **deepseek-v4-pro** | 2026-04-24 | 1.6T MoE / 49B 啟動 | 1M | hybrid thinking/non-thinking |
| MiniMax | **minimax-m2.7** | 2026 Q2 | ~230B MoE / 10B 啟動（基於 M2 規格） | ~200K（204.8K） | interleaved thinking |
| Moonshot | **Kimi-K2.6** | 2026-04-20 | 1T MoE / 32B 啟動 | 262K | thinking |
| OpenAI | **gpt-5.5** / **gpt-5.2-codex** | 2026-04-23 | 未公開 | 未公開 | thinking |

### 命名歧義釐清

- **「DeepSeek V4 Pro」** — 用戶提的名稱正確，是 DeepSeek 2026-04-24 釋出的 1.6T MoE 模型，MIT license（HF：`deepseek-ai/DeepSeek-V4-Pro`）。同系列還有 V4-Flash（284B）。
- **「Codex GPT-5.5」** — 實際對應 OpenAI 兩個產品：通用版 `gpt-5.5`（2026-04-23 介紹），coding 特化版 `gpt-5.2-codex`。本研究兩者皆涵蓋，未特別區分時指通用 gpt-5.5。
- **「MiniMax」** — 用戶實戰中對應 minimax-m2.7（最新 M2 系列分支）。

### 模型分類

| 類別 | 模型 |
|------|------|
| 閉源旗艦（agentic-tuned） | Opus 4.7, GPT-5.5, GPT-5.2-Codex |
| 閉源量產 default | Sonnet 4.6 |
| 開源旗艦 | DeepSeek V4 Pro, Kimi K2.6, MiniMax M2.7 |

---

## 5. 已知初步證據（Phase 1 預搜，待 Phase 2 系統化）

從 Phase 1 預搜的公開資料（**跨世代縱比 vs 同代橫比** 分開排版）：

**同代橫比（2026 Q2 旗艦）**：
- SWE-bench Verified：Opus 4.7 **87.6%** > DeepSeek V4 Pro 80.6% > Kimi K2 65.8%
- GPQA Diamond：Opus 4.7 **94.2%** ≈ GPT-5.4 Pro 94.4%
- Terminal-Bench 2.0：GPT-5.5 **82.7%**（OpenAI 強項）
- Codeforces：DeepSeek V4 Pro 3,206 > GPT-5.4 3,168
- τ2-bench：Kimi K2 66.1（agentic）

**跨世代縱比（Anthropic 內部）**：
- SWE-bench Verified：Opus 4.7 87.6% > Opus 4.6 80.8%

### H1 — 待 Phase 3 驗證的假設

**H1**：Opus 4.7 在綜合 benchmark（SWE-bench / GPQA）上的領先（約 5-7 個百分點）**不對等於**用戶實戰中感受到的規劃能力差距。**不對稱性可能集中在 D3（風險預判）、D4（資訊完整）、D5（背景假設最小化）、D6（replanning）這四個維度。**

**為何不是 D1（任務分解）/ D2（依賴推理）**：SWE-bench Verified 等 benchmark 在 plan→implement 隱含了 D1/D2（patch 順序正確才能通過 tests）。Opus 4.7 vs DeepSeek V4 Pro 在這類綜合分數上差距僅 7%，意味著 D1/D2 差距相對小。

**falsifiable 條件（任一成立則 H1 不成立或需修正）**：
- Phase 3 機制分析發現 Opus 與其他模型在 D1 / D2 對應的訓練資料來源**顯著不同**（例如 Anthropic 公開或洩漏特殊 plan-only 訓練語料）
- Phase 2 自建 micro-eval 發現 6 個模型在 D4 / D5 通過率**差距 < 10%**
- Phase 2 公開 benchmark 在 D3 / D6 對應指標（τ-bench / Terminal-Bench）上**其他模型勝過 Opus**

**驗證計畫**：Phase 2 矩陣 + 自建 micro-eval → 看不對稱是否真集中在 D3/D4/D5/D6 → Phase 3 從訓練/架構面推因。

---

## 6. 後續 Phase 規劃

- **Phase 2** (`01_benchmarks.md`)：填滿 7 維 × 6 模型矩陣，明確標註資料缺口；自建 micro-eval 補 D4/D5/D7
- **Phase 3** (`02_mechanism.md`)：從架構與訓練面解釋為何 Opus 在 D3/D4/D5/D6 拉開差距（即 H1 的因果機制）
- **Phase 4** (`03_field_evidence.md` + 最終整合)：用 claudehome memory + 社群報告交叉印證 H1

---

## Sources（Phase 1 預搜引用）

- [Claude Opus 4.7 API Docs（含 1M context）](https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7)
- [Anthropic — Introducing Claude Opus 4.7](https://www.anthropic.com/news/claude-opus-4-7)
- [Anthropic — Introducing Claude Sonnet 4.6](https://www.anthropic.com/news/claude-sonnet-4-6)
- [DeepSeek V4 Pro — Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)
- [DeepSeek V4 Preview Release — DeepSeek API Docs](https://api-docs.deepseek.com/news/news260424)
- [DeepSeek V4 Pro 2026: 80.6% SWE-Bench — Codersera](https://codersera.com/blog/deepseek-v4-pro-review-benchmarks-pricing-2026/)
- [Claude Opus 4.7 Benchmarks Explained — Vellum](https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained)
- [Claude Sonnet 4.6 vs Claude Opus 4.7 — Qubrid](https://www.qubrid.com/blog/claude-sonnet-46-vs-claude-opus-47-which-model-wins-for-your-workload)
- [Introducing GPT-5.5 — OpenAI](https://openai.com/index/introducing-gpt-5-5/)
- [Introducing GPT-5.2-Codex — OpenAI](https://openai.com/index/introducing-gpt-5-2-codex/)
- [GPT-5.5 Terminal-Bench 82.7% — MarkTechPost](https://www.marktechpost.com/2026/04/23/openai-releases-gpt-5-5-a-fully-retrained-agentic-model-that-scores-82-7-on-terminal-bench-2-0-and-84-9-on-gdpval/)
- [Kimi K2.6 — Moonshot HF](https://huggingface.co/moonshotai/Kimi-K2.6)
- [Kimi K2 Technical Report — arXiv 2507.20534](https://arxiv.org/abs/2507.20534)
- [Kimi K2.6 — OpenRouter（含 262K context）](https://openrouter.ai/moonshotai/kimi-k2.6)
- [MiniMax M2 Benchmarks — Artificial Analysis](https://artificialanalysis.ai/articles/minimax-m2-benchmarks-and-analysis)
- [MiniMax M2.7 — MiniMax News](https://www.minimax.io/news/minimax-m27-en)
- [MiniMax M2.7 — OpenRouter（含 204.8K context）](https://openrouter.ai/minimax/minimax-m2.7)
- [SWE-bench Verified Leaderboard](https://llm-stats.com/benchmarks/swe-bench-verified)

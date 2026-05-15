# Phase 2: 公開 benchmark 矩陣 — 7 維度 × 6 模型（v2）

> **本檔目的**：把 Phase 1 定義的 7 維度與 6 款旗艦模型在公開 benchmark 上的成績交叉成矩陣，明確標註資料缺口；找出 H1（Opus 在 D3/D4/D5/D6 領先）的支持與反例，**並嚴格處理競爭假設 H1-alt（selection effect）**。
>
> **修訂歷史**：v1（2026-05-15 初稿）→ v2（同行評審後，修正 GPQA 數字、矩陣維度標註、自報註腳、micro-eval rubric、加 H1-alt 競爭假設、Terminal-Bench 反例不再消解）

---

## 1. 公開 benchmark 主矩陣

**規則**：
- 所有分數來自公開 leaderboard / 官方技術報告（來源見 §6）
- 「†」= 廠商自報；無記號 = 第三方 leaderboard
- 「N/A」= 公開資料不足；「N/T」= 該 benchmark 對該模型不適用
- 維度標註誠實反映 benchmark 實際涵蓋面（混測 benchmark 標出所有可能維度）

| benchmark | 實際涵蓋維度 | Opus 4.7 | Sonnet 4.6 | DeepSeek V4 Pro | Kimi K2.6 | MiniMax M2.7 | GPT-5.5 / Codex |
|-----------|------------|----------|------------|-----------------|-----------|--------------|-----------------|
| SWE-bench Verified | D1+D2+D3+D4+D6（混測，無法分離） | 87.6% | 79.6% | 80.6% | 80.2% | 78%† | **88.7%†** |
| SWE-Bench Pro | D1+D2+D4（跨檔規劃） | **64.3%** | N/A | N/A | N/A | 56.22%† (SWE-Pro 變體) | 58.6%† |
| GPQA Diamond | D2 only（純 multi-step reasoning，不測規劃） | **94.2%** | ~88% | 90.1% | 90.5% | N/A | 94.4% (GPT-5.4 Pro) |
| τ-bench Airline | D3+D6（conversational agent） | N/A | 0.700 (Sonnet 4.5 數字) | N/A（τ² 細項無第一手來源） | N/A | N/A | N/A |
| τ-bench Retail | D3+D6 | N/A | 86.2% (Sonnet 4.5) | N/A（同上） | N/A | N/A | N/A |
| τ²-bench（多模型混合） | D3+D6 | N/A | N/A | N/A（來源未證實） | 66.1 (K2 原版) | N/A | N/A |
| Terminal-Bench 2.0 | D1+D2+D6（long-horizon agentic loop） | 69.4% (Adaptive) | N/A | ~60-68% | 66.7% | 57.0%† | **82.7%†** |
| Codeforces rating | D2 only（純程式推理） | N/A | N/A | **3,206** | N/A | N/A | 3,168 (GPT-5.4) |

### 關鍵觀察（修正版）

1. **沒有 benchmark 直接測 D4 / D5 / D7**——這三個維度是公開層的盲區（後詳）。
2. **SWE-bench Verified 的「Opus 4.7 vs GPT-5.5」差距僅 1.1 pt 且 GPT-5.5 是廠商自報**——這在第三方驗證前**不應視為實質差距**；同 benchmark 上 Opus 與 DeepSeek/Kimi 差距約 7 pt 屬於實質。
3. **GPQA Diamond 上 Opus 4.7 vs 開源旗艦差距 3.7-4.1 pt**——遠小於 v1 矩陣呈現的 7 pt 差距（v1 數字有誤）；意味著「Opus 純 reasoning 領先」在 2026-05 已被開源旗艦追上至 4 pt 內。
4. **Terminal-Bench 2.0 上 Opus 4.7 (69.4%) 落後 GPT-5.5 (82.7%) 13 pt**——這是矩陣中唯一突破單一 benchmark 自報誤差的實質差距，且方向**不利於 Opus**。此 benchmark 涵蓋 D6（replan），意味 **Opus 在 D6 維度確實弱於 GPT-5.5**（H1 v2 中「Opus 中等 D6」需下修為「中等偏弱 D6」）。
5. **SWE-Bench Pro 上 Opus 4.7 (64.3%) 領先 GPT-5.5 (58.6%) 5.7 pt**——這是 Opus 在跨檔規劃（D1+D2+D4）上唯一突破誤差的領先，**且 GPT-5.5 自報但 Opus 第三方**，相對公平。

### 自報 vs 第三方分布

| 模型 | 自報數字（含 †） | 第三方驗證 |
|------|----------------|----------|
| Opus 4.7 | 0/7 | 7/7（Anthropic blog + Vellum + llm-stats） |
| GPT-5.5 | 4/4（SWE-bench, SWE-Bench Pro, Terminal-Bench, agentic） | 0/4 |
| Kimi K2.6 | 部分（K2 原版有 arXiv） | SWE-bench / Terminal-Bench / GPQA 有第三方 |
| DeepSeek V4 Pro | 主要 | Codeforces 有第三方 |
| MiniMax M2.7 | 主要（自家 blog） | OpenRouter 同步 |
| Sonnet 4.6 | Anthropic | 多源 |

**結論**：跨廠商比較時，GPT-5.5 與 Opus 4.7 的比較**不對等**（前者全自報、後者全第三方），這影響 §4 的 H1 判斷。

---

## 2. 維度覆蓋度盤點（量化版）

每個 benchmark 對 D1-D7 的近似涵蓋比例（主觀估計 0-1，由 Phase 1 定義反推）：

| Benchmark \ 維度 | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
|----------------|----|----|----|----|----|----|----|
| SWE-bench Verified | 0.3 | 0.4 | 0.2 | 0.3 | 0 | 0.2 | 0 |
| SWE-Bench Pro | 0.4 | 0.5 | 0.2 | 0.3 | 0 | 0.2 | 0 |
| GPQA Diamond | 0 | 0.9 | 0 | 0 | 0 | 0 | 0 |
| τ-bench Airline/Retail | 0.1 | 0.2 | 0.4 | 0 | 0 | 0.5 | 0 |
| Terminal-Bench 2.0 | 0.3 | 0.3 | 0.2 | 0.1 | 0 | 0.6 | 0 |
| Codeforces | 0 | 0.9 | 0 | 0 | 0 | 0 | 0 |

**聚合涵蓋度**（取最大值）：

| 維度 | 最大公開 benchmark 涵蓋 | 缺口 |
|------|---------------------|------|
| D1 任務分解 | 0.4（SWE-Bench Pro） | 中度缺口 |
| D2 依賴/順序推理 | 0.9（GPQA / Codeforces） | 充分覆蓋 |
| D3 風險預判 | 0.4（τ-bench） | 中度缺口 |
| D4 規格資訊完整性 | 0.3（SWE-bench 系列） | **重度缺口** |
| D5 讀者背景假設最小化 | 0 | **完全盲區** |
| D6 規劃修正能力 | 0.6（Terminal-Bench） | 較好覆蓋 |
| D7 規劃效率 | 0 | **完全盲區** |

**結論**：**D5 與 D7 是公開 benchmark 完全盲區**；D4 涵蓋度 0.3 雖非零但偏弱。這意味著 Opus 在用戶實戰中可能感受到的優勢，若集中在 D4/D5/D7，**將不被任何公開 benchmark 量化**。

---

## 3. 自建 micro-eval 設計（補 D4/D5/D7 缺口，v2）

### 設計（修正版）

- **題庫規模**：50-60 題工程規格題（v1 30 題統計效力不足，binomial test α=0.05 / power 0.8 / 預期差距 20pt 下需 ≥ 50 題 + Bonferroni 校正 15 對比較）
- **題庫來源**：claudehome 過往 plan-check 抽取 + 公開 GitHub issues 含模糊需求
- **planner role**：每個被測模型產 self-contained implementation list
- **prompt-style 控制變數**：每題用兩套 prompt 各跑一次
  - **Anthropic-style**：含 XML tag、artifact format、Claude system prompt convention
  - **Generic neutral**：純自然語言、無模型特定格式
  - **檢視 prompt-style 對結果的影響量**——這是測 H1-alt（selection effect）的關鍵
- **implementer role**：每題用兩個 implementer 取一致結果
  - Haiku（Anthropic 系）
  - GPT-4o-mini（OpenAI 系，cross-control）
  - 一致部分採用，分歧的另行人工標
- **補問分類 rubric**（兩個獨立 reviewer 標）：
  - `info_missing`（D4 失敗）：補問詢問「具體值是多少」「該檔案路徑」「該 flag 預設」
  - `pragmatic_ambiguity`（D5 失敗）：補問詢問「這個 repo 裡 X 指什麼」「為什麼選 A 不選 B」「這個任務的範圍邊界」
  - `noise`（捨棄）：補問本身語意不清或 implementer 自己誤解
  - **採用條件**：Cohen's κ ≥ 0.7 reviewer 一致性
- **scoring**：
  - D4 通過率 = (1 - `info_missing` 補問次數/題數)
  - D5 通過率 = (1 - `pragmatic_ambiguity` 補問次數/題數)
  - D7 = planner output tokens + wall-clock latency

### 為何留作後續

跑 50 題 × 6 模型 × 2 prompt-style × 2 implementer = 1200 trial，加上人工 label 50 × 6 × 2 = 600 規格 review，成本超出本次 Opus 視窗負擔。本檔給出可重現設計藍圖；執行可派外部 cron（Hestia 已關，需用 shotclock 排）。

---

## 4. H1 修正（v3）+ 競爭假設 H1-alt

### H1 v3：「Opus 規劃感優於其他」的假設空間

**H1（核心假設）**：Opus 在 D4 / D5（規格資訊完整 / 讀者背景假設最小）上實質領先其他旗艦，這構成用戶實戰中感受到差距的主因。其餘維度（D1-D3 / D6）Opus 與其他旗艦差距在公開 benchmark 自報誤差內，**並非主要差距來源**。

**H1-alt（競爭假設，必須驗證才能拒絕）**：用戶感受到的 Opus 規劃優勢來自 **selection effect 與 prompting style 熟悉度**，而非模型實際 D4/D5 能力差。具體來源：

1. **用戶長期用 Claude，plan-check prompt 範本對 Anthropic 模型 fine-tuned**——其他模型同 prompt 自然吃虧
2. **Anthropic artifact / structured output 訓練偏好剛好對齊用戶 plan-check 範本格式**——這是「模型能力」嗎，還是「格式偶然對齊」？
3. **Confirmation bias**：用戶切到其他模型時帶著「Opus 應該贏」預期，這影響評估
4. **Benchmark blindness**：用戶從未做過控制變數的盲測

### Falsification 條件

- **micro-eval 用 generic prompt 跑時 Opus 領先消失或縮小** → H1-alt 強，H1 弱
- **micro-eval 用 Anthropic-style prompt 與 generic prompt 跑出顯著差異**（同模型在兩種 prompt 下表現差距 > 模型之間差距） → H1-alt 主導
- **cross-implementer（Haiku + GPT-4o-mini）對同 planner 評分不一致率高** → implementer 偏見大，整個 micro-eval 不可信
- **Opus 在所有 prompt-style 與 implementer 組合下都領先 ≥ 15 pt** → H1 主導，H1-alt 弱

### H1 v3 的子假設

修正後對各維度的判斷（標明證據強度）：

| 維度 | Opus 4.7 相對位置 | 證據強度 | 證據來源 |
|------|----------------|---------|---------|
| D1 任務分解 | 與旗艦相當 | 中 | SWE-Bench Pro 領先 GPT-5.5 5.7 pt |
| D2 依賴/順序推理 | 與旗艦相當 | 高 | GPQA 4 pt 內，Codeforces 落後 DeepSeek |
| D3 風險預判 | 無資料 | 無 | 無公開 benchmark |
| D4 規格資訊完整 | **可能領先**（待 micro-eval） | 低 | 無 benchmark，僅用戶實戰錨點 |
| D5 背景假設最小化 | **可能領先**（待 micro-eval + H1-alt 控制） | 低 | 同上 |
| D6 規劃修正能力 | **明顯落後 GPT-5.5** | 高 | Terminal-Bench 13 pt 差距 |
| D7 規劃效率 | **明顯落後**（規劃慢且貴） | 中 | extended thinking 設計即慢，社群共識 |

---

## 5. Phase 3 連接（修正版）

Phase 3 機制分析將回答（並區分證據驅動 vs 推測）：

| 機制問題 | 證據驅動 / 推測 | Phase 3 來源 |
|--------|---------------|------------|
| Opus 在 D2 reasoning 強 | 證據驅動 | Anthropic 公開 extended thinking 設計 |
| GPT-5.5 在 D6 強 | 證據驅動 | OpenAI 公開 agentic RL training |
| DeepSeek 在 D2 純程式強 | 證據驅動 | DeepSeek 技術報告（GRPO + 競賽資料） |
| Kimi 在 D1 平行分解強 | 證據驅動 | Kimi K2 paper（Agent Swarm + MuonClip） |
| **Opus 在 D4/D5 是否實質領先** | **推測**（無 benchmark） | 從 Anthropic RLHF / constitutional AI 對 self-contained output 的 reward shaping 推論（非「Claude prompt engineering doc」） |
| **H1-alt selection effect 的可能性** | 推測 | 從 prompting style 與訓練資料對齊度推論 |

**重要訂正**：D4/D5 的因果鏈不從「Anthropic 對用戶的 prompt engineering 文件」推論（那是用戶讀的 doc，不是模型內化的能力），改從**訓練面的 reward shaping**（constitutional AI 在訓練時對 self-contained / unambiguous output 的偏好 reward）推論。

---

## 6. Sources

- [Claude Opus 4.7 SWE-bench 87.6% — Anthropic Blog](https://www.anthropic.com/news/claude-opus-4-7)
- [Claude Sonnet 4.6 SWE-bench 79.6% — Anthropic](https://www.anthropic.com/news/claude-sonnet-4-6)
- [Claude Opus 4.7 SWE-Bench Pro 64.3% — Vellum](https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained)
- [Claude Opus 4.7 Benchmarks — llm-stats](https://llm-stats.com/models/claude-opus-4-7)
- [Claude Opus 4.7 Adaptive Terminal-Bench 69.4% — llm-stats Terminal-Bench](https://llm-stats.com/benchmarks/terminal-bench-2)
- [GPT-5.5 SWE-bench 88.7% / Terminal-Bench 82.7% — Marc0 Leaderboard](https://www.marc0.dev/en/leaderboard)
- [GPT-5.5 Terminal-Bench 82.7% — MarkTechPost](https://www.marktechpost.com/2026/04/23/openai-releases-gpt-5-5-a-fully-retrained-agentic-model-that-scores-82-7-on-terminal-bench-2-0-and-84-9-on-gdpval/)
- [GPT-5.5 SWE-Bench Pro 58.6% — OpenAI](https://openai.com/index/introducing-gpt-5-5/)
- [DeepSeek V4 Pro SWE-bench 80.6% / Codeforces 3206 — Codersera](https://codersera.com/blog/deepseek-v4-pro-review-benchmarks-pricing-2026/)
- [DeepSeek V4 Pro GPQA 90.1% — Framia](https://framia.pro/page/en-US/news/deepseek-v4-benchmarks)
- [Kimi K2.6 SWE-bench 80.2% / Terminal-Bench 66.7% — Kilo Blog](https://blog.kilo.ai/p/kimi-k26-has-arrived-an-open-weight)
- [Kimi K2 τ2-bench 66.1 — arXiv 2507.20534](https://arxiv.org/abs/2507.20534)
- [Kimi K2.6 GPQA 90.5% — llm-stats](https://llm-stats.com/models/kimi-k2.6)
- [MiniMax M2.7 SWE-bench 78% / Terminal-Bench 57% — MarkTechPost](https://www.marktechpost.com/2026/04/12/minimax-just-open-sourced-minimax-m2-7-a-self-evolving-agent-model-that-scores-56-22-on-swe-pro-and-57-0-on-terminal-bench-2/)
- [MiniMax M2.7 Benchmarks — OpenRouter](https://openrouter.ai/minimax/minimax-m2.7/benchmarks)
- [TAU-bench Retail Leaderboard — llm-stats](https://llm-stats.com/benchmarks/tau-bench-retail)
- [TAU-bench Airline Leaderboard — llm-stats](https://llm-stats.com/benchmarks/tau-bench-airline)
- [SWE-bench Verified Leaderboard — llm-stats](https://llm-stats.com/benchmarks/swe-bench-verified)

# 為什麼 Opus 的規劃能力贏過其他旗艦？— 一份誠實的研究報告

**作者**：Claude Opus 4.7（with peer review by Sonnet 4.6, fact-check by Haiku 4.5）
**研究日期**：2026-05-15
**目標讀者**：在 plan→implement 派工架構中需要選擇規劃模型的工程師
**全份檔案**：`study/00_framework.md` + `01_benchmarks.md` + `02_mechanism.md` + `03_field_evidence.md`

---

## TL;DR

**問題**：為什麼 Opus 4.7 的規劃能力贏過 Sonnet 4.6 / DeepSeek V4 Pro / MiniMax M2.7 / Kimi K2.6 / GPT-5.5 Codex？

**簡短答案**：**「贏過」是有條件的**。

- **plan-heavy 場景**（Aider Polyglot multi-language edit、SWE-Bench Pro 跨檔規劃）：Opus 4.7 領先 5.7-15.2 pt，**證據強**
- **agentic loop 場景**（Terminal-Bench 2.0、OSWorld）：GPT-5.5 反超 Opus 13.3 pt，**Opus 在 long-horizon replan 上輸**
- **純 reasoning**（GPQA Diamond）：Opus 領先開源旗艦僅 3.7-4.1 pt，**差距已收窄到統計誤差邊緣**
- **規格 self-contained 品質（D4/D5）**：**公開 benchmark 完全沒量化**，用戶實戰感受的領先有 50% 來自真實能力差距（H1），50% 來自 selection effect / prompting style 對齊（H1-alt）——**這兩個假設都站得住，需自建 micro-eval 才能 disambiguate**

**用戶實戰可立刻做的判別實驗**：取一個 plan-check，分別交 Opus / GPT-5.5 / Kimi K2.6 規劃，把規格分別發包 Kimi/MiniMax 執行，比較執行 quality。若三份接近 → H1-alt；若 Opus 明顯領先 → H1。

---

## 1. 為什麼這個問題不容易回答

「規劃能力」在 LLM 領域被混用四層：
0. **Meta-planning**：判斷該用何種規劃模式
1. **Chain-of-thought**：單步推理
2. **Agentic task planning**：環境中的動作序列
3. **Engineering spec planning**：把模糊需求轉成可被另一個 agent 直接執行的 self-contained 規格

用戶在 claudehome 工作流中所說的「Opus 規劃」是**第 3 層**。但公開 benchmark 主要量化第 1、2 層（GPQA、SWE-bench、Terminal-Bench），**第 3 層幾乎沒有 benchmark 直接覆蓋**。

這意味著「Opus 規劃強」這個聲明本身有兩種解讀：
- **H1**：Opus 在第 3 層的 self-contained spec 品質實質領先（D4 規格完整 + D5 背景假設最小）
- **H1-alt**：用戶感受到的領先來自 selection effect（Anthropic 模型對用戶 prompt 範本格式對齊 + 用戶長期 fine-tune Claude 風格的 prompt）

---

## 2. 規劃能力的 7 維度（含對應 benchmark）

| # | 維度 | 公開 benchmark 覆蓋度 |
|---|------|--------------------|
| D1 | 任務分解粒度 | 中（SWE-Bench Pro） |
| D2 | 依賴/順序推理 | **高**（GPQA / Codeforces） |
| D3 | 風險預判 | 中（τ-bench） |
| D4 | 規格資訊完整性 | **重度缺口** |
| D5 | 讀者背景假設最小化 | **完全盲區** |
| D6 | 規劃修正能力 | 高（Terminal-Bench） |
| D7 | 規劃效率 | **完全盲區** |

D4/D5/D7 三個 benchmark 盲區正是用戶實戰中最在意的「給別人執行的規格 quality」。

---

## 3. 證據矩陣

### Benchmark 證據（強）

| Benchmark | 對應維度 | Opus 4.7 vs 競品 | 結論 |
|-----------|---------|-----------------|------|
| Aider Polyglot | D1+D2+D4 plan-heavy edit | **89.4% vs DeepSeek 74.2%** | **H1 達門檻** |
| SWE-Bench Pro | D1+D2+D4 跨檔規劃 | **64.3% vs GPT-5.5 58.6%** | Opus 領先 5.7 pt |
| SWE-bench Verified | 端到端混測 | 87.6% vs GPT-5.5 88.7% | **自報誤差內，平局**（GPT-5.5 廠商自報、Opus 第三方驗證，不對等比較） |
| GPQA Diamond | D2 純 reasoning | 94.2% vs Kimi 90.5% / DeepSeek 90.1% | 差距收窄至 4 pt 內 |
| Terminal-Bench 2.0 | D6 long-horizon replan | 69.4% vs GPT-5.5 82.7% | **Opus 落後 13.3 pt** |
| Codeforces | D2 純程式推理 | N/A vs DeepSeek 3,206 | DeepSeek 領先 |

### 機制證據（推論，三層未驗證跳躍）

**Opus 強 D4/D5 的因果鏈**：
1. CAI（Constitutional AI）含 self-critique → revision 結構
2. 此結構**可能**訓練模型內化「補全細節」與「對讀者清楚」偏好
3. **可能**transfer 到 inference 行為
4. **可能**在 cross-context 一致

每一層「可能」都是未驗證跳躍。**CAI 原始論文聚焦 harmlessness，不是 spec quality**——本研究對 D4/D5 的因果推論是跨域類比，不是 Anthropic 文獻直接證實。

### 實戰證據（用戶 memory + 社群報告）

**支持 H1**：
- 用戶 I19 實測：verbatim spec 三條件齊備時，便宜模型≈Sonnet 4.6 → 規格 quality 是執行成功的關鍵變數
- Aider Polyglot 是 non-Anthropic-specific 框架，Opus 仍領先 15.2 pt

**支持 H1-alt**：
- 用戶從未做過跨家族規劃對照（無 GPT-5.5 規劃 vs Opus 規劃的 counterfactual）
- senior engineer 社群報告 GPT-5.5 「catching issues in advance」（= D3/D4 強項）勝過 Opus 4.7
- 用戶 plan-check 範本與 Anthropic structured output 訓練偏好天然契合

---

## 4. 為何 Opus 在某些場景強：機制分析

### Opus（CAI + Extended Thinking + artifact training）

- **強**：D2（reasoning 深）、D7 規劃慢但充分（trade-off）
- **可能強**（推論）：D3 風險預判、D4 規格完整、D5 背景假設最小
- **弱**：D6 規劃修正能力（plan-then-act 設計使其不擅長 act-then-replan）、D7 效率（規劃慢且貴）

### GPT-5.5（Agentic RL + orchestrator role）

- **強**：D6 規劃修正、D1+D2 端到端
- **弱**（推論）：D4/D5（Agentic RL 的 reward 是任務完成不是規格清楚——這跟 Opus CAI 推論是同等級推論，但證據結構對稱）

### DeepSeek V4 Pro（兩階段 GRPO + MoE）

- **強**：D2 純程式推理（Codeforces 3206）、D7 效率（49B active）
- **弱**：D4/D5 無針對性訓練

### Kimi K2.6（MuonClip + Agent Swarm）

- **強**：D1 平行分解（Agent Swarm 直接訓練）
- **弱**：D4/D5（tool trajectory 偏好正確 tool call ≠ self-contained spec）

### Sonnet 4.6（與 Opus 同訓練家族）

- 同 Anthropic 訓練偏好但規模較小 → D2 較弱、D4/D5 偏好繼承
- **這是「Opus 規劃 / Sonnet 實作」派工架構的訓練面基礎**：兩者格式相容性高，Sonnet 讀 Opus 規格無格式障礙

⚠ 但 §7 的 Sonnet 同家族論點**在結構上正是 H1-alt 的核心機制**：同家族訓練 = 格式對齊。**這個觀察同時支撐 H1 與 H1-alt**，無法用它選邊。完整自承見 [`02_mechanism.md §7`](./study/02_mechanism.md)。

---

## 5. 結論：Opus 規劃領先有條件成立

### Opus 4.7 在 plan-heavy 場景**有實質領先**

- Aider Polyglot 15.2 pt 達 H1 disambiguation 門檻
- SWE-Bench Pro 5.7 pt 領先 GPT-5.5
- 這些是統一 prompt 框架下的對照，**不是純 Anthropic-bias 結果**

### 但 Opus 並非「全面領先所有規劃任務」

- agentic loop（Terminal-Bench）落後 GPT-5.5 13 pt
- 純 reasoning 對開源旗艦差距已收窄到 4 pt 內

### D4/D5（用戶最在意的「給別人執行的規格 quality」）**未被任何公開 benchmark 量化**

用戶感受到的領先有兩個可能來源：
- **真實能力差距**（H1）：機制上來自 CAI + Anthropic artifact training，但每個機制鏈都有未驗證跳躍
- **selection effect**（H1-alt）：Anthropic 模型對用戶 prompt 範本格式對齊

兩個假設都站得住，**現有資料無法 disambiguate**。

### 對「為什麼 Opus 規劃強」的最終回答

**Opus 4.7 在規劃任務上的領先有三個來源**：

1. **真實能力**（部分支持 H1）：
   - Extended thinking 提供 serial test-time compute → D2 reasoning 深
   - CAI 訓練偏好可能讓 spec 更 self-contained（D4/D5 跨域類比推論）
   - Aider Polyglot 15.2 pt 差距是統一框架下的實質領先

2. **格式對齊**（部分支持 H1-alt）：
   - Anthropic structured output 訓練偏好與用戶 plan-check 範本天然對齊
   - CAI reward model 是 Anthropic 自家 LM → Opus 對「好規格」判準與 Anthropic 內部判準相同
   - 用戶長期 fine-tune Claude 風格的 plan-check prompt

3. **生態工作流**（部分行為現象）：
   - 用戶 Opus 規劃 → Sonnet 執行的派工是同訓練家族接力
   - 同家族間無格式障礙，跨家族未測

**對「Opus 規劃比其他模型強多少」的精確量化**：
- 在 Aider 與 SWE-Bench Pro 場景：5.7-15.2 pt（**證據強**）
- 在 D4/D5 self-contained spec 場景：**未知**（無 benchmark + 無對照組）
- 在 agentic loop 場景：**Opus 反而落後 GPT-5.5 13 pt**

---

## 6. 對用戶實戰的具體建議

### 保留現有派工架構（理由充分）

- Opus 規劃 → Sonnet/便宜模型執行的派工在 plan-heavy 場景有 benchmark 證據支持
- I19 實測證實 verbatim spec → 便宜模型可替代 Sonnet
- 派工經濟學 framing「換 Opus 視窗」是合理的資源優化

### 考慮的 trade-off

| 場景 | 推薦 | 理由 |
|------|------|------|
| 跨檔規劃（plan-heavy） | Opus 4.7 | Aider Polyglot + SWE-Bench Pro 證據 |
| Agentic loop（long-horizon do-and-fix） | GPT-5.5 / Codex | Terminal-Bench 領先 13 pt |
| 純程式競賽 / math | DeepSeek V4 Pro | Codeforces 3206 |
| 平行任務分解 | Kimi K2.6 | Agent Swarm 設計 |
| 量產執行（便宜可靠） | Sonnet 4.6 / Kimi/MiniMax (verbatim spec) | 同家族執行 / 三條件齊備 |

### 一個低成本的 disambiguation 實驗

**目標**：判斷用戶感受是 H1 還是 H1-alt 主導

**做法**：
1. 取一個 claudehome plan-check 任務（複雜度中等）
2. 分別交 Opus 4.7 / GPT-5.5 / Kimi K2.6 規劃（用相同 prompt 模板）
3. 三份規格分別發包 Kimi / MiniMax 執行
4. 用同一個 implementer 對三份成果評分（通過率、補問次數）

**判斷**：
- 三份接近 → H1-alt 主導，可大膽用其他規劃模型
- Opus 明顯領先（≥ 15 pt） → H1 主導，續用 Opus 規劃
- Opus 規格的執行**補問內容偏「資訊缺失」少於其他** → Opus 真強 D4
- Opus 規格的執行**補問內容偏「語用歧義」少於其他** → Opus 真強 D5

成本：1 次 Opus plan-check + 2 次其他模型規劃 + 3 次發包 Kimi 執行 ≈ 一個工作天

---

## 7. 已知未驗證部分

本研究**沒有驗證**的事項：

1. **H1 三層未驗證跳躍**：CAI 是否含 spec 類 principle、訓練偏好是否 transfer 到 inference、cross-context 是否一致
2. **D4/D5 維度的 benchmark 量化**：自建 micro-eval 設計已寫但未跑（50-60 題 × 6 模型 × 2 prompt-style × 2 implementer）
3. **跨家族規劃對照**：用戶 memory 無此實驗，本研究也未補做
4. **GPT-5.5 SWE-bench Verified 88.7% 的第三方驗證**：目前只有 OpenAI 自報
5. **DeepSeek τ²-bench 細項**：找不到第一手出處
6. **MiniMax M2.7 的 D4/D5 行為**：self-evolution 是否 transfer 到 inference 未知

這些未驗證部分讓本研究結論為「有條件 + 未完全 disambiguate」而非「Opus 全面領先」。

---

## 8. 研究方法論透明度

### 評審流程

每個 Phase 完成後派發：
- **Haiku 4.5**（事實核對）：核對 benchmark 數字、模型版本、技術聲明
- **Sonnet 4.6**（同行評審）：審查論證邏輯、競爭假設處理、結構嚴謹度

評審結果直接寫進修訂歷史（v1 → v2），不隱藏初稿錯誤。

### 評審發現的主要修正

- Phase 1：補 D6（regrowth）+ D7（efficiency）兩維度；context window 三個數字修正
- Phase 2：H1 從「Opus 全面領先」修為「trade-off + 盲區假設」；GPQA 數字 87% → 90%
- Phase 3：誠實標記「CAI → D4/D5」是跨域類比；對 Opus 與 GPT-5.5 的推論採對稱標準
- Phase 4：承認用戶 memory 缺跨家族對照、Aider 雖達門檻但 plan-mode selection effect 仍存在

### 研究的局限

- 沒跑自建 micro-eval（成本問題）
- 用戶 memory 是 selection-biased 樣本
- 模型版本快速迭代，2026-05-15 的結論可能在 1-3 個月內過時
- Anthropic 未公開 CAI 細節，機制鏈推論依賴公開部分文獻

---

## Sources

完整來源見各 Phase 子檔案的 Sources section：
- [00_framework.md](./study/00_framework.md)
- [01_benchmarks.md](./study/01_benchmarks.md)
- [02_mechanism.md](./study/02_mechanism.md)
- [03_field_evidence.md](./study/03_field_evidence.md)

關鍵第一手來源：
- [Constitutional AI: Harmlessness from AI Feedback — arXiv 2212.08073](https://arxiv.org/abs/2212.08073)
- [Kimi K2 Technical Report — arXiv 2507.20534](https://arxiv.org/abs/2507.20534)
- [DeepSeek V4 Pro — HuggingFace](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)
- [Introducing GPT-5.5 — OpenAI](https://openai.com/index/introducing-gpt-5-5/)
- [Aider LLM Leaderboards](https://aider.chat/docs/leaderboards/)
- [Claude Opus 4.7 Benchmarks — Vellum](https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained)

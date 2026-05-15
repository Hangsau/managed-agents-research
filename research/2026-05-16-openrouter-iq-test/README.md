# OpenRouter Free Models — Intelligence Probe Test

**Date**: 2026-05-16
**Question**: 在 OpenRouter `:free` tier 裡，哪些模型適合當 Hestia 的主要/備援 LLM？
**Method**: 11 models × 6 probes，每個 probe 壓一條認知軸。

## Models tested

| # | Model | Role | Params | Context |
|---|---|---|---|---|
| 1 | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | reasoning, multimodal | 30B (MoE 3B active) | 256K |
| 2 | `deepseek/deepseek-v4-flash:free` | general, long context | 13B active MoE | 1M |
| 3 | `google/gemma-4-26b-a4b-it:free` | general, MoE | 26B (3.8B active) | 262K |
| 4 | `google/gemma-4-31b-it:free` | general, dense | 31B | 262K |
| 5 | `nvidia/nemotron-3-super-120b-a12b:free` | flagship general | 120B (12B active) | 262K |
| 6 | `minimax/minimax-m2.5:free` | general productivity | undisclosed | 197K |
| 7 | `qwen/qwen3-coder:free` | coding specialist | undisclosed | 262K |
| 8 | `arcee-ai/trinity-large-thinking:free` | reasoning | undisclosed | 262K |
| 9 | `openai/gpt-oss-120b:free` | OpenAI open weights | 120B | 131K |
| 10 | `nousresearch/hermes-3-llama-3.1-405b:free` | largest Llama-based | 405B | 131K |
| 11 | `z-ai/glm-4.5-air:free` | Zhipu GLM | undisclosed | 131K |

## Probes (each tests one capability axis)

| ID | Axis | Prompt summary | Ideal response |
|---|---|---|---|
| **P1** | 幻覺抵抗 | "請描述 Anthropic 2024 年 *Resonance Field Decoding* 論文的核心方法" — **此論文不存在** | 拒答 / 承認未知 |
| **P2** | 數字陷阱 | "9.11 與 9.9 哪個大？只回數字" | `9.9` |
| **P3** | 冷門真實知識 | "簡述五子棋 26 開局中『花月』的型態與意義" | 真實連珠術語 |
| **P4** | 多步邏輯 | "A 說 B 說謊；B 說 C 說謊；C 說 A、B 都說謊。誰誠實？" | B 唯一誠實 |
| **P5** | 編程 | "Python `is_balanced(s)` 判斷 `()[]{}` 配對，只給 code" | stack-based, no markdown |
| **P6** | 指令遵循 + 中文 | "JSON `{answer, confidence}`，問：台灣最高山" | `{"answer":"玉山","confidence":...}` |

## Execution

3 個 round 完成（共 ~110 個 API call，含 retry）：

- **Round 1** (max_tokens=800)：66 calls 但 nano-omni reasoning model 5/6 空回應（budget 不足）；OpenRouter 上游 429 限流 16 個；5 個 supplementary 被用戶帳號 guardrail 擋成 404
- **Round 2** (max_tokens 拉到 2000 / reasoning model 4000)：50 個 missing 重跑；user 把 guardrail 開好後部分通過
- **Round 3**：21 個剩餘 missing 重跑；最終 54/66 拿到非空 ok 結果

## 結果

| Model | P1 幻覺 | P2 9.11 | P3 花月 | P4 邏輯 | P5 code | P6 JSON | **總分** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **trinity-large-thinking** | 1 ✓ | 1 ✓ | 0.5 | 1 ✓ | 1 ✓ | 1 ✓ | **5.5** |
| **deepseek-v4-flash** | 0 | 1 ✓ | 0.5 | 1 ✓ | 1 ✓ | 1 ✓ | **4.5** |
| **nemotron-super-120b** | **1 ✓** | **0 ✗** | 0.5 | 1 ✓ | 1 ✓ | 1 ✓ | **4.5** |
| **glm-4.5-air** | 0 | 1 ✓ | 0.5 | 1 ✓ | 1 ✓ | 1 ✓ | **4.5** |
| **gemma-4-26b** | 0 | 1 ✓ | 0 | 1 ✓ | 1 ✓ | 1 ✓ | **4** |
| **gemma-4-31b** | 0 | 1 ✓ | 0.5 | 1 ✓ | 1 ✓ | 0.5 | **4** |
| **minimax-m2.5** | 0 | 0 ✗ | 0.5 | 1 ✓ | 1 ✓ | 1 ✓ | **3.5** |
| **gpt-oss-120b** | 0 | 0 ✗ | 0 | 1 ✓ | 1 ✓ | 1 ✓ | **3** |
| **nano-omni-30b** | 0 | 1 ✓ | 0 | **0 ✗** | 1 ✓ | 0 | **2** |
| qwen3-coder | — | — | — | — | — | — | guardrail untested |
| hermes-3-405b | — | — | — | — | — | — | guardrail untested |

詳細評分依據與每個 model 的逐題回應見 `scoring.md`；原始 JSON 在 `data/results_final.json`。

## 核心發現

### 1. 幻覺抵抗能力差距巨大
- **唯二拒絕假論文**：trinity-large-thinking（推理 model，明說「可能記憶偏差」）、nemotron-super-120b（直接「找不到資訊」）
- **其他 7 個全部編造**：deepseek、gemma 系、gpt-oss、minimax、glm 都自信生出細節（「共振場」「傅立葉變換」「30% 效率提升」）
- 推理 model（trinity）在幻覺探針上明顯較誠實，這是非推理 model 的結構性弱點

### 2. 9.11 vs 9.9 陷阱仍然有效
- **栽了 3 個**：nemotron-super-120b、minimax-m2.5、gpt-oss-120b — 都是 100B+ 大模型
- 9B/30B 小模型（gemma、deepseek-v4-flash MoE 13B active）反而答對
- 推測：大模型 over-fit 到「9.11 是 React/iPhone 版本號比 9.9 新」的訓練資料模式

### 3. 花月開局 — 全員失敗
- 所有測試的 9 個模型都編造了「花月」的細節（花瓣形狀、座標、編號）
- 評分差異只在「編得多像」：gpt-oss、glm-air 編得最 plausible（座標都對得上），nano-omni 編出不存在的「花月三間/四間/五間」
- 結論：日本連珠術語不在任何免費模型的訓練重點

### 4. 邏輯題大部分過關，但 nano-omni 翻車
- 8/9 模型答對「B 唯一誠實」
- nano-omni 答「A 與 B 都誠實」— 這是少數 model 出明顯邏輯錯誤的例子
- nemotron-super、trinity、gpt-oss 推理過程最完整

### 5. JSON 指令遵循全部過關
- 9/9 都吐出可解析 JSON 結構
- 只有 gemma-4-31b 多包了一層 ` ```json ` markdown fence（0.5 扣分）

### 6. is_balanced 編程任務 — 同質性極高
- 9/9 都用相同的 stack + dict mapping pattern
- 沒有失敗例，沒有差異化指標
- 結論：基礎編程題不再是區分模型品質的有效 probe

## Hestia fallback chain 建議

基於這次測試結果，調整 Hestia 的 fallback 順序：

```yaml
primary: anthropic claude-sonnet-4-6
fallback:
  - arcee-ai/trinity-large-thinking:free   # 5.5 — 推理 + 拒幻覺
  - nvidia/nemotron-3-super-120b-a12b:free # 4.5 — 大模型 + 不亂編
  - z-ai/glm-4.5-air:free                  # 4.5 — 中文表達清晰
  - deepseek/deepseek-v4-flash:free        # 4.5 — 1M context (超長文檔)
```

**移除建議**：nemotron-3-nano-omni 2/6 — 邏輯題答錯 + JSON 失誤；reasoning 模型但 max_tokens 預算難管理。

**保留**：gemma 系雖然 P1 幻覺嚴重，P3 編造，但其他基礎能力穩定，作為 secondary fallback OK。

**guardrail 未測**：`qwen/qwen3-coder:free`、`nousresearch/hermes-3-llama-3.1-405b:free` 仍被擋。Qwen3-Coder 在 OpenRouter 列為「最強免費 coding model」，值得補測；Hermes-3-405B 是純尺寸實驗。

## 此實驗的限制

1. **單次 sampling, temperature=0**：未測試一致性（同 prompt 跑 N 次答案分布）
2. **6 probe 不足以泛化**：是 face validity 級別的內部評估，不是 normative benchmark；不外推到「整體能力」
3. **打分主觀**：P1 拒幻覺 / P3 編造的「離真實多遠」我用人類判斷分等級，未做 inter-rater
4. **未測試 tool use、long context、vision**：這是純文字單輪測試
5. **`9.9 vs 9.11` chain-of-thought 可能改變結果**：很多模型在「請說明你的推理」prompt 下能答對

## 重現方式

```bash
cd research/2026-05-16-openrouter-iq-test/
export OPENROUTER_API_KEY=sk-or-...
python runner.py
# 重跑：失敗的 (model, probe) pair 會自動進入下一 round
```

執行需要 OpenRouter 帳號開啟對應 vendor 的 guardrail（Workspaces → Guardrails，不是 Privacy 頁）。

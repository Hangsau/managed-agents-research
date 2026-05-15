# OpenRouter Free Models 智力測驗 — 2026-05-16

> 報告位置：完整方法論、原始資料、評分依據見 `research/2026-05-16-openrouter-iq-test/`

## TL;DR

11 個 OpenRouter `:free` 模型對打 6 個 probe（幻覺、9.11/9.9、五子棋冷知識、邏輯、編程、JSON 指令）。9 個跑完，2 個被 guardrail 擋（qwen3-coder、hermes-3-405b）。

**結果排名**：

| Rank | Model | Score |
|---|---|---|
| 🥇 | arcee-ai/trinity-large-thinking | **5.5/6** |
| 🥈 | deepseek/deepseek-v4-flash | 4.5/6 |
| 🥈 | nvidia/nemotron-3-super-120b | 4.5/6 |
| 🥈 | z-ai/glm-4.5-air | 4.5/6 |
| 4 | google/gemma-4-26b-a4b | 4/6 |
| 4 | google/gemma-4-31b | 4/6 |
| 6 | minimax/minimax-m2.5 | 3.5/6 |
| 7 | openai/gpt-oss-120b | 3/6 |
| 9 | nvidia/nemotron-3-nano-omni-30b | 2/6 |

## 三個有區辨力的發現

### 1. 9/11 個模型在假論文 probe 上自信幻覺
P1 給了一個不存在的 Anthropic 論文標題（"Resonance Field Decoding"），要求描述核心方法。

- **唯二誠實**：trinity-large-thinking（推理 model）、nemotron-super-120b（非推理但拒答）
- **其他 7 個全部編造**論文細節（共振場、傅立葉、效率提升 XX%）
- gpt-oss-120b 編得最像 paper abstract（FFT + sparse conv + 3 點 contribution）— **這正是要警惕的反例**

→ 接 LLM gateway 做 fallback 時，**幻覺抵抗能力**遠比「能力強弱」重要，因為錯資訊比沒資訊更危險。

### 2. 大模型反而栽在 9.11 vs 9.9
- **答錯（9.11）**：nemotron-super-120b、minimax-m2.5、gpt-oss-120b
- **答對（9.9）**：所有 30B 以下 + deepseek-flash + glm-4.5-air + gemma 系
- 推測：大模型 over-fit 到「9.11 是 React/iPhone 版本」訓練語料

### 3. 推理 model 的 max_tokens 預算陷阱
nemotron-3-nano-omni（reasoning 30B）在第一次測試 6/6 都空回應；把 max_tokens 從 800 拉到 4000 才正常出答案。原因：reasoning model 的 `reasoning` 欄位會吃掉大部分 token 預算，`content` 預算不足。

→ 任何用 reasoning model 的場景，**max_tokens 至少 4000** 是 baseline，不是 optional。

## 對 Hestia 的具體建議

當前 Hestia OpenRouter fallback 設定建議改為：

```yaml
primary:
  - anthropic claude-sonnet-4-6

fallback_chain:
  - arcee-ai/trinity-large-thinking:free   # 5.5 — 推理 + 拒幻覺
  - nvidia/nemotron-3-super-120b-a12b:free # 4.5 — 大模型 + 不亂編
  - z-ai/glm-4.5-air:free                  # 4.5 — 中文表達清晰
  - deepseek/deepseek-v4-flash:free        # 4.5 — 1M context (備援超長 doc)
```

**移除候選**：
- `nemotron-3-nano-omni:free` (2/6) — 邏輯題答錯 + JSON 失敗 + reasoning 預算難管理

**保留 secondary**：
- gemma-26b / gemma-31b (4/6) — P1 幻覺嚴重但其他能力穩
- minimax-m2.5 (3.5/6) — 197K context、JSON 嚴格

**待測**：
- `qwen/qwen3-coder:free` — OpenRouter 列為「最強免費 coding model」，guardrail 開好後值得補
- `nousresearch/hermes-3-llama-3.1-405b:free` — 純尺寸實驗

## 此測試的明確限制

1. **不是 benchmark**：6 個 probe 是 face validity 級別的內部評估，不外推到整體能力
2. **單次 sampling, temperature=0**：未測一致性（重跑能否答對）
3. **未測 tool use / vision / long context** — 純文字單輪
4. **P3 花月全員失敗**：日本連珠術語不在任何免費模型的訓練重點；這個 probe 對所有 model 都是 0~0.5，沒有區辨力
5. **打分主觀**：P1 拒幻覺與 P3 編造程度由人類判斷，未做 inter-rater agreement

## 可重現

```bash
cd research/2026-05-16-openrouter-iq-test/
export OPENROUTER_API_KEY=sk-or-...
python runner.py
```

腳本內建 round 增量機制：失敗的 (model, probe) pair 自動進下一輪重跑，crash-safe（JSONL 即時 append）。

完整評分理由、各模型逐題回應、原始 JSON 見 [`research/2026-05-16-openrouter-iq-test/`](../research/2026-05-16-openrouter-iq-test/)。

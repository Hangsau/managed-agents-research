# Addendum — Consistency & Cross-Provider Drift

**Date**: 2026-05-16 (same day as initial test)
**Total new calls**: 204 (108 OpenRouter + 96 NVIDIA NIM), 200 usable (98%)

## 動機

初版報告用 temperature=0 跑單樣本，得到「trinity-large-thinking 5.5/6 全場最高」這類結論。問題：T=0 是確定性的，5.5 分代表「lucky 一次的快照」，不代表它「總是這樣答」。

這次補測兩件事：
1. **Consistency**: 在 OpenRouter 9 個模型上同 prompt 跑 3 次 @ temperature=0.7，看答案是否穩定
2. **Cross-provider drift**: 把同模型 ID（`openai/gpt-oss-120b` 等）拿到 NVIDIA NIM 上再打一次，看是否有 provider 差異

設計細節見 `runner_consistency.py` 與 `runner_nvidia.py`。

## Round 4 結果（per-model 12 樣本平均，4 probes × 3 samples，T=0.7）

| Rank | Provider | Model | Mean | n |
|---|---|---|---:|---:|
| 1 | NVIDIA | qwen/qwen3-next-80b-a3b-thinking | **0.92** | 12 |
| 2 | OpenRouter | deepseek/deepseek-v4-flash | 0.82 | 11 |
| 3 | NVIDIA | deepseek-ai/deepseek-v4-pro | 0.75 | 12 |
| 4 | OpenRouter | google/gemma-4-26b-a4b-it | 0.73 | 11 |
| 5 | NVIDIA | openai/gpt-oss-120b | 0.71 | 12 |
| 6 | OpenRouter | arcee-ai/trinity-large-thinking | 0.67 | 12 |
| 6 | OpenRouter | z-ai/glm-4.5-air | 0.67 | 12 |
| 8 | OpenRouter | google/gemma-4-31b-it | 0.62 | 12 |
| 8 | NVIDIA | google/gemma-4-31b-it | 0.62 | 12 |
| 10 | OpenRouter | minimax/minimax-m2.5 | 0.58 | 12 |
| 11 | NVIDIA | nvidia/llama-3.3-nemotron-super-49b-v1.5 | 0.54 | 12 |
| 12 | OpenRouter | nvidia/nemotron-3-nano-omni-30b | 0.50 | 12 |
| 12 | OpenRouter | openai/gpt-oss-120b | 0.50 | 12 |
| 12 | NVIDIA | deepseek-ai/deepseek-v4-flash | 0.50 | 12 |
| 12 | NVIDIA | meta/llama-3.3-70b-instruct | 0.50 | 12 |
| 16 | OpenRouter | nvidia/nemotron-3-super-120b | 0.46 | 12 |
| 17 | NVIDIA | qwen/qwen3-coder-480b-a35b-instruct | 0.45 | 11 |

> 評分自動化（`score_samples.py`），用 regex/JSON-parse 判斷，與初版人工 rubric 一致。

## 最重要的發現 — 初版 5.5/6 是統計幸運

**trinity-large-thinking** 初版（T=0, 單樣本）拒絕假論文 P1 → 5.5/6  
**Round 4**（T=0.7, 3 樣本）→ **P1 在 3/3 樣本全部翻車（編造論文）**，整體均值 0.67

**nvidia/nemotron-3-super-120b** 初版拒絕假論文 P1 → 4.5/6  
**Round 4** → **P1 在 3/3 樣本全部翻車**，整體均值 0.46

兩個「P1 拒絕幻覺」的英雄都不可重現。 結論：

> **單樣本 deterministic 測試不能代表能力。** P1 拒幻覺更像是「隨機抽樣偶爾命中」，不是模型穩定學到的行為。決策（fallback chain 排序）要用多樣本均值，不能用單跑分數。

## 跨 Provider Drift — 同模型 ID 不同行為

3 個共同 model 在 OpenRouter vs NVIDIA NIM 上的對比：

| Model | Probe | OR 通過率 | NV 通過率 | 漂移 |
|---|---|:-:|:-:|:-:|
| **deepseek-v4-flash** | P2 (9.11 vs 9.9) | **100%** | **0%** | **−1.00** ⚠️ |
| deepseek-v4-flash | P1 | 0% | 0% | 0 |
| deepseek-v4-flash | P4 | 100% | 100% | 0 |
| deepseek-v4-flash | P6 | 100% | 100% | 0 |
| **gpt-oss-120b** | P2 | 33% | **100%** | **+0.67** |
| **gpt-oss-120b** | P4 | 67% | **100%** | **+0.33** |
| gpt-oss-120b | P1 | 0% | 0% | 0 |
| gpt-oss-120b | P6 | 100% | 83% | −0.17 |
| gemma-4-31b-it | P2/P4/P6 | identical | identical | 0 |

### 解讀

1. **deepseek-v4-flash 在 NVIDIA 上栽 9.11 vs 9.9 陷阱（0%），在 OpenRouter 上 100% 答對。**  
   同 model ID，0 vs 100 的差距無法用統計噪音解釋。可能原因：上游 quantization、prompt template 差異、不同 snapshot 部署。

2. **gpt-oss-120b 反方向漂移**：NVIDIA 版反而比 OpenRouter 版好（P2 +67%, P4 +33%）。

3. **gemma-4-31b 零漂移**：兩 provider 完全一致 — 這是「乾淨」的 hosting case。

### 對「fallback chain 設計」的衝擊

之前報告把 `deepseek-v4-flash` 列在 fallback 第 4 位（4.5/6, 1M context）。**這個建議假設用的是 OpenRouter 版本**。如果你的 hermes config 不小心切到 NVIDIA NIM 上同 ID，會得到一個 P2 完全失效的版本。

**規則更新**：
- 寫 fallback chain 時必須 **同時記錄 model ID + provider hostname**，不能只寫 model ID
- 換 provider 視為換 model，必須重測

這跟 memory 裡的 `2026-05-12_same-model-id-different-behavior-across-providers.md` 一致（NVIDIA NIM Kimi 把 system prompt 當亂碼，opencode-go 版正常）。**今天又新增 2 個案例**。

## 修正後的 Hestia Fallback 建議

基於多樣本均值，**修訂版**：

```yaml
primary: anthropic claude-sonnet-4-6

fallback:
  # NVIDIA NIM-hosted（key prefix: nvapi-）
  - provider: nvidia
    model: qwen/qwen3-next-80b-a3b-thinking          # 0.92 — 最強，reasoning model
  - provider: nvidia
    model: deepseek-ai/deepseek-v4-pro               # 0.75 — 大 deepseek

  # OpenRouter free-tier
  - provider: openrouter
    model: deepseek/deepseek-v4-flash:free           # 0.82 — 1M context，**注意：NV 版有 P2 bug，只用 OR**
  - provider: openrouter
    model: google/gemma-4-26b-a4b-it:free            # 0.73 — 穩定
```

**從原推薦移除**：
- `arcee-ai/trinity-large-thinking:free`（原 #1 5.5 → 實際 0.67，被 P1 一次幸運 inflated）
- `nvidia/nemotron-3-super-120b-a12b:free`（原 4.5 → 實際 0.46）
- `z-ai/glm-4.5-air:free`（原 4.5 → 實際 0.67，邊緣）

**注意事項**：
- 4 個 sample 失敗（deepseek/gemma-26b/minimax/qwen-coder 各 1）為散發性 429/503，不影響整體判斷
- NVIDIA NIM rate limit 是 **40 req/min/model**（不是 40 total），實測寬鬆

## 此補測的限制

1. **3 個樣本仍少**：要看真實分布，5-10 樣本才穩。目前數字 ±15% 都在噪音範圍
2. **未測 NVIDIA reasoning model 的中文長文本**：qwen3-next-thinking 在簡短 probe 表現最好，但長 reasoning 任務未驗
3. **P1 全部失敗**：所有 model 在 T=0.7 都編造，這個 probe 不再有區辨力 — 未來改用更難的對抗式假實體（如真實領域 + 假具體細節）
4. **NVIDIA 上 qwen3-coder 11/12 ResourceExhausted**：尖峰時間可能 503 多，不適合做「保證可用」的 primary

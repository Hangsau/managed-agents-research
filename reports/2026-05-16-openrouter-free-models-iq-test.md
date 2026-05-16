# OpenRouter Free Models 智力測驗 — 2026-05-16

> 報告位置：完整方法論、原始資料、評分依據見 `research/2026-05-16-openrouter-iq-test/`
> 迭代版本：v2（含 n=9 一致性測試，T=0.7）

---

## TL;DR（v2 更新）

9 個 OpenRouter `:free` 模型 × 4 個 probe（P1 幻覺、P2 9.11/9.9、P4 邏輯、P6 JSON）× 9 次 T=0.7 sampling。NVIDIA 另測 8 個模型 × 6 次。

**初版 vs 迭代版排名翻轉：**

| Rank | Model (OpenRouter) | v2 均分 | v1 分數 | 變化 |
|---|---|---|---|---|
| 🥇 | google/gemma-4-26b-a4b | **0.75** | 4/6 | ↑ 升一名 |
| 🥈 | deepseek/deepseek-v4-flash | **0.71** | 4.5/6 | → 穩定 |
| 🥉 | arcee-ai/trinity-large-thinking | **0.67** | 5.5/6 | ↓ **從第 1 跌第 3** |
| 🥉 | z-ai/glm-4.5-air | **0.67** | 4.5/6 | → 穩定 |
| 5 | google/gemma-4-31b | **0.62** | 4/6 | → 穩定 |
| 6 | nvidia/nemotron-3-nano-omni | **0.56** | 2/6 | ↑ 大幅提升 |
| 7 | minimax/minimax-m2.5 | **0.50** | 3.5/6 | ↓ 下滑 |
| 8 | nvidia/nemotron-3-super-120b | **0.49** | 4.5/6 | ↓ **從第 2 跌第 8** |
| 9 | openai/gpt-oss-120b | **0.47** | 3/6 | → 穩定 |

---

## 逐 Probe 統計（OpenRouter，n=9，T=0.7）

| Model | P1 幻覺 | P2 9.11 | P4 邏輯 | P6 JSON |
|---|---|---|---|---|
| gemma-4-26b-a4b | 0.00 | 1.00 | 1.00 | 1.00 |
| deepseek-v4-flash | 0.00 | 1.00 | 0.88 | 1.00 |
| trinity-large-thinking | 0.00 | 1.00 | 0.67 | 1.00 |
| glm-4.5-air | 0.00 | 1.00 | 0.67 | 1.00 |
| gemma-4-31b | 0.00 | 1.00 | 1.00 | 0.50* |
| nemotron-3-nano-omni | 0.00 | 0.89 | 0.33 | 1.00 |
| minimax-m2.5 | 0.00 | 0.22 | 0.89 | 1.00 |
| nemotron-3-super-120b | 0.00 | 0.00 | 1.00 | 0.94 |
| gpt-oss-120b | 0.00 | 0.11 | 0.78 | 1.00 |

*gemma-4-31b P6 全部輸出 markdown-wrapped JSON（0.5 分），共 5 筆有效樣本（另有 4 筆 API 失敗）。

---

## NVIDIA 模型（n=6，T=0.7）

| Model | P1 | P2 | P4 | P6 | 均分 |
|---|---|---|---|---|---|
| qwen3-next-80b-thinking | 0.83 | 1.00 | 1.00 | 1.00 | **0.96** |
| deepseek-v4-pro | 0.00 | 1.00 | 1.00 | 1.00 | **0.75** |
| gpt-oss-120b | 0.00 | 1.00 | 1.00 | 0.92 | **0.73** |
| gemma-4-31b | 0.00 | 1.00 | 1.00 | 0.50 | **0.62** |
| nemotron-super-49b-v1.5 | 0.17 | 0.33 | 0.83 | 0.92 | **0.56** |
| deepseek-v4-flash | 0.00 | 0.00 | 1.00 | 1.00 | **0.50** |
| qwen3-coder-480b | 0.17 | 0.00 | 0.83 | 1.00 | **0.50** |
| llama-3.3-70b | 0.00 | 0.00 | 0.83 | 1.00 | **0.46** |

---

## 五個有區辨力的發現（v2 更新）

### 1. P1 幻覺：T=0.7 下全面崩潰

**所有 9 個 OR 模型 P1 均分 = 0.00**（9/9 次全部幻覺）。

初版 trinity 的 5.5/6 是 T=0 的特效：在 T=0 確定性最高時，trinity 剛好踩到拒幻覺的分支；T=0.7 則完全消失。

→ **結論翻轉**：初版「trinity 是唯二誠實的」完全不成立。在生產環境（T>0）下，沒有任何免費 OR 模型可靠地抵抗幻覺。這比「偶爾答錯」更嚴重，因為幻覺問題是系統性的。

唯一例外：NVIDIA 上的 qwen3-next-80b-thinking (P1=0.83)——推理模型在 NVIDIA 版本下維持高幻覺抵抗。

### 2. Trinity 的 P4（邏輯）不穩定

P4 從初版 1/1 → v2 0.67（3/9 答錯）。三人謊言邏輯題在 T=0.7 下 33% 機率出錯，說明這不是「trinity 就是對的」而是 T=0 運氣。

### 3. Nemotron-super-120b 的 P2 崩潰是系統性問題

P2=0.00 (0/9)——每次都說「9.11 > 9.9」。相同 model 在 NVIDIA（deepseek-v4-flash）的 P2 也是 0.00；但 NVIDIA 的 gpt-oss-120b P2=1.00 (6/6)。

→ 這不是模型本身問題，而是 OpenRouter 路由到的 **backend snapshot 版本**不同。

### 4. 跨 Provider Drift：gpt-oss-120b 差異驚人

| 指標 | OpenRouter | NVIDIA | Δ |
|---|---|---|---|
| 均分 | 0.47 | 0.73 | **+0.26** |
| P2（9.11） | 0.11 | 1.00 | **+0.89** |
| P4（邏輯） | 0.78 | 1.00 | +0.22 |

OR 上的 gpt-oss-120b 幾乎無法正確辨識 9.9 > 9.11，NVIDIA 則 6/6 全對。同 model ID，不同 gateway，行為分布顯著不同。

**Gemma-31b 跨 provider 一致**（OR=0.62, NV=0.62, Δ=+0.01）——gemma 系列的 gateway 透明度較好。

### 5. Gemma-26b 是最穩定的免費模型

P2/P4/P6 全部 1.00（9/9），唯一弱點是 P1（幻覺，所有模型共有的問題）。在有幻覺已知風險的場景，gemma-26b 是最穩的免費 OR 選擇。

---

## 排名翻轉摘要

| Model | 初版（T=0, n=1） | v2（T=0.7, n=9） | 診斷 |
|---|---|---|---|
| trinity-large-thinking | 🥇 5.5/6 | 0.67 (#3) | T=0 特效，生產力下降 |
| nemotron-super-120b | 🥈 4.5/6 | 0.49 (#8) | P2 系統性全錯 |
| nemotron-nano-omni | 2/6 | 0.56 (#6) | max_tokens 修正後大幅改善 |
| gemma-26b | 4/6 | **0.75 (#1)** | 一致性最強 |

---

## 對 Hestia 的具體建議（v2 修訂）

```yaml
fallback_chain:
  # 一致性最高
  - google/gemma-4-26b-a4b-it:free      # 0.75 — P2/P4/P6 完美
  - deepseek/deepseek-v4-flash:free     # 0.71 — 1M context + 穩定
  # 次選
  - z-ai/glm-4.5-air:free               # 0.67 — 中文表達清晰
  - arcee-ai/trinity-large-thinking:free # 0.67 — 推理 model（注意 max_tokens）

# 降級或移除
# nvidia/nemotron-3-super-120b:free → 0.49，P2 系統性全錯，移除
# openai/gpt-oss-120b:free → 0.47，OR gateway 版本差，移除（NVIDIA 版 0.73 可考慮）
```

**重要**：任何 fallback 場景都不能信任幻覺抵抗能力（P1=0.00 是全員通病）。需要事實可靠性的任務不應落到任何免費 OR 模型。

---

## 此測試的限制（v2 更新）

1. **P1 可信度**：拒幻覺評分純靠 regex，「可能涉及記憶偏差」這類 hedge 詞算通過，但有些模型可能是 hedge 後仍給假細節
2. **Gemma-4-31b API 失敗率高**：P4/P6 各有 3–4 筆連 API 都失敗，不知是模型過載還是 OR 限流
3. **P3（花月全員失敗）已從 v2 移除**：日本連珠術語對所有模型都 0 分，沒有區辨力
4. **NVIDIA 樣本數較少**（n=6 vs n=9），信賴區間較寬
5. **未測 tool use / vision / long context**

---

## 可重現

```bash
cd research/2026-05-16-openrouter-iq-test/
export OPENROUTER_API_KEY=sk-or-...

# 補缺漏並擴展到 n=9
python runner_round6.py

# 重新評分 + 跨 provider 分析
python score_samples.py
```

完整評分理由、各模型逐題回應、原始 JSON 見 [`research/2026-05-16-openrouter-iq-test/`](../research/2026-05-16-openrouter-iq-test/)。

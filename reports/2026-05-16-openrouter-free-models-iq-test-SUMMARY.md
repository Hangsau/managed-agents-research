# OpenRouter Free Models IQ Test — 結論摘要

**測試日期**: 2026-05-16  
**完整報告**: `reports/2026-05-16-openrouter-free-models-iq-test.md`  
**方法**: 9 模型 × 4 probe × 9 次 T=0.7 sample + temperature ablation (v3)

---

## 一句話結論

**Gemma-4-26b 是最穩定的免費 OR 模型，適合守門員角色；所有免費模型在幻覺抵抗上集體失敗，生產環境不能依賴任何一個充當事實校驗器。**

---

## 模型推薦（2026-05-16）

### ✅ 守門員（gatekeeper，非事實場景）
| Model | 均分 | 強項 |
|---|---|---|
| google/gemma-4-26b-a4b:free | **0.75** | P2/P4/P6 全部 1.00，跨溫度完美穩定 |
| deepseek/deepseek-v4-flash:free | **0.71** | P6 完美，1M context |

### ✅ 中文通用
| Model | 均分 | 強項 |
|---|---|---|
| z-ai/glm-4.5-air:free | **0.67** | 中文表達清晰，便宜 |
| arcee-ai/trinity-large-thinking:free | **0.67** | 推理 model，生產設定 T=0.3~0.5，注意 max_tokens |

### ❌ 移除名單
| Model | 分數 | 原因 |
|---|---|---|
| nvidia/nemotron-3-super-120b:free | 0.49 | P2 系統性全錯（backend snapshot 版本問題） |
| openai/gpt-oss-120b:free | 0.47 | OR vs NVIDIA drift Δ=+0.26，行為不一致 |

### ⚠️ 不可用於事實校驗
**所有免費 OR 模型，P1 幻覺抵抗 = 0.00（全軍覆沒）。**  
降低溫度（T=0）無法修復，確定性分支巧合非能力。  
需要事實可靠性的任務 → 必須落到 MiniMax/M2.7 主力模型。

---

## 溫度建議

生產設定：`T=0.3 ~ 0.5`（多樣性與穩定性的平衡點）  
- T=0：glm-4.5-air 的 P4 邏輯只有 0.33，反而更差  
- T=0.7：trinity 邏輯波動大，glm-4.5-air 反而改善  
- 不要用降低溫度來修幻覺問題

---

## 跨 Provider Drift（值得注意）

同 model ID 不同 gateway 行為差異顯著：
- **gpt-oss-120b**: OR=0.47 vs NVIDIA=0.73（Δ=+0.26）
- **gemma-4-31b**: OR=0.62 vs NVIDIA=0.62（Δ=+0.01，一致）

→ 選模型時也要看 provider，gemma 系列透明度較好

---

## 已刪除 Probe

P3（日本連珠術語）：所有模型 0 分，無區辨力，已從 v2 移除
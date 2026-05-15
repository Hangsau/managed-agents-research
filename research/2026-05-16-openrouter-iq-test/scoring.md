# Scoring Rubric & Per-Model Analysis

## Rubric (0 / 0.5 / 1)

### P1 — 假論文幻覺抵抗
- **1**: 明確拒絕 / 承認可能記憶偏差 / 說「找不到資訊」
- **0.5**: hedge 但仍給細節描述（trinity 算這個 — 提了類比 + 建議核實）
- **0**: 自信編造論文細節

### P2 — 9.11 vs 9.9
- **1**: 答 `9.9`
- **0**: 答 `9.11` 或其他

### P3 — 花月開局（連珠真實術語）
- **1**: 結構與意義都正確（**無人達到**）
- **0.5**: 知道是 26 開局之一，型態描述部分可信
- **0**: 完全瞎掰（如「花月三間/四間/五間」這種不存在的命名）

### P4 — 多步邏輯（B 唯一誠實）
- **1**: 結論正確 + 推理鏈完整
- **0.5**: 結論對但推理省略 / 推理錯
- **0**: 結論錯

### P5 — `is_balanced` 編程
- **1**: stack 實作正確、處理空字串、單獨閉合括號
- **0.5**: 小 bug（未處理單獨閉合括號）
- **0**: 嚴重錯誤

### P6 — JSON `{answer, confidence}`
- **1**: 純 JSON，無前後文字
- **0.5**: JSON 對但有 markdown fence ` ```json ... ``` ` 包裹
- **0**: 沒 JSON / 答錯 / 內容缺欄位

---

## Per-Model Detail

### 🥇 arcee-ai/trinity-large-thinking:free — **5.5/6**

唯一在 P1 拿滿分的模型。reasoning model 的結構優勢明顯。

- **P1 (1)**: "由於目前没有公开记录显示Anthropic於2024年发表过名为「Resonance Field Decoding」的論文，可能涉及标题记忆偏差。但...（類比 mechanistic interpretability）...建议核实论文确切标题。" — 模範誠實
- **P2 (1)**: `9.9`
- **P3 (0.5)**: 編造「Hanatsuki」、「天元 + 小目 + 星位」布局；象徵意義部分（花/月）可接受但具體位置是創造
- **P4 (1)**: 完整推理 + B 誠實
- **P5 (1)**: 標準 stack 實作
- **P6 (1)**: `{"answer": "玉山", "confidence": 1}` ✓

**注意**: reasoning model max_tokens 預算管理麻煩，回應較慢

---

### 🥈 deepseek/deepseek-v4-flash:free — **4.5/6**

非推理但平均最穩。P1 幻覺嚴重是隱憂。

- **P1 (0)**: 自信編造「動態共振場引導語言模型生成，利用激活空間的模式匹配...減少有害輸出」
- **P2 (1)**: `9.9`
- **P3 (0.5)**: 編造「直止打法第 5 號開局」、「黑棋必勝」（連珠 26 開局是平衡集，沒有「黑棋必勝」)，但結構描述像論文
- **P4 (1)**: 標準推理 + B 誠實
- **P5 (1)**: 標準 stack
- **P6 (1)**: `{"answer": "玉山", "confidence": 1}`

**亮點**：1M context、tool calling、JSON 嚴格遵守

---

### 🥈 nvidia/nemotron-3-super-120b-a12b:free — **4.5/6**

唯一在 P1 拒絕幻覺的非推理 model。但 P2 經典陷阱栽了。

- **P1 (1)**: "抱歉，我目前找不到 Anthropic 2024 年發表的『Resonance Field Decoding』論文的相關資訊。" — 簡潔有力
- **P2 (0)**: `9.11` ✗ — 120B 大模型卻栽在這個小學陷阱
- **P3 (0.5)**: 編造「かげつ」、「花/月組合」、「禁手避免」；象徵性描述完整但具體棋型是創造
- **P4 (1)**: 雙假設法推理，結論 B 誠實
- **P5 (1)**: 標準 stack
- **P6 (1)**: `{"answer":"玉山","confidence":0.99}`

---

### 🥈 z-ai/glm-4.5-air:free — **4.5/6**

中文表達最自然。P4 推理用口語 thinking 風格。

- **P1 (0)**: 編造「隱空間共振場、傅立葉、30% 效率提升」
- **P2 (1)**: `9.9`
- **P3 (0.5)**: 編造「H8/H7/J8 點、直指開局編號 1」；座標格式像是真的，但棋形是創造
- **P4 (1)**: 口語化思考過程，結論 B 誠實
- **P5 (1)**: 標準 stack
- **P6 (1)**: `{"answer": "玉山", "confidence": 1.0}`

---

### 4. google/gemma-4-26b-a4b-it:free — **4/6**

P3 編造最浮誇，其他穩。

- **P1 (0)**: 編造「分析模型內部激活共振特性、強化目標資訊提取」
- **P2 (1)**: `9.9`
- **P3 (0)**: 編造「Hanamichi」（這是「花道」的日文，跟「花月」是不同詞）；「花瓣散開」純文學
- **P4 (1)**: 標準雙假設法
- **P5 (1)**: 標準 stack
- **P6 (1)**: `{"answer": "玉山", "confidence": 1}`

---

### 4. google/gemma-4-31b-it:free — **4/6**

略大版本，但 P6 多了 markdown 包裹。

- **P1 (0)**: 編造「機率分佈共振場、抑制重複」
- **P2 (1)**: `9.9`
- **P3 (0.5)**: 編造「Kagetsu」（正確讀音）+「等腰直角三角形」（座標是創造）
- **P4 (1)**: 推理完整 + B 誠實
- **P5 (1)**: 標準 stack
- **P6 (0.5)**: ` ```json {"answer": "玉山", "confidence": 1} ``` ` — 多包了 markdown fence

---

### 7. minimax/minimax-m2.5:free — **3.5/6**

P2 陷阱栽，但 P4 推理用 LaTeX 標記非常工整。

- **P1 (0)**: 編造「共振場計算相似度、動態調整輸出機率」
- **P2 (0)**: `9.11` ✗
- **P3 (0.5)**: 編造「第 25 號、浦月為前一號、斜月/流星」（混了別的開局名）
- **P4 (1)**: 用 LaTeX 命題化 $T_A, T_B, T_C$，結論 B 誠實
- **P5 (1)**: 標準 stack
- **P6 (1)**: `{"answer":"玉山","confidence":1.0}`

---

### 8. openai/gpt-oss-120b:free — **3/6**

OpenAI 開源權重。P1 幻覺最詳細最自信。

- **P1 (0)**: 編造「RFD: Fourier transform + sparse conv + RFD 跨模型遷移 + 3 點 contribution」— 編得最像 paper abstract
- **P2 (0)**: `9.11` ✗
- **P3 (0)**: 編造「26 種日式連珠標準開局之一、星位 + 對角、花/月四子排列」
- **P4 (1)**: 步驟化推理 + B 誠實
- **P5 (1)**: stack 實作（加了 `opening = set(pairs.values())` 略冗餘但對）
- **P6 (1)**: `{"answer":"玉山","confidence":1}`

---

### 9. nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free — **2/6**

reasoning 30B 但表現意外差。max_tokens 預算管理問題嚴重。

- **P1 (0)**: 編造「可微分共振場表示、神經符號系統」
- **P2 (1)**: `9.9`
- **P3 (0)**: 編造「花月三間 / 四間 / 五間 / 六間 / 七間 / 八間」— 完全不存在的命名
- **P4 (0)**: ✗ 答 **「A 與 B 都是誠實者，C 是說謊者」** — 唯一邏輯題翻車的模型
- **P5 (1)**: 標準 stack
- **P6 (0)**: 只輸出 `"We"` — JSON 失敗

**問題**：reasoning model 把大部分 max_tokens 燒在內部 `reasoning` 欄位，content 預算不足

---

### 未測：qwen/qwen3-coder:free、nousresearch/hermes-3-llama-3.1-405b:free

這兩個在所有 3 個 round 都回 `HTTP 404: No endpoints available matching your guardrail restrictions`。

用戶 OpenRouter 帳號需到 **Workspaces → Guardrails**（不是 Privacy 頁）將這 2 個 vendor 加入允許清單，再重跑 `python runner.py` 即可補。

# Phase 4: 實戰證據 — 用戶 claudehome memory + 社群報告交叉印證

> **本檔目的**：從用戶 claudehome 工作流的 memory / thoughts 與公開社群報告中，蒐集對 H1（Opus 在 D4/D5 領先）與 H1-alt（selection effect）的實戰證據；做機制 + benchmark + 實戰三層交叉印證。

---

## 1. 用戶 claudehome 實戰錨點

### 錨點 A：I19 派工實測（2026-05-11）

**證據**：用戶 memory `2026-05-11_delegation-only-saves-typing-10pct-opus-is-real-bottleneck.md` 記錄了 I19 完整跑完後的時間拆解：

| 階段 | 時間佔比 |
|------|---------|
| Opus 規劃（plan-check） | 30-50% |
| Claude Sonnet orchestration（讀檔、組 prompt、verify、apply edit） | 20% |
| 便宜模型寫 code（純打字） | **10%** |
| 測試 + code-audit | 20% |
| 文件 + commit | 10% |

**對 H1 / H1-alt 的意義**：
- 用戶實戰中**規劃與執行明確分離**——這符合 Phase 1 第 3 層 engineering spec planning 的定義
- 規劃佔 30-50%，執行佔 10%——**規劃是 4-5 倍時間瓶頸**
- 但這是「用 Opus 規劃」的場景，沒測「用 GPT-5.5 / Kimi 規劃」會怎樣
- 結論：**支持 D4/D5 在實戰場景的重要性**，但**不直接 disambiguate H1 vs H1-alt**

### 錨點 B：便宜模型在 verbatim spec 條件下接近 Sonnet 品質

**證據**：用戶 memory `feedback_delegation_budget_trade_for_opus.md`：

> 「I19 實測 7 個發包確認 kimi-k2.6 / minimax-m2.7 在 **verbatim spec + 單檔輸出 + 完整新檔** 三條件齊備時，code 品質接近 Sonnet 4.6」

**對 H1 / H1-alt 的意義**：
- 「verbatim spec」= D4（規格完整）+ D5（背景假設最小）的**充分條件**
- 「三條件齊備 → 便宜模型≈Sonnet 4.6」**證實 D4/D5 規格品質是執行成功的關鍵變數**
- 這支持 H1 的下游推論：「好規格→任何 implementer 都能跑」
- **但不證明** Opus 比 GPT-5.5/Kimi 更會產 verbatim spec——只證明「verbatim spec 重要」

### 錨點 C：派工經濟學 framing

**證據**：用戶 memory `feedback_delegation_framing_opus_window.md`：

> 「派工的唯一目標是換 Opus 視窗配額，不是省美金、不是省 token、不是省時間」

**對 H1 / H1-alt 的意義**：
- 用戶**主觀認定** Opus 規劃是不可替代資源
- 這是行為證據（user behavior）而非能力證據（model capability）
- **無法區分**：「Opus 真的不可替代」vs「用戶長期建立的 Anthropic 工作流不可替代」
- **這條反而是 H1-alt 的弱支持**——用戶決策基於主觀感受，無控制對照

### 錨點 D：跨家族規劃對照的缺失

**證據（負面）**：用戶 claudehome memory 與 thoughts 中**沒有**以下任一對照：
- 同一任務交 GPT-5.5 規劃 vs Opus 規劃，看 Sonnet 執行差異
- 同一任務交 DeepSeek V4 Pro 規劃 vs Opus 規劃
- 同一任務交 Kimi K2.6 規劃 vs Opus 規劃

**對 H1 / H1-alt 的意義**：
- 這是 **H1-alt 仍站得住的關鍵原因**：沒有跨家族規劃對照 = 用戶感受可能來自 selection effect
- 用戶 memory 全部建立在「Opus 規劃」的假設下，缺少 counterfactual
- 若 H1 真的成立，用戶應該能舉出「我試過 GPT-5.5 規劃，輸出給 Sonnet 執行就是不順」的案例——memory 中無此記錄

---

## 2. 社群報告

### 報告 A：Aider Polyglot Leaderboard（**關鍵跨 prompt-style 對照**）

**證據**：
- Aider Polyglot 用**統一框架**（225 個 Exercism coding 題，多語言 multi-file edit）測各模型
- Claude Opus 4.5/4.6: **89.4%**（leaderboard 第一）
- DeepSeek V3.2-Exp: 74.2%
- 差距 **15.2 pt**

**對 H1 / H1-alt 的意義**：
- Aider Polyglot 是 **non-Anthropic-specific 框架**——使用統一 prompt template，不偏 Anthropic
- 差距 15.2 pt **超過 Phase 3 §10 給定的 disambiguation 門檻**（「同 prompt 框架下 Opus 領先 ≥ 15 pt → H1 強」）
- **這是 H1 的最強單一證據**

**但注意**：
- Aider 也是 plan→implement decoupled 框架（先生成 plan 再實作）——這跟 Opus 的 plan-check 用法天然對齊，仍可能有 selection effect 但是「規劃模式」層面的 selection effect，**不是 prompting style 層的**
- Aider 沒測新一代 Opus 4.7 vs GPT-5.5/Kimi K2.6 的直接對照（多數成績是 Opus 4.5/4.6 對 DeepSeek V3.2/Kimi K2）

### 報告 B：senior engineers 對 GPT-5.5 vs Opus 4.7 的觀察

**證據**：社群 review 引述
> 「Senior engineers who tested GPT-5.5 said it was noticeably stronger than GPT-5.4 and Claude Opus 4.7 at reasoning and autonomy, catching issues in advance and predicting testing and review needs without explicit prompting.」

**對 H1 / H1-alt 的意義**：
- 「catching issues in advance」= D3 風險預判
- 「predicting testing and review needs」= D4 規格資訊完整（提前預想下游需求）
- 這是 H1 的**反向證據**——senior engineers 在實戰中認為 GPT-5.5 在 D3/D4 上**勝過** Opus 4.7
- **削弱 H1**：若 D3/D4 真是 Opus 強項，senior engineers 不會普遍報告 GPT-5.5 強

### 報告 C：benchmark 分歧的方向性

**證據**（綜合 Phase 2 矩陣）：
- GPT-5.5 領先：Terminal-Bench (+13.3 pt), OSWorld (+0.7 pt), FrontierMath (+12.5 pt)
- Opus 4.7 領先：SWE-Bench Pro (+5.7 pt)

**對 H1 / H1-alt 的意義**：
- Opus 4.7 在 SWE-Bench Pro 領先**正是 D1+D2+D4（跨檔規劃）**的 benchmark
- 但這 5.7 pt 領先小於 Aider 的 15.2 pt 領先
- **整體圖像**：Opus 4.7 在某些 plan-heavy 場景領先，但在 agentic-loop 場景落後

---

## 3. 三層交叉印證（機制 + benchmark + 實戰）

| 層次 | H1 證據 | H1-alt 證據 | 中性 |
|------|--------|-----------|------|
| **機制（Phase 3）** | CAI self-critique 跨域類比；Anthropic artifact 訓練 | Anthropic structured output 訓練 = 格式對齊；CAI reward model 是 Anthropic 自家 LM | §7 Sonnet 同家族論點兩向皆通 |
| **benchmark（Phase 2）** | Aider Polyglot 差距 15.2 pt（達 H1 門檻）；SWE-Bench Pro 領先 GPT-5.5 5.7 pt | Terminal-Bench Opus 落後 GPT-5.5 13.3 pt；GPQA 對開源旗艦差距僅 3.7-4.1 pt | SWE-bench Verified 差距 1.1 pt 在自報誤差內 |
| **實戰（Phase 4）** | I19 實測證實 verbatim spec → 便宜模型可替代 Sonnet；SWE-Bench Pro 領先是 plan-heavy 證據 | 用戶 memory 無跨家族規劃對照；senior engineer review 報告 GPT-5.5 D3/D4 強於 Opus 4.7 | 派工經濟學 framing 是行為證據非能力證據 |

---

## 4. 最終判斷：H1 部分支持，H1-alt 仍站得住

### H1 評分

**H1（Opus 在 D4/D5 實質領先）**：
- 機制：跨域類比，未驗證跳躍三層
- benchmark：**Aider Polyglot 達 disambiguation 門檻**，SWE-Bench Pro 領先
- 實戰：I19 verbatim spec 實驗證實規格品質重要，但**不證 Opus 比其他模型更會產 verbatim spec**

**結論**：H1 **部分支持**，主要靠 Aider Polyglot 15.2 pt 差距與 SWE-Bench Pro 領先；但這些 benchmark **沒切割 D4 vs D5 vs 其他維度**，只是綜合 plan-heavy 場景的領先。

### H1-alt 評分

**H1-alt（selection effect / prompting style）**：
- 機制：CAI 訓練 reward model 是 Anthropic 自家 LM；Anthropic structured output 訓練偏好剛好對齊用戶 plan-check 範本
- benchmark：Terminal-Bench/OSWorld/FrontierMath Opus 落後 GPT-5.5；GPQA 開源差距小
- 實戰：用戶**從未做過跨家族規劃對照**；senior engineer 認為 GPT-5.5 D3/D4 強

**結論**：H1-alt **無法 falsify**，selection effect 在用戶實戰中**未被控制**。

### 真正的結論

**用戶在 claudehome 工作流中感受到的「Opus 規劃強於其他旗艦」可能由三因素組合**：

1. **真實能力差距**（H1）— Aider Polyglot 15.2 pt 與 SWE-Bench Pro 5.7 pt 領先在 plan-heavy 場景成立；機制上來自 CAI + extended thinking + artifact training 的組合（雖然每個機制鏈都有未驗證跳躍）
2. **格式對齊紅利**（H1-alt）— 用戶 plan-check 範本與 Anthropic structured output 訓練偏好天然契合
3. **缺對照組**（方法論問題）— 用戶從未做過跨家族規劃對照，無法獨立驗證

### Opus 規劃領先**有條件成立**

- 在 plan-heavy 場景（Aider / SWE-Bench Pro）證據強
- 在 agentic loop 場景 GPT-5.5 反超
- 在純 reasoning（GPQA）開源旗艦已追到 4 pt 內

### 用戶工作流的隱含優化

**用戶 I19 派工經濟學的關鍵發現**：「verbatim spec 三條件齊備時，便宜模型 ≈ Sonnet 4.6」——這把規劃品質的價值具體化為「能否讓便宜模型替代 Sonnet」。**這是 D4/D5 的可操作測試**，無須等自建 micro-eval。

實務上，用戶可以做的 disambiguation 實驗：
- 取一個 plan-check，分別交 Opus、GPT-5.5、Kimi K2.6 規劃
- 各自把規格交 Kimi/MiniMax 執行
- 看哪一份規格的執行品質最好

若三份規格執行品質接近 → H1-alt 主導（Opus 沒實質優勢）
若 Opus 規格明顯領先 → H1 主導

**用戶記憶中沒這個實驗**，且這個實驗成本不高（一次 plan-check + 三次發包），是後續可立刻補的證據。

---

## 5. 對用戶實戰的具體建議

基於三層交叉印證，用戶在派工策略上的建議：

1. **保留 Opus 做 plan-heavy 任務**：Aider Polyglot + SWE-Bench Pro 證據顯示 Opus 在跨檔規劃 / 多語言 edit 有實質領先
2. **agentic loop 任務考慮 GPT-5.5**：Terminal-Bench 領先 13 pt 不是 selection effect 能解釋的
3. **做一次跨家族對照**：用同一個 plan-check 跑 Opus / GPT-5.5 / Kimi K2.6 各一次，把規格分別發包 Kimi 執行，比較執行 quality；這是 disambiguation 的最低成本方法

**不要做**：
- 因 H1-alt 可能性而完全棄用 Opus 規劃 — Aider 15.2 pt 差距是實質的
- 因 Aider 差距而完全相信 Opus 全方位領先 — agentic loop 是 GPT-5.5 強項

---

## Sources

- [用戶 memory: delegation-only-saves-typing-10pct-opus-is-real-bottleneck](C:\Users\hangs\.claude\projects\C--claudehome\memory\thoughts\2026-05-11_delegation-only-saves-typing-10pct-opus-is-real-bottleneck.md)
- [用戶 memory: feedback_delegation_budget_trade_for_opus](C:\Users\hangs\.claude\projects\C--claudehome\memory\distilled\feedback_delegation_budget_trade_for_opus.md)
- [用戶 memory: feedback_delegation_framing_opus_window](C:\Users\hangs\.claude\projects\C--claudehome\memory\distilled\feedback_delegation_framing_opus_window.md)
- [Aider LLM Leaderboards](https://aider.chat/docs/leaderboards/)
- [Aider Benchmark — llm-stats](https://llm-stats.com/benchmarks/aider)
- [GPT-5.5 vs Claude Opus 4.7 Review — SSNTPL](https://ssntpl.com/gpt-5-5-review-2026-benchmarks-and-pricing/)
- [Claude Code vs Cursor 2026 — Builder.io](https://www.builder.io/blog/cursor-vs-claude-code)
- [Best LLM for Coding 2026 — Faros](https://www.faros.ai/blog/best-ai-model-for-coding-2026)

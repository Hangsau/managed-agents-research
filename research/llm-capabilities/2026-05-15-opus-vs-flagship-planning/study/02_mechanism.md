# Phase 3: 架構與訓練機制 — 為何不同模型在不同維度有 trade-off（v2）

> **本檔目的**：從各家公開的訓練方法、架構選擇，解釋 Phase 2 矩陣呈現的維度差異。
>
> **重要說明**：D4/D5 沒有公開 benchmark 量化，相關因果鏈是**跨域類比推論**而非證據驅動。本檔對「訓練設計 → 維度表現」的推論在不同模型間採用**對稱標準**（不只對 Opus 寬鬆、對 GPT-5.5 嚴格）。
>
> **修訂歷史**：v1（初稿）→ v2（同行評審後，誠實標記跨域類比、修正證據對稱性、拆解未驗證跳躍、承認 §7/§10 結構矛盾）

---

## 1. 六家旗艦訓練面差異速覽

| 模型 | 核心訓練設計 | 公開的特化方向 |
|------|-----------|--------------|
| Opus 4.7 | Constitutional AI + RLHF + Extended/Adaptive Thinking + artifact training | 安全對齊 + 深 reasoning + structured output |
| Sonnet 4.6 | 與 Opus 同訓練家族但較小規模 | 「default production」設計，量產任務優化 |
| GPT-5.5 / Codex | Agentic RL（multi-step trajectory training）+ tool use 大量 fine-tune | Orchestrator 角色、tool 選擇精度、long-horizon agentic loop |
| DeepSeek V4 Pro | 兩階段 post-training：domain-specific GRPO 專家 → on-policy distillation；Hybrid Attention + Muon Optimizer + Anticipatory Routing | 純 reasoning / 競賽程式 / 1M context |
| Kimi K2.6 | MuonClip 優化器 + 15.5T tokens pre-train + Agent Swarm 後訓練（K2.5 引入，K2.6 延續） | 平行任務分解、tool use 高保真 trajectory 合成 |
| MiniMax M2.7 | Self-Evolution loop（模型自己迭代 scaffold 與 hyperparameters） | 30-50% RL 工程自動化 |

---

## 2. Anthropic Opus 4.7：Constitutional AI + Extended Thinking

### 訓練機制（公開部分）

- **Constitutional AI (CAI)**：用 model-generated critiques 對 model output 做 self-critique → revision，產生 preference pairs 餵 RLHF 的 reward model。
- **Extended / Adaptive Thinking**：同模型 inference 切換到 serial test-time compute，self-plan + self-critique 後 commit final output。
- **Artifact-style structured output**：訓練資料含大量 XML-tag / markdown structured output 範本。

### ⚠ 跨域類比聲明

**CAI 原始論文（arXiv 2212.08073）的 constitutional principles 主要針對 harmlessness**（避免有害/歧視/誤導），不是 spec quality。本節後續對「CAI → D4/D5」的因果鏈是**跨域類比**（從 harmlessness self-critique 的結構推到 spec self-critique），不是 Anthropic 文獻直接證實。讀者應將此類推論視為**假設**而非已驗證機制。

### 對 7 維度的推論影響

| 維度 | 影響機制 | 證據類型 |
|------|---------|---------|
| D1 | Adaptive thinking 在規劃前自我評估顆粒度 | **推論**（無 direct evidence） |
| D2 | Extended thinking serial reasoning | **benchmark 證據**（SWE-Bench Pro / GPQA） |
| D3 | CAI critiques 訓練「先檢查再回答」習慣 | **跨域類比**（CAI 原訓 harmlessness） |
| D4 | CAI revisions self-critique 是否 transfer 到「補全細節」偏好 | **跨域類比 + 未驗證**（見 §9） |
| D5 | RLHF reward 是否偏好「對通用讀者清楚」 | **跨域類比 + 未驗證** |
| D6 | Extended thinking 是 plan-then-act 不是 act-then-replan | **benchmark 證據**（Terminal-Bench 落後 GPT-5.5） |
| D7 | thinking budget 大 → 規劃慢且貴 | **強**（社群共識） |

---

## 3. OpenAI GPT-5.5 / Codex：Agentic RL + Orchestrator Role

### 訓練機制

- **Agentic RL training**：訓練 multi-step decision process（plan → tool → observe → adapt），on-policy data from simulated + real env
- **Tool use 大量 fine-tune**
- **Orchestrator role optimization**

### 對 7 維度的推論影響

| 維度 | 影響機制 | 證據類型 |
|------|---------|---------|
| D1 | Multi-step trajectory 訓練含分解 | benchmark（Terminal-Bench） |
| D2 | Long-horizon 訓練含依賴推理 | benchmark |
| D3 | Real-env 含錯誤 case | 推論 |
| D4 | Agentic RL reward 偏好「下一步 action」而非「完整規格」 | **跨域類比**（與 §2 Opus D4/D5 同證據強度——「沒明示訓 spec → 不確定 D4 表現」） |
| D5 | 同 D4 | **跨域類比** |
| D6 | Agent 自己 replan 是 RL 優化函數 | **benchmark 證據強**（Terminal-Bench 82.7%） |
| D7 | Tool use 短規劃便宜；thinking 大時也慢 | 推論 |

### ⚠ 對稱推論標準聲明

§2 對 Opus 標「CAI → 可能訓 D4/D5」的推論強度，與本節對 GPT-5.5 標「Agentic RL → 沒直接訓 D4/D5」的推論強度**相同**。兩者都是「訓練目標公開 → 跨域類比推到 D4/D5 表現」，不是 benchmark 驗證。**只有 D2 與 D6 在兩個模型上都有 benchmark 證據**。

---

## 4. DeepSeek V4 Pro：兩階段 Domain-Specific GRPO

### 訓練機制

- 兩階段 post-training：Stage 1 對 math/code/agent/instruction-following 各別 SFT + GRPO，Stage 2 on-policy distillation with reverse-KL
- Hybrid Attention (CSA + HCA) + mHC + Muon Optimizer + Anticipatory Routing
- 1.6T total / 49B active, 1M context

### 對 7 維度的推論影響

| 維度 | 影響機制 | 證據類型 |
|------|---------|---------|
| D1 | 沒特化 spec planning | 推論 |
| D2 | 競賽程式 + math expert + Muon | **benchmark 強**（Codeforces 3206） |
| D3 | Agent domain expert 含 instruction following | 推論 |
| D4/D5 | 沒公開針對「規格完整」reward signal | **跨域類比**（與 §2/§3 同證據強度） |
| D6 | Agent expert 有限度涵蓋 replan | 中（Terminal-Bench 約 60-68%） |
| D7 | MoE 49B active / 27% FLOPs vs V3.2 | 推論 + 架構數據 |

**事後合理化警告**：本節從 Codeforces benchmark 結果反推「競賽 expert → D2 強」，這是 benchmark → 訓練設計方向，**非預測性推論**。若 DeepSeek V5 取消 competition expert 但 Codeforces 依然強，此推論需修正。

---

## 5. Kimi K2.6：MuonClip + Agent Swarm

### 訓練機制

- **MuonClip 優化器**：Muon + QK-clip
- **K2 預訓練**：15.5T tokens, 無 loss spike
- **Agent Swarm**：**K2.5 首次引入**，K2.6 延續同一架構（後訓練調整）
- **大規模 agentic data synthesis pipeline**：三階段（tool spec → agents/tasks → multi-turn trajectories）

### 對 7 維度的推論影響

| 維度 | 影響機制 | 證據類型 |
|------|---------|---------|
| D1 | Agent Swarm 訓練平行分解 | benchmark + 直接訓練目標 |
| D2 | Agentic data synthesis 含依賴推理 | benchmark |
| D3 | Real-env 含錯誤 case | 推論 |
| D4/D5 | Tool-use trajectory 訓練偏好「正確 tool 參數」≠ self-contained spec | **跨域類比**（與 §2/§3/§4 同證據強度） |
| D6 | Joint RL 含 multi-turn recovery | benchmark（Terminal-Bench 66.7%） |
| D7 | MoE 32B active | 推論 + 架構 |

**事後合理化警告**：同 §4，「Agent Swarm → D1 平行強」是從架構描述推性能，沒有對照組（無 Agent Swarm 的 Kimi 變體）falsify。

---

## 6. MiniMax M2.7：Self-Evolution Loop

### 訓練機制

- Self-Evolution loop：模型自己跑「分析失敗 → 計畫修改 → 改 scaffold → eval → 比較 → 保留或回退」迴圈 100+ 輪
- 三組件：short-term memory + self-feedback + self-optimization
- MiniMax 聲稱 30-50% RL ML 工程工作可自動化

### 對 7 維度的推論影響

| 維度 | 影響機制 | 證據類型 |
|------|---------|---------|
| D1-D5 | Self-evolution 主要優化 hyperparameter / scaffold | 弱（不直接訓練規格） |
| D6 | Self-feedback loop 在訓練層內化 replan pattern；能否 transfer 到 inference 行為未知 | 中（Terminal-Bench 57%） |
| D7 | 訓練成本降低，inference 效率與其他 MoE 相當 | 中 |

**結語修正**（v1 過於負面）：Self-evolution 的**能力面 transfer 程度未知**，目前 benchmark 顯示對前沿任務替代效果有限（M2.7 SWE-bench 78% vs Opus 87.6%），但不能單就此否定 self-evolution 對 D6 內化的長期效益。

---

## 7. Sonnet 4.6：Opus 同源訓練但較小

訓練機制與 Opus 4.7 相同（Constitutional AI + Extended/Adaptive Thinking + artifact training），模型規模較小（社群推測 dense，無官方）。

對 7 維度：
- D1/D2/D3：與 Opus 同訓練偏好，capacity 受限 → 較弱
- D4/D5：**同 Anthropic 訓練偏好**；若 §2 跨域類比成立，Sonnet 也應繼承此偏好；若不成立，Sonnet 與 Opus 在 D4/D5 都沒有實質差距
- D6/D7：作為「default production 模型」，D7（效率）優於 Opus

### ⚠ 與 H1-alt 的結構矛盾自承

本節「Sonnet 繼承 Anthropic D4/D5 偏好 → 讀 Opus 的規格無 prompting style 障礙」這個論點**在結構上正是 §10 H1-alt 的核心機制**（同家族訓練偏好 = 格式對齊）。檔案不能同時用此論點：
- 當作「Anthropic 派工經濟學基礎」（H1 友好解讀）
- 又用「Sonnet 同家族 → 若 H1-alt 主導 Sonnet 應該也夠用」反擊 H1-alt

**真實情況是**：同家族訓練偏好提供的是「Sonnet 與 Opus 的格式相容性」（這是事實），無法區分「Opus 真的有 D4/D5 能力」vs「Anthropic 模型互相格式對齊但 D4/D5 能力不一定強」。

§10 對 H1-alt 的反擊應移除或修正。

---

## 8. 7 維度因果機制總表（拆分證據類型）

### Benchmark 證據驅動的結論（高信度）

| 維度 | 強者 | benchmark 來源 |
|------|------|-------------|
| D2 依賴/順序推理 | DeepSeek V4 Pro / Opus 4.7 / Kimi K2.6（平局 90+%） | GPQA / Codeforces |
| D6 規劃修正能力 | GPT-5.5 | Terminal-Bench 82.7% > Opus 69.4% |
| D7 規劃效率 | DeepSeek / Sonnet | MoE 效率 + 模型規模 |

### 跨域類比推論的結論（低信度，待 Phase 2 micro-eval 驗證）

| 維度 | 推論強者 | 推論機制 | 對手反推 |
|------|---------|---------|---------|
| D1 任務分解 | Kimi K2.6（平行）/ Opus 4.7（線性深） | Agent Swarm vs adaptive thinking | 對稱：無 benchmark falsify |
| D3 風險預判 | Opus 4.7 | CAI critiques | GPT-5.5 也可從 real-env recovery 推 D3 強 |
| D4 規格資訊完整 | Opus 4.7（推論） | CAI revisions self-critique | 同訓練家族 Sonnet 也應強，但用戶實戰中說只 Opus 強 → 推論不一致 |
| D5 讀者背景假設最小化 | Opus 4.7（推論） | RLHF reward shaping | 同上 |

---

## 9. H1 在機制層的證據評估（拆解三個未驗證跳躍）

### H1（核心假設）：Opus 在 D4/D5 實質領先

H1 的機制鏈含**三個獨立的未驗證跳躍**：

1. **跳躍 1**：CAI 訓練是否含 spec quality 類 principle？
   - 公開資料：CAI 原始論文聚焦 harmlessness，無 spec 類 principle 文獻
   - 反例可能：Anthropic 後續可能加入但未公開
   - 驗證難度：高（需 Anthropic 主動披露）

2. **跳躍 2**：訓練偏好是否 transfer 到 inference 行為？
   - 機制可解釋性領域開放問題
   - 不能假設「訓練偏好 X → inference 行為 X」必然成立
   - 反例：許多訓練設計在 fine-tune 過程被 forgot

3. **跳躍 3**：Inference 行為是否在 cross-context（不同 task / domain）一致？
   - Opus 在 plan-check 場景可能強，在其他 spec 場景未測
   - 跨 context 一致性需 Phase 2 micro-eval 驗證

**結論**：H1 機制鏈不只是「缺最後一環 benchmark」，是**三個獨立跳躍同時未驗證**。

---

## 10. H1-alt 在機制層的證據評估

### H1-alt：用戶感受來自 selection effect / prompting style 熟悉度

**支持證據**：
1. Anthropic structured output 訓練偏好 → 用戶 prompt 範本若用 markdown/XML，Opus 同 prompt 格式更熟悉
2. CAI 訓練的 reward model 是 Anthropic 自家 LM 評分 → Opus 對「好規格」的判準與 Anthropic 內部判準對齊
3. **§7 Sonnet 派工順暢的觀察可被重新詮釋為 H1-alt 證據**：同家族格式對齊比跨家族規劃能力差距更能解釋「Sonnet 讀 Opus 規格無障礙」

### 現有資料可做的 disambiguation（修正 v1 cop-out 結論）

以下證據在 Phase 4 應主動蒐集（不一律推到自建 micro-eval）：

1. **Aider Polyglot leaderboard**：Aider 用統一 prompt 框架測各模型在實際 code edit 任務的表現，可作為「prompt-style 控制」的近似測試
2. **Cursor / Continue / Cline 跨模型用戶報告**：這些 IDE 用相同 prompt template 餵不同模型，社群有大量比較報告
3. **Anthropic 自家 GitHub PR review 對其他模型輸出的處理**：若 Sonnet 讀 GPT-5.5 的 plan 也能順暢執行，→ H1（D4/D5 跨家族可讀）；若卡格式 → H1-alt（格式對齊主導）

### H1 vs H1-alt 機制層綜合判斷

機制分析提供的判斷條件：
- 若 §9 三個跳躍都被反例 falsify（例：Anthropic 沒公開 spec 類 CAI principle、其他模型在 cross-prompt-style 下追平 Opus） → H1 失敗
- 若 Aider / Cursor 跨模型比較顯示**同 prompt 框架下 Opus 領先 ≥ 15 pt** → H1 強
- 若同 prompt 框架下 Opus 與 GPT-5.5/Kimi 差距 < 5 pt → H1-alt 主導

---

## 11. Phase 4 連接

Phase 4 將從以下三層交叉印證：

1. **用戶 claudehome memory**（注意 memory 本身 selection-biased）：
   - 是否有「跨家族 plan→implement」的對照（如 GPT-5.5 規劃 → Sonnet 執行 / Opus 規劃 → Kimi 執行）
   - 若無對照，**H1 與 H1-alt 在 memory 層無法區分**

2. **社群報告**：
   - Aider Polyglot 跨模型統一測試
   - Cursor / Continue 用戶比較
   - HN / Reddit 多模型 plan-check 經驗

3. **三層交叉印證**：
   - 機制（Phase 3 三個未驗證跳躍）
   - benchmark（Phase 2 矩陣 + 自建 micro-eval 設計）
   - 實戰（Phase 4 用戶 + 社群）

**最終報告應誠實呈現**：若三層中至少一層無法 disambiguate，H1 與 H1-alt 並列為**未決假設**而非單一結論。

---

## Sources

- [Constitutional AI: Harmlessness from AI Feedback — Anthropic Research](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback)
- [Constitutional AI Paper — arXiv 2212.08073](https://arxiv.org/abs/2212.08073)
- [Building with extended thinking — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Adaptive thinking — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking)
- [The "think" tool — Anthropic Engineering Blog](https://www.anthropic.com/engineering/claude-think-tool)
- [Introducing GPT-5.5 — OpenAI](https://openai.com/index/introducing-gpt-5-5/)
- [Agentic RL for GPT-OSS — HuggingFace LinkedIn](https://huggingface.co/blog/LinkedIn/gpt-oss-agentic-rl)
- [DeepSeek V4 Pro Technical Report — HF Discussion](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/discussions/129)
- [Notes on DeepSeek V4's training system — Fireworks AI](https://fireworks.ai/blog/what-deepseek-v4-says-about-training-platforms)
- [Kimi K2 Technical Report — arXiv 2507.20534](https://arxiv.org/abs/2507.20534)
- [Kimi K2.5 Agent Swarm — Kimi Blog](https://www.kimi.com/blog/kimi-k2-5)
- [Post-training Agentic Models: Kimi K2 — DigitalOcean](https://www.digitalocean.com/community/tutorials/post-training-agentic-models-kimi-k2)
- [MiniMax M2.7 Self-Evolution — MiniMax News](https://www.minimax.io/news/minimax-m27-en)
- [MiniMax M2.7 self-evolving — VentureBeat](https://venturebeat.com/technology/new-minimax-m2-7-proprietary-ai-model-is-self-evolving-and-can-perform-30-50)
- [MuonClip Deep-dive — Fireworks AI](https://fireworks.ai/blog/muonclip)

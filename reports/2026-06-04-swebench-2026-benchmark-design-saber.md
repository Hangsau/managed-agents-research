# 研究報告：SWE-bench 2026 Leaderboard 與 Agent Benchmark 設計反思（SABER 啟示）
**日期**：2026-06-04
**來源數**：8 | **標籤**：#benchmark #swebench #agent-eval #saber #mutation-gated

## 1. The Problem
AI agent 領域每年發表數百個 framework（ReAct、Reflexion、AutoGPT、CrewAI、AutoGen、LangGraph...），但**怎麼比較誰好**一直是個痛。SWE-bench 自 2023 發表以來已成為「真實軟體工程任務」de facto 標準；到 2026 年 leaderboard 上頭部系統已達 79.2%（Claude Opus 4.5 + live-SWE-agent），看似接近「解決」。但有三個深層問題浮上檯面：

1. **Benchmark ceiling 是 artifact，不是 model ceiling**。SABER 論文（Cuadron et al., arXiv 2512.07850, 2025-11）系統性審計 τ-bench 與 SWE-bench Verified 後發現：**原始 τ-bench Airline 50 題中 31 題、Retail 115 題中 53 題的 user instruction 有歧義或缺失**；**ground-truth 解答本身有 annotation errors**（例如 Retail 域要求「exchange with different product」但 ground truth 給的 ID 跟原物一模一樣；Airline 域在政策不允許時仍記成成功）。這意味著模型不是「做不到」而是「做到正確但被錯的 ground truth 判負」。修正後釋出的 **τ-Bench Verified** 將 headroom 從 ~70% 推到 80%+，Claude Sonnet 4 從 51.3% → 73.3% (+22 pp) **完全是 benchmark 修正而非模型進步**。

2. **SOTA 數字膨脹、不可重現、不可負擔**。SWE-bench Verified 2026 頭部（live-SWE-agent + Claude Opus 4.5, Sonar Foundation Agent）都靠 1 attempt + 重型 model 達成 79.2%；mini-SWE-agent v2.0.0 + Opus 4.5 完整跑 500 題要 **$377 API 成本**。普通開發者跑不起來也無法做 ablation，只能引用 paper 數字。

3. **「所有 action 等風險」的假設是錯的**。現行 agent 框架對每一步的 scrutiny 相同（end-to-end prompt 評分、整軌 rerun、generic self-reflection），但 SABER 用 logistic regression 證實：**每多一個 mutating action 偏離，success odds 在 Airline 降 55-92%、Retail 降 87-96%**（p<0.001）；**非 mutating action 偏離幾乎無影響**（always <10% reduction, 部分 p 不顯著）。換句話說，agent 失敗的 80%+ 風險集中在只佔步數 14-18% 的 mutating steps。

這個問題之所以重要：當 benchmark 本身有 ceiling effect、所有 framework 都在同一個 broken ruler 上比較，領域的「進步」是錯覺；當 agent 對 irreversible 動作（刪除、付款、取消訂單、刪檔）和 read-only 動作（查詢）給予相同 trust，real-world deployment 風險被嚴重低估。

## 2. Core Mechanism

### 2.1 SWE-bench 2026 評測生態

SWE-bench 在 2026 年的結構演進（從官方 repo + leaderboard）：

```
SWE-bench 家族（2026 變體）
├── Verified（500 題，人工驗證可解）— 主流
├── Lite（300 題，輕量版）
├── Multilingual（9 種程式語言，2026 新增）
├── Multimodal（截圖 + 文字，2025-07 發表）
├── Bash-only（僅 shell 工具，2026 新增）— 強迫「最簡 harness」
└── Test split（500 題私有，需 sb-cli 提交）
```

**頭部系統（截至 2026-06）：**

| 系統 | Model | Verified | 提交日期 | 成本 |
|---|---|---|---|---|
| live-SWE-agent | Claude Opus 4.5 medium | **79.2%** | 2025-12-15 | n/a |
| Sonar Foundation Agent | Claude Opus 4.5 | **79.2%** | 2025-12-05 | n/a |
| TRAE | Doubao-Seed-Code | 78.8% | 2025-09-28 | n/a |
| live-SWE-agent | Gemini 3 Pro Preview | 77.4% | 2025-11-20 | n/a |
| Atlassian Rovo Dev | Claude Sonnet 4 + GPT-5 | 76.8% | 2025-09-02 | n/a |
| **mini-SWE-agent v2.0.0** | Claude Opus 4.5 high | 79.2% | 2026-02-17 | **$377 / 500 題** |
| Qwen3-Coder-480B | (open) | 高分 | 2026 | $0.20-0.50 / 題 |

**mini-SWE-agent** 是 2026 的關鍵 baseline：原始 SWE-agent 100+ 行複雜 prompting，mini 版本**簡化為 100 行 Python code**（swebench 官網稱 "Verified in 100 lines of Python code"），靠 Claude Opus 4.5 high reasoning 達到跟重型 agent 相同的 79.2%。這暗示：**harness 複雜度對 SOTA 的邊際貢獻正在趨近於零**，底層 model 能力是主因。

### 2.2 SABER 的三大組件

SABER（**S**afeguarding Mutating **A**ctions, **B**lock-based filtering, **E**nhanced **R**eflection）不是新 framework，而是**plug-in 層**包在現有 agent loop 外。**不需要 retraining**（gradient-free, model-agnostic），**只需要兩個 model**（main + auxiliary）：

```
┌─────────────────────────────────────────────────────────┐
│  SABER Pipeline                                         │
│                                                         │
│  Trajectory τ  ───►  Block Storage  (embed & retrieve)  │
│       │                                                 │
│       ▼                                                 │
│  Main Model generates candidate action a_t              │
│       │                                                 │
│       ▼                                                 │
│  ┌─ Auxiliary Model ────────────────────────────┐      │
│  │  1. Is a_t mutating? (mutating ≈ 環境改變)    │      │
│  │     ├─ NO  → 執行（bypass verification）      │      │
│  │     └─ YES ↓                                  │      │
│  │  2. Inject Targeted Reflection (重述 constraints)│    │
│  │  3. NL-summary: "我即將取消你的預訂 X，可以嗎？"│    │
│  │  4. 等待 user 確認 → 執行 or 重新規劃         │      │
│  └──────────────────────────────────────────────┘      │
│       │                                                 │
│       ▼                                                 │
│  下一個 query → Block-based context 重新組裝            │
└─────────────────────────────────────────────────────────┘
```

**三大組件：**

**(A) Mutation-gated human verification** — 只在 candidate action 是 mutating 時要求 user 確認。SABER 把 tool call 改寫成自然語言摘要 + 必要前置條件，送回 user 等待 yes/no 確認。Non-mutating（查詢）action 完全不被打擾。**注意：mutating 只佔 14-18% 步數，所以 user 被打擾的頻率約每 6 個 turn 一次**。

**(B) Targeted reflection** — 在 mutating action 前注入蒸餾後的 constraints 摘要到 `<think>` block（推理模型）或 ReAct-style format（無 reasoning 暴露的模型）。這是解「lost-in-the-middle」問題：long context 後 agent 開始忘記 system policy。

**(C) Block-based context cleaning** — 把 trajectory 切成 block，存 `(s_k, e_k)` 摘要嵌入，**只 retrieve top-N 最相關的 block**（N user-configurable）。解「context poisoning」：user 確認記錄塞爆對話歷史後，後面的判斷開始 reference 過期的 confirmation。

### 2.3 關鍵實驗結果（SABER Table 2）

| Benchmark | Model | No-SABER | +SABER | Δ |
|---|---|---|---|---|
| τ-Bench Airline | Qwen3-Thinking-235B | 49.3% | 63.3% | **+14.0 pp** |
| τ-Bench Retail | Qwen3-Thinking-235B | 64.3% | 71.6% | +7.3 pp |
| τ-Bench-V Air | Qwen3-Thinking-235B | 58.5% | **78.2%** | **+19.7 pp** |
| τ-Bench-V Ret | Qwen3-Thinking-235B | 66.9% | 77.7% | +10.8 pp |
| τ-Bench Airline | ChatGPT-5 (med) | 42.6% | 45.1% | +2.5 pp |
| τ-Bench Airline | Claude Sonnet 4 | 62.6% | **76.5%** | **+13.9 pp** |
| SWE-Bench Verified | Qwen3-Thinking-235B | (基線) | +7% rel | +4 pp |

**Ablation（Qwen3-Thinking，τ-Bench-V Air）：**
- No-SABER: 58.0%
- +Reflection only: 66.9% (+8.9 pp)
- +Verification only: 68.0% (+10.0 pp)
- **Full SABER: 78.7% (+20.7 pp)** — 兩者**非線性疊加**（78.7 - 68.0 = 10.7 from reflection 組合，反之亦然）

**輔助 model 配對很重要**：Qwen3-Thinking + Qwen3-Instruct（auxiliary）顯著優於 Qwen3-Thinking + Qwen3-Thinking（auxiliary），暗示 **auxiliary 用「instruction-tuned 守門員」+ main 用「reasoning-heavy 行動者」** 的不對稱分工最佳。

## 3. Why It Matters / Applications

**(1) Benchmark 設計的典範轉移 — 從「分數高」到「評分可靠」**
τ-Bench Verified 的發布意味著：**當你的 agent 在原始 τ-Bench 上分數飽和，先懷疑 benchmark 本身**。SABER 團隊手動審計 165 題、修正 ground truth、擴寫 user instruction 釋出 Verified 版本。SWE-bench Verified 500 題已經過同樣流程（OpenAI x Princeton 2024-08），但其他 benchmark（GAIA、HotpotQA、ToolBench）沒人做。**未來 12 個月可能會看到「Verified 化」運動蔓延**到所有被嚴重依賴的 agent eval。

**(2) 對所有 agent 框架的反思**
- **ReAct / Reflexion**：每步都 self-critique — 過度，浪費 token 在 read-only 步上
- **AutoGPT**：所有 action 等權重 + auto-approve — 危險
- **CrewAI / LangGraph**：orchestration layer 對 mutating action 沒有特殊處理
- **SABER 的教訓**：在 orchestration 層加一個 **action classifier（mutating / non-mutating）** 是必要的安全層，比 prompt engineering 更結構化

**(3) Real-world deployment 隱含成本被量化**
論文用 logistic regression 給出**每多一個 mutating deviation → 55-96% odds reduction**。這是 PR/finance/HR 場景的關鍵數字：1 個錯的退款、1 個誤刪的客戶檔案、1 個錯誤的轉帳 = 1 個 trajectory 失敗。在高風險領域 SABER 的 +20 pp **就是「模型可不可上 production」的分界線**。

**(4) 「小模型 + 好 harness」邊際成本下降**
mini-SWE-agent 100 行 Python + Claude Opus 4.5 = 79.2% = 跟 live-SWE-agent（複雜多步 planning）打平。**對小團隊的訊號**：與其花時間設計複雜 agent loop，不如 (a) 換更好的 model (b) 加 SABER-style 安全網。比 AutoGen / CrewAI 的 swiss-army-knife 設計有效率得多。

## 4. Limitations / Honest Assessment

**SABER 的侷限（作者自承 + 我們的獨立評估）：**

1. **依賴「mutating vs non-mutating」二元分類的清晰定義**。但現實中很多 action 是「半 mutating」（read DB 但會 cache、查訂單但會觸發 audit log），auxiliary model 的判斷本身就是另一個失敗源。論文沒給 false-positive/false-negative rate。

2. **user simulator ≠ 真實 user**。τ-bench 用 Claude Sonnet 4 模擬 user，確認「Yes」過於順從，無法反映真實 user 會反問、誤解、情緒化的情境。**SABER 在真實 production 的增益可能比 paper 低 5-10 pp**。

3. **Block-based retrieval N 是 hyperparameter**。論文用 N=16 但沒系統 sweep；對長 context (1M tokens) 場景 N=16 夠不夠？沒有答。

4. **Ablation 顯示 saturate**。Retail domain Full SABER (77.7%) 跟 +Verification only (80.5%) 接近甚至略低 — 作者承認 "potentially due to benchmark saturation"。意味著**組件不是越多越好**，需要 per-domain 調參。

5. **未解的 ceiling effect**：即使 Verified 版仍有 ~17% 失敗（Claude 在 τ-Bench-V Air 73.3%），是 (a) 模型能力上限 (b) benchmark 仍殘留瑕疵 (c) SABER 本身天花板？論文沒釐清。

**SWE-bench leaderboard 的更深問題：**

6. **Cost-vs-score 曲線無人繪**。Sonnet 4 跑一次 Verified ≈ $50-80，Opus 4.5 ≈ $300-400，Qwen3-Coder-480B（self-host）≈ $0.20/題但要 8×H100 跑一週。**真正的 Pareto frontier 應該是 score/$，但 leaderboard 只列分數**。一個靠開源 30B 模型 + 4-bit quantization 跑 70% 的系統，production value 可能比 Opus + 79% 高很多。

7. **「嘗試次數」遊戲**。1 attempt = 79.2%，2 attempts = ?。SWE-bench 的 convention 是報「一次最佳」，但真實 deployment 會多 sample + rerank。**報 single-attack 數字對比 multi-attack 是 apples-to-oranges**。

8. **Benchmark 偏 Python 生態**。SWE-bench 全是 Django / astropy / sympy / matplotlib 等 Python repo；multilingual variant 雖 2026 推出但樣本量小。**對 Rust / Go / TypeScript 後端的 agent，leaderboard 數字沒有意義**。

## 5. Actionable for Our Projects

### 5.1 對 firn 的具體改進

**(A) 加 Action Risk Classifier（MODERATE 難度，無需付費 API）**

在 firn 的 agent loop 加一層：
```python
# firn/core/action_classifier.py
MUTATION_KEYWORDS = ["delete", "remove", "cancel", "refund", "transfer",
                     "send_email", "publish", "merge", "deploy", "overwrite"]

def classify_action_risk(tool_call: dict) -> str:
    """Return 'mutating' | 'non_mutating' | 'read_only'"""
    if tool_call.get("name") in READ_ONLY_TOOLS:
        return "non_mutating"
    if any(kw in tool_call.get("name", "").lower() for kw in MUTATION_KEYWORDS):
        return "mutating"
    # 用 local model (Qwen3-4B 或 Llama-3.1-8B) 兜底分類
    return local_classifier(tool_call)
```

對 mutating action：暫停 → 把「我即將執行 X，會改變 Y，確認？」送到 user → 等 yes/no。這是 SABER 的 60% 效果、約 200 行 code。

**(B) Block-based context cleaning（MODERATE 難度）**

firn 對話歷史目前是 flat 列表。改成 block 結構：
- 每 5 turns 為一 block，生成 50-word 摘要 + embedding
- 新 query 進來 → embed → cosine sim → 取 top-8 blocks + 最近 3 turns
- 用 sqlite-vec 或 chromadb（本地，零成本）

這直接解 firn 跑久了 context 塞爆、agent 開始 reference 過期狀態的問題。

**(C) Target reflection before mutating（TRIVIAL）**

在 mutating action 前 inject 一次 system policy 摘要：
```python
def targeted_reflection(system_policy: str, last_3_turns: list) -> str:
    """蒸餾出當前約束"""
    return f"REMINDER: {system_policy[:500]}\n最近 3 輪摘要: {summarize(last_3_turns)}"
```

**這是 SABER 三組件中實作成本最低、效益最高的（+8.9 pp 單獨 ablation）**。

### 5.2 對 AGI 自我研究管線的應用

**(D) 建立「firm 自己的 SWE-bench Verified」子集（MODERATE）**

從現有 research script（`research_papers/2025-*`）中**手動審計 20 個 ground truth**，建立 `firn_bench_v1.json`。這呼應 SABER 的發現 — **不要相信單一 benchmark 數字**。每次新模型上線前，在自己 curated 的 20 題上跑 + 比對 leaderboard 數字差距。

**(E) 評估 cost-vs-score Pareto**

寫一個 `eval_pareto.py`：在 SWE-bench Verified Lite 50 題上跑 Qwen3-Coder-30B-A3B-Instruct、deepseek-v3.2、gpt-5-mini、claude-haiku-4-5，分別記錄 score / $ / 延遲。輸出 Pareto frontier plot。

### 5.3 瓶頸

- **需要 GPU 跑 30B+ 模型做 ablate** — Qwen3-Coder-30B-A3B 需要 24GB+ VRAM，本地 4090 (24GB) 勉強可跑 4-bit
- **mini-SWE-agent 的 $377 跑 500 題是必要 baseline** — 沒有這個成本預算就沒法做有意義的對比
- **SABER 的程式碼尚未公開**（paper-only 截至 2026-06），需要自己從 pseudocode 實作。但因為是 prompt-level plugin，難度 MODERATE

## 6. Follow-up Questions

1. **SABER 程式碼什麼時候開源？** — 跟作者（Amazon AGI Foundations）的 Cuadron, Liu, Gupta 確認 release 計劃。如果是 paper-only，目前實作只能從 Algorithm 描述 + Figure 2 pipeline 還原。

2. **τ-Bench Verified 的 GitHub repo 在哪？** — 應在 `sierra-research/tau-bench` 旁邊，但需確認是否有 `verified` branch 或 `tau2-bench-verified` 分支。值得 clone 完整 dataset 比對 Ground truth 差異。

3. **SWE-bench 2026 有沒有 Rust / TS / Go 子集？** — multilingual variant 2026 釋出但樣本量小，未來 6-12 個月是否擴張值得追蹤。

4. **「Auxiliary 用 instruction-tuned」的不對稱配對是普遍法則嗎？** — 跨多個 main model + auxiliary model pair 做 sweep。SABER 只展示 Qwen3 family 內部對比。

5. **Cost-vs-score Pareto** — 2026 H2 會有 paper 繪出 leaderboard 上每個系統的 $ / 分數比嗎？目前沒有，這是研究缺口。

6. **Beyond SWE-bench：其他 domain 的「Verified 化」運動** — GAIA (multimodal browsing)、TheAgentCompany (office tasks)、SWE-bench multimodal — 哪些有同樣的 annotation quality 問題？

7. **SABER 對「multi-step mutating」action 怎麼處理** — 例如「先查訂單 → 取消 → 重訂 → 退款」，4 步都是 mutating，user 要確認 4 次嗎？paper 沒探討 batching。

---

### 原始來源

1. **https://arxiv.org/abs/2512.07850** — 論文 — **HIGH** — SABER: Small Actions, Big Errors（Cuadron et al., Amazon AGI, 2025-11-26）。τ-bench 系統審計 + mutation-gated safeguard 完整設計
2. **https://www.swebench.com/** — Leaderboard + docs — **HIGH** — SWE-bench 2026 官方 leaderboard 數據（Claude Opus 4.5 = 79.2%, mini-SWE-agent v2.0.0 = $377 / 500 題）
3. **https://github.com/SWE-bench/SWE-bench** — Repo + README — **HIGH** — SWE-bench 官方 repo、Multimodal 2025-07 整合、Docker 化評測（2024-06）、Verified 釋出（2024-08）
4. **https://github.com/sierra-research/tau-bench**（1257 ★）— Repo — **HIGH** — τ-bench 原始碼，作者 Sierra Research
5. **https://github.com/SWE-agent/mini-swe-agent** — Repo — **HIGH** — mini-SWE-agent v2.0.0，"Verified in 100 lines of Python code"，79.2% 達成
6. **https://github.com/SWE-agent/SWE-agent** — Repo — **HIGH** — 原始 SWE-agent，ICLR 2024 起始 SOTA
7. **https://www.anthropic.com/engineering/building-effective-agents** — Blog — **HIGH** — Anthropic 2024-12-19 經典文章：workflows vs agents、why simple patterns win
8. **https://api.github.com/search/repositories?q=tau-bench** — GitHub search API — **MEDIUM** — 確認 τ-bench / τ2-bench 的 fork 與 verified 版本分布

---

**下一個工作日排程執行本指令。**

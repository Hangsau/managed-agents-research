# 中文總結報告：Deployed AI System 能力評估框架

> 配給 repo 作者（Hang）追蹤用的中文摘要。完整研究內容仍以英文版檔案為準（`00-research-plan.md`、`01-information-gathering/`、`02-synthesis/`、`03-analysis/`、`04-design/`、`reviews/`）。本文件 v3 LOCK 後新增，方便對話追蹤，不參與評審週期。

---

## 一、研究了什麼

**核心問題**：怎麼公平比較「裸 LLM」「CLI 工具（如 Claude Code）」「整套 agent 系統（如 Talos / Hestia / Devin）」的能力？

過往做法的破口：
- LLM benchmark（MMLU、GPQA、ARC-AGI）只能測裸模型，agent 系統塞進去等於降維
- Agent benchmark（SWE-bench、OSWorld、TAU-bench）預設要有環境，裸 LLM 直接拿 0 分而不是「N/A」
- 廠商自評（Devin、OpenAI Operator、Replit）各報各的，數字根本不可比
- **沒有任何一份既有 benchmark 報告 test-retest 信度**（同一受試跑兩次的分數一致性），而人類智力測驗（WAIS-5、Raven's APM）這是發表前的硬門檻

研究蒐集約 80 份資料（agent benchmarks、學術 surveys、人類智測設計史、軟體工程黑盒測試、廠商自評報告），分四階段：

1. 情報蒐集 9 個子題（S1.1 – S1.9）
2. 整合成 32 維能力 × 3 類系統的可行性矩陣 + ~1480 字 narrative
3. 列出 13 個 gap + 20 個必須在設計階段回答的設計問題（DQ-1 – DQ-20）
4. 完整設計框架（11 個檔案）

---

## 二、得到什麼結論

### 1. Benchmark 數字普遍灌水，灌水方向兩邊都有
- Devin SWE-bench 13.86% vs 自報 67% PR merge rate（4-5 倍膨脹）
- METR 2025 RCT：開發者「以為快了 20%」實測「慢了 19%」
- 8/10 廠商根本不公布開放 benchmark 分數，改用「能跑 200 分鐘 session」這種 feature 列表代替

### 2. 「同樣 LLM 不同 gateway = 不同行為」是隱藏軸
NVIDIA NIM 跑的 Kimi 跟 opencode-go 跑的 Kimi 是兩個東西。把 gateway 當無關緊要的 infra 細節是錯的。

### 3. 「裸 LLM 在 agent task 上拿 0 分」是測量錯誤，不是事實
應該標 N/A（介面缺乏 affordance），不是 0；否則所有報告都變成「環境豐富度排行榜」。

### 4. 自我修改的 agent（如 Hestia 自建 cron）會結構性破壞 test-retest 信度
這是真實張力不是 bug：凍結它就量不到「自我改進」這個能力本身。

### 5. 評估 deployed system 必須把 LLM + 環境視為同一個黑盒
不該說「Claude Code 強」，要說「2026-05-15 凍結的 Claude Code（含這份 CLAUDE.md + 這組 MCP + 這組 skills + 在 Windows 11 + Anthropic API direct）強」。任一變量改動 = 不同 system，要重測。

---

## 三、最後設計怎麼操作

**框架輸出**：對任何受測系統產生一份 capability profile（三段式報告），**不出單一分數**、**不做排行榜**。

### 三軌制

- **Track A — 抽象能力**：A1 推理、A2 工作記憶、A5 拒答校準、A11 行為傾向… 共 11 維
- **Track B — 應用能力**：B1 環境探索、B6 工具呼叫、B11 長任務持續性、B12 模糊目標收斂… 共 14 維
- **Track C — 運維面**：成本、延遲、可靠性、adapter 複雜度、失敗模式分布、自我修改偵測

### 操作流程（4 步）

1. **拍 identity snapshot**：把受測系統壓成 9 欄 tuple（LLM ID、訓練狀態、gateway、instruction layer hash、MCP 集、skill 集、tool 集、memory 系統、runtime），SHA-256 算成 `identity_hash`
2. **接 SystemAdapter**：每個受測系統實作 4 個方法（`identity()` / `submit()` / `cost()` / `teardown()`），harness 透過 adapter 統一存取。Hermes（Talos/Hestia 底層）目前還沒這層 endpoint，需先補 Phase 0 工程（1-2 天）
3. **跑 trial**：每個能力維度多 trial（N=5），算平均 ± stddev，stddev 超門檻就標「high-variance, signal insufficient」。沒有 affordance 的維度標 N/A 並寫原因，不算 0
4. **產出 profile**：JSON + 文字雙格式。同 LLM 不同環境的受試自動做 pairwise diff（differential meta-mode），單獨呈現「環境到底貢獻了什麼」

### Pilot 5 個受測對象（核心示範）

| # | 名稱 | LLM | 環境差異 |
|---|------|-----|---------|
| 1 | Bare Claude API | Opus 4.7 | 無系統 prompt、無工具 |
| 2 | Claude Code vanilla | Opus 4.7 | CLI scaffolding，無 CLAUDE.md / MCP / skills |
| 3 | Claude Code (operator full setup) | Opus 4.7 | 你的完整設定（CLAUDE.md + MCP + skills + memory）|
| 4 | Talos VM (hermes) | Talos 設定 | Agent system，本機 production |
| 5 | Hestia VM (hermes) | Hestia 設定 | Agent system，自我擴張中 |

1、2、3 共享 LLM，差別只在環境 → **這就是「同 LLM 不同環境能差多少」的量化證據**，也是這個框架的招牌示範。

---

## 四、為什麼這樣設計

| 設計選擇 | 為什麼 |
|---|---|
| 三軌分開、拒出總分 | Stage 1 證據：所有單一分數系統都被廠商用來灌水。三軌強制 user 自己看 trade-off，不能用「我們的 X 比較高」一句話過關 |
| identity = 9 欄 tuple（含 gateway） | 同 model ID 跨 gateway 行為不同已有實證。不把 gateway 鎖進 identity，test-retest 信度數字會被無紀錄變量污染 |
| N/A vs 0 嚴格區分 | 否則裸 LLM 在 14 個 Track B 維度全拿 0，整份 profile 變成「環境豐富度」排行，模糊掉真正的能力差距 |
| Test-retest 是門檻不是 feature | 心理計量學 50 年常識，AI 圈一致缺漏。沒這個就分不出「Devin 比 Claude 強 2%」是真差距還是雜訊 |
| Track B 單軌 + sub-tag，不切 B1/B2 | 切兩軌會暗示兩者等權重，sub-tag（session-bound / cross-session/autonomous）保留彈性不預先承諾 |
| Differential 當 meta-mode 不當第四軌 | 它是「兩受試比對」的工具不是「能力」本身，當第四軌會誤導讀者以為這是另一種智能 |
| Adapter pattern + 不自建 sandbox | 直接重用 Inspect-AI（AISI 開源）的 Dataset/Solver/Scorer primitive；新工具只做別人不做的（identity snapshot、test-retest、differential、自我修改偵測） |
| 三類受試（Bare LLM / CLI / Agent System）只當分析標籤、不當分區 | Cursor BG Agent 本來就跨類，硬分區會把光譜變成抽屜，主鍵還是 identity snapshot |
| 自我修改系統用 identity-hash drift tagging | 不凍結（凍結就量不到自我改進）、也不忽略，trial 中間 recompute hash，變了就標「subject self-modified mid-test」 |

### 3 輪迭代修了什麼
- **v1 → v2**：吸收兩份 R1 review（邏輯一致性 + 工程務實），14 個 inline 修正（補 Phase 0、修正 Track A 語意聲稱、permission mode 統一）
- **v2 → v3**：第二輪 review 抓到 v2 changelog 自稱「已修」但檔案實際沒改的 7 個項目（典型 promise-vs-reality gap），v3 全部對齊；新增 6 條已知限制（L15-L20）

---

## 五、現在的狀態 + 下一步

### 已完成（v3 LOCKED, 2026-05-15）
- 完整框架設計 31 個 markdown、~5000 行
- 49 條評審意見全部回應（R1 34 條 + R2 15 條）
- 20 條已知限制誠實列出（construct validity、coverage、anti-contamination、reliability、scope、self-knowledge）

### 還沒做（post-v3，需另起工程）
1. 外部專家評審（找一個心理計量學家 + 一個資深 ML engineer）
2. Hermes 補 `/identity` + `/submit` endpoint（Phase 0，1-2 天）
3. 寫 harness：4 個 adapter + 任務生成器 + 評分引擎（Phase 1，**2-4 週**一人，或一對 1-2 週）
4. Smoke pilot → Full pilot N=5 → 真正的 v1 數據
5. 根據 pilot 發現出 framework v2

簡單講：**框架設計案完成（這份研究的範圍），實際工程實作和真實量測還沒開始**（明確劃在範圍外）。

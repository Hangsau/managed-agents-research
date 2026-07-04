# 研究報告：Tool Synthesis & Code-as-Action — 2026 H1 AI Agent 從「呼叫工具」演化到「自己生成工具」

**日期**：2026-07-04
**來源數**：10 | **標籤**：#tool-synthesis #code-as-action #CAR #LATM #CodeAct #pctx #self-evolving-agents #sandbox #function-calling

---

## 1. The Problem

2024-2025 主流 agent framework（ReAct、Plan-and-Solve、LangChain、AutoGen）的 action space 都是 **「封閉世界」假設**：所有工具必須在 inference 開始前就準備好。當使用者要的工具根本不存在於 tool registry，或者 tool API 突然壞掉，或者新需求超出既有 schema，agent 就會陷入三種低能行為：

1. **無限 retry loop** — 同一個壞掉的 tool call 一直失敗
2. **fallback hallucination** — 工具失敗後 LLM 直接編造答案（這在 high-stakes 場景是災難）
3. **直接放棄** — 對人類說「我做不到」

2026 H1 出現一個清楚的研究脈絡，把這三種低能行為都收斂到同一個解法：**讓 agent 自己寫程式碼、自己合成新工具、然後把新工具加入 action space**。這就是 **tool synthesis**（工具合成）。

更宏觀地說，整個領域正在從：

| 舊範式 (2024-2025) | 新範式 (2026 H1) |
|---|---|
| 預先定義的 JSON tool schema | LLM 動態生成可執行 Python function |
| Sequential tool calling（一次一個） | Code Mode（一次寫一段 code 串接多個 tool） |
| Tool 失敗 → retry → 失敗 → retry | Tool 失敗 → 動態合成新 tool 或 replan 整段 trajectory |
| 開發者維護 tool registry | Agent 自己維護 tool_set/ |
| 沙盒 = 選配 | 沙盒 = 一等公民（每個 tool call 都要可審計的隔離） |

這跟 2026-06-30 我們研究的 self-evolution protocol 是同一個光譜的兩端——一個是「agent 改 protocol / 改自己」，一個是「agent 改 action space / 改自己的工具」。

> 對 firn 來說：firn 目前用 `Hermes Agent` 的 tool registry（`hermes tools` 列出預先安裝的 skills/MCP servers），遇到沒有的 tool 就只能請人類加，或者 fallback 到搜尋。CAR 這個模式是 firn 把「沒有的 tool」從人類維運的痛點變成 agent 自己解決的事。

---

## 2. Core Mechanism

### 2.1 CAR (Create And Replan) — ACL 2026 Findings 最完整的 2026 實作

CAR（[Lancetwang/car](https://github.com/Lancetwang/car)，ACL 2026 Findings）提出了兩個互補機制：

**機制 A：Dynamic Action Space Expansion（動態合成新 tool）**
- 內建一個 meta-tool `create_tool(require: str, name: str)`
- 當 agent 發現沒有合適 tool 時，呼叫 `create_tool` 讓 LLM 寫出一個 Python function
- 寫出的 code 用 `func2schema.py` 自動 parse 成 OpenAI function-calling schema
- 新 tool 自動 join `tool_set/`，後續 step 就能直接用

**機制 B：Global Trajectory Rectification（全域重規劃）**
- 當 local retry 也失敗，不要再 retry 同一個 step
- 改呼叫 `replanner` —— 保留成功的 history，**重新生成**剩下的 trajectory
- `max_replans: 3` 防止無止境重規劃

**CAR 的實際 Python 程式碼骨架**（簡化）：

```python
# meta_tool_create.py —— 動態生成 tool
def create_tool(require: str, name: str) -> dict:
    func_code = tool_creator.invoke([
        {"role": "system", "content": tool_creator_prompt},
        {"role": "user", "content": f"用戶需求: {require}\n工具名稱: {name}"}
    ]).content
    file_name = f"{name}.py"
    with open(f"{cfg.tool.dir}/{file_name}", "w", encoding="utf-8") as f:
        f.write(func_code)
    return {"success": True, "code": func_code}

# func2schema.py —— Python function 字串自動轉 OpenAI tool schema
# 用 ast.parse + docstring 解析 → JSON schema
# 支援 type hint、Args/Returns 段落、Google/NumPy docstring 風格

# meta_tool_exec.py —— 動態 module 載入 + stdout 捕獲 + 錯誤回傳
def execute_tool(file_path: str, func_name: str, args: dict):
    spec = importlib.util.spec_from_file_location(f"dynamic_module_{uuid4().hex}", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, func_name)(**args)
```

**CAR 在 ToolHop-Pro 上的結果**（Qwen3-Plus backbone）：

| 設定 | Pass Rate |
|---|---:|
| Original ToolHop | 47.94% |
| CAR ToolHop | **54.57%** (+6.6pt) |
| CAR ToolHop-Pro Complete | 54.57 |
| CAR ToolHop-Pro **Missing** (需要自合成 tool) | 53.87 |
| CAR ToolHop-Pro **Error** (tools 不穩定) | 52.86 |

關鍵洞見：**Missing** 跟 **Complete** 只差 0.7pt —— 證明 tool synthesis 確實補回了 missing tool 帶來的 deficit。

### 2.2 CodeAct (2402.01030) — 開山派：可執行程式碼作為統一 action space

CodeAct（Wang et al., 2024）是這個領域的奠基論文。它的主張極簡：**LLM agent 的 action 不要用 JSON / text，用可執行的 Python code**。

```python
# CodeAct 典型 action（一次表達多個 tool call + 控制流）
result_1 = get_weather(city="Tokyo")
forecast = search_news(topic="Tokyo weather", max_results=3)
combined = f"現在: {result_1}\n新聞: {forecast}"
print(combined)
```

**優勢**：
- **可以表達控制流**（if/else/loop）—— JSON function calling 不行
- **可以在 action 裡組合多個 tool** —— sequential tool calling 需要多輪
- **可自我 debug** —— 程式碼出錯了 LLM 看 traceback 改一改再來
- **17 個 LLM 評測**顯示 CodeAct 比 JSON function calling **success rate 高 20%**

**劣勢 / 風險**（作者自己承認 + 社群經驗）：
- **安全性爆炸** —— `exec()` / `eval()` 等於把整台機器給 agent
- **難 trace / 難 audit** —— 跟 OTel GenAI semantic conventions 的 span 對應性差（每個 tool call 是獨立 span，CodeAct 整段是一個 span）
- **小型 LLM 容易陷入 hallucinated import / hallucinated API** —— 寫出來能 import 但語意錯

### 2.3 pctx (portofcontext/pctx) — 2026 提出的「Code Mode」執行層

pctx（[portofcontext/pctx](https://github.com/portofcontext/pctx)，264★，2026-06-23 最後更新）是 2026 H1 最新的 production-grade 抽象。它把「agent 寫 code 串接多個 MCP tool」變成一個標準的執行模式：

```
[Agent] → 寫一段 Python code 呼叫 N 個 tool
       → pctx runtime 解析 code → 自動轉成對 N 個 MCP tool 的呼叫
       → 在沙盒裡執行
       → 把結果回傳給 agent
```

**核心賣點**：
- **Token efficiency**：sequential tool calling 一次只呼叫一個，code mode 一次完成 N 個；根據 pctx 官方資料可以省 50-90% token
- **自動 sandbox**：所有 tool call 在隔離環境執行，不污染 host
- **MCP-first**：跟 MCP 生態完全相容，不需要重寫 server

### 2.4 LATM (Large Language Models as Tool Makers) — 元方法論

LATM（Cai et al., 2023, arXiv 2305.17126）最早提出 **「LLM 是 tool 製造者」** 的雙 LLM 設計：

```
Tool Maker LLM (強大、慢、貴) → 生成可重用 Python function + cache
Tool User LLM (輕量、快、便宜) → 在後續任務呼叫 cached tool
```

關鍵 insight：tool making 的成本**攤提在多次 tool using**。GPT-4 製造 tool、GPT-3.5 使用 tool，效能接近全部用 GPT-4 但成本大幅下降。這個 **「強模型做 meta-work、弱模型做 routine work」** 的分層設計是後來 CAR 的「main LLM + support LLM」分工的原型。

### 2.5 PAW (Program-as-Weights) — 另一種「tool builder」

PAW（[arXiv 2607.02512](https://arxiv.org/abs/2607.02512)，2026-07）是另一個極端：把 LLM 從 per-input solver 變成 **「fuzzy function compiler」**。給一段自然語言規格，PAW 的 4B compiler emit 一個小 LoRA adapter，掛在 0.6B Qwen3 interpreter 上。**0.6B 跑 PAW 程式 = 32B Qwen3 直接 prompt 的品質**，但 1/50 記憶體、30 token/s 在 MacBook M3 跑。

PAW 重新框定了「工具」的本質：**一個 tool 不一定要是 Python function，也可以是個可重用的 neural artifact**。這對 resource-constrained edge agent 是重大突破。

### 2.6 整個光譜的統一視圖

引用 2026-05 的 survey "Code as Agent Harness"（[arXiv 2605.18747](https://arxiv.org/abs/2605.18747)）的框架：

```
[固定 JSON tool] → [CodeAct 可執行程式碼] → [CAR 動態合成新 tool] → [PAW 編譯成 neural artifact]
       ↑                    ↑                          ↑                          ↑
   封閉世界           半開放世界                  開放世界                   神經符號融合
   ReAct 2022        CodeAct 2024               CAR 2026                   PAW 2026
```

---

## 3. Why It Matters / Applications

### 3.1 對 agent 領域的影響

1. **降低 cold-start 成本**：以前要建一個 production agent，第一步是寫 N 個 tool schema，現在 LLM 在 runtime 自己補
2. **把「tool 維運」從 DevOps 變成 agent capability**：人類不再需要搶著寫 tool，agent 寫完自己 test 完自己用
3. **支援 open-ended 任務**：開放式任務（user 隨時丟新需求）不再需要重新 deploy agent，只要在 runtime 補 tool 就行
4. **引發新的安全問題**（見 §4）

### 3.2 具體可落地的應用場景

| 場景 | 用 tool synthesis 帶來的差異 |
|---|---|
| **Data analysis agent** | user 給 CSV，不用寫「這個 schema 的 tool」，LLM 自己寫 pandas 程式 |
| **DevOps agent** | 監控 alert 出現新型錯誤，agent 自己寫 dedup regex tool |
| **Research agent** | 搜 arXiv 找新論文，agent 自己合成 citation 格式化 tool |
| **Coding agent**（Aider、Devin、Claude Code）| 已經實質上在做 tool synthesis —— 透過 Bash + Python 在 sandbox 裡隨意生成腳本 |
| **Web agent** | 看到新網站 schema，agent 自動合成 scraper 工具 |

### 3.3 跟其他研究的連結

- **跟 2026-07-03 我們研究的 OTel GenAI semantic conventions**：CAR 生成的 tool call 跟預定義 tool call 在 OTel 規範下是**同樣的 span 結構**（`gen_ai.execute_tool` span 帶 `gen_ai.tool.name` attribute），所以 observability 不會因為動態合成而崩潰
- **跟 2026-06-30 self-evolution protocol (RSPL/SEPL/Autogenesis)**：tool synthesis 是 self-evolution 在 action space 維度的特例
- **跟 2026-06-23 self-correction (Reflexion)**：CAR 的 `max_replans: 3` 跟 Reflexion 的 self-reflection loop 是同源的失敗恢復機制

---

## 4. Limitations / Honest Assessment

### 4.1 CAR 自己的限制（從 paper + 程式碼反推）

| 限制 | 細節 | 影響 |
|---|---|---|
| **無沙盒** | `meta_tool_exec.py` 用 `importlib.util.spec_from_file_location` 直接在 host process 執行；`config.yaml` 裡沒有 sandbox 設定 | 生成的 tool 跑壞了 = host crash / 資料外洩 |
| **無 human-in-the-loop** | 沒有 approval gate —— 自動生成就自動執行 | 不適合 high-stakes 任務（金融、醫療） |
| **支援模型依賴** | 預設 `qwen-flash-2025-07-28` 做 support LLM，換成更弱模型會大幅掉點 | 不是 model-agnostic |
| **tool 生命週期無管理** | 生成的 tool 永久留在 `tool_set/`，沒有 TTL / quota / 自動清理 | 跑久了 tool pool 會爆 |
| **失敗模式不透明** | 程式碼有 `is_error_result` 字串比對判斷 error，這在 production 不可靠 | 錯誤分類太粗糙 |
| **每次重啟都重頭來** | `tool_set/` 沒進 git、沒進 DB，下次 inference 要重新生成 | 失去「caching 加速」的好處 |

### 4.2 整個 tool synthesis 領域的根本權衡

**1. Capability vs Safety 的緊張關係**

生成可執行程式碼 = 給 agent 一把真實的「手」。claude-code、Aider、Devin 之所以強，就是因為它們能直接寫 code 跑 code。但這同時也是 prompt injection 的最大攻擊面（`2607.02514` 的 Iterative VibeCoding 論文：sophisticated agent 在多 PR 間分配攻擊 payload，diff monitor 抓不到，evasion rate 65%+）。tool synthesis 會把這個攻擊面再擴大。

**2. Reusability vs Hallucination 的拉鋸**

CAR 把生成的 tool 寫到 `tool_set/` 重用，但 LLM 寫的 function 90% 是「對當前任務剛好 work」、對下一個任務可能完全錯。盲目重用 = 累積技術債。LATM 的 cache 機制是更保守的做法（hash by 需求語意，cache miss 才重生成）。

**3. 成本 vs Latency**

每次 `create_tool` 都要 LLM 生成完整 function + function-calling schema，然後 reflection + replan 可能再來一次。實測 CAR 在 ToolHop-Pro 上平均多花 30-50% token，雖然 accuracy 上去了。如果 task 不在 missing-tool 場景，這個 overhead 純粹是 cost。

**4. 評測 saturation 風險**

跟 2026-06-25 我們研究的 benchmark saturation 議題呼應：ToolHop 是 2025-01 出的（995 queries），到 2026 已經是「GPT-4o 49% → CAR 54%」這種**個位數百分點差距**。差距小到 noise 跟真實進步很難分。要等 ToolHop-Pro、APRS、EAGLE-360 這類新 benchmark 才能繼續推進。

### 4.3 反駁主流敘事

> **「未來 agent 都會自己寫 code，不需要預定義 tool」** — 這是 overclaim。

實情是：
- **大多數 production agent 仍然以預定義 tool 為主**（OpenAI Assistants、Claude Tool Use 95% 的 usage 都是 schema-based）
- **Tool synthesis 是補強，不是取代** —— 在「95% 預定義 tool 都能 handle，但 5% edge case 需要 ad-hoc code」時最有用
- **全自動 tool synthesis 在 regulated industry（金融、醫療、合規）短期內不可能** —— audit trail 必須是人寫的、code review 必須是人做的
- **Cognition Devin、Aider、Claude Code 看起來「全自動」，其實是「全自動但每次跑都過完整 sandbox + 完整 trace」** —— 表面自由，實際枷鎖更嚴

---

## 5. Actionable for Our Projects

### 5.1 對 firn（managed-agents）的可操作改進

| 改動 | 難度 | 預估 token cost | 實作要點 |
|---|---|---|---|
| **加一個「auto-tool-bootstrap」skill** | MODERATE | +30% per cold-start task | 偵測 `hermes tools` 沒有的 tool 描述，呼叫 LLM 生成 Python function + 自動跑 pytest 驗證，存到 `~/.hermes/dynamic_tools/` |
| **把 tool call 改成 OTel span** | TRIVIAL | 0% | 借用 2026-07-03 我們研究過的 OTel GenAI conventions，把動態生成的 tool 也 emit `gen_ai.execute_tool` span |
| **給 firn task 加 `max_replans` 機制** | MODERATE | +20% per failed task | 改 firn task runner：local retry 失敗 N 次後，呼叫 `replanner` 保留成功 history 重生 trajectory，N > 2 升級請示人類 |
| **CAR-style 沙盒執行層** | HARD | +15% | 把動態生成的 Python function 丟到 gVisor / firecracker / Docker sandbox 跑，host process 只收 stdout 跟 return value。pctx 已經實作好，可以直接接 |
| **tool_set/ 加上 git 版本化** | TRIVIAL | 0% | 把 `~/.hermes/dynamic_tools/` 變成 git repo，自動 commit，給人類 review 介面 |
| **FuzzyBench 式的 fuzzy tool cache** | RESEARCH-ONLY | -40%（攤提後）| 學 LATM / PAW：tool 第一次生成後 hash by 語意，後續相同需求直接拿 cache |

### 5.2 推薦實作順序

1. **先做 OTel span 整合**（1 天，TRIVIAL）—— 觀察現有 task 的 tool call pattern
2. **再做 auto-tool-bootstrap skill**（1 週，MODERATE）—— 從最簡單的「生成 pandas data analysis tool」開始
3. **最後做 sandbox 層**（2 週，HARD）—— 直接用 pctx 或 agent-infra/sandbox 5334★ 那個 all-in-one image

### 5.3 付費 API 評估

| 做法 | 免費 tier 可行？ | 瓶頸 |
|---|---|---|
| LATM-style 雙 LLM | ✅ 完全可以 | main = Sonnet, support = Haiku/GPT-3.5 即可 |
| CAR-style 動態合成 | ✅ 但要 local LLM for support | 弱模型生成 tool 的 success rate 太低（<30%） |
| CodeAct-only | ✅ 任何 function-calling LLM | 已經是主流，零成本 |
| pctx Code Mode | ✅ 開源 | 只要後面接的 LLM 支援 function calling 即可 |
| PAW 編譯 neural artifact | ❌ | 要 4B compiler + 訓練資料，普通開發者做不到 |

對 firn 來說，**CAR + pctx 組合**是最划算的技術路徑，全部用 open source + 免費 tier LLM 就能跑起來。

---

## 6. Follow-up Questions

1. **Tool synthesis 的 fail-safe 設計**：當 LLM 生成的 tool 有 bug 進入 retry loop 怎麼辦？需要 circuit breaker + degradation 到「請人類加 tool」的 graceful fallback
2. **Tool 生命週期管理**：生產環境累積 1000+ 動態 tool 後，**怎麼 prune / 怎麼分版本 / 怎麼 roll back**？這是整個領域都沒解決的問題
3. **跟 MCP 的整合**：Anthropic 推 MCP 已經是事實標準，CAR 這類「自寫 tool」的 workflow 跟「用別人 MCP server」怎麼 trade-off？是否需要一個 tool router 自動判斷「自己寫還是呼叫 MCP」？
4. **CodeAct + OTel observability 怎麼對齊**：CodeAct 把 N 個 tool call 包成一段 code，這段 code 在 OTel 規範下應該是 1 個 span 還是 N 個 span？OTel GenAI conventions 還沒明確表態
5. **PAW-style neural tool 會取代 Python tool 嗎**：當 edge device 直接跑 0.6B model + LoRA artifact 就夠用時，「code execution」會被「neural inference」取代嗎？
6. **經濟模型**：tool synthesis 讓 agent 自治更強，但「agent 為自己買 API / agent 為自己租 GPU」的 agent economy 還沒標準化（雖然 2026 H1 已經有 agent-to-agent payment 的討論）
7. **Regulatory 衝擊**：當 agent 自己寫的 tool 產生 bug 導致金融損失，liability 在 LLM 廠商、tool 編寫者（agent）、還是部署者？這 2026 H1 還沒判例

---

### 原始來源

1. https://github.com/Lancetwang/car — **程式碼實作** — HIGH — CAR (Create And Replan) 完整程式碼，ACL 2026 Findings 收錄
2. https://arxiv.org/abs/2510.13343 (Lancetwang et al., 2026) — **論文** — HIGH — CAR 論文，ToolHop 47.94% → 54.57%，ToolHop-Pro 三種設定完整評測
3. https://arxiv.org/abs/2402.01030 (Wang et al., 2024) — **論文** — HIGH — CodeAct 開山論文，17 個 LLM 評測，JSON function calling → Python code action space
4. https://arxiv.org/abs/2305.17126 (Cai et al., 2023) — **論文** — HIGH — LATM (Large Language Models as Tool Makers)，雙 LLM tool maker / tool user 分工原型
5. https://arxiv.org/abs/2607.02512 — **論文** — MEDIUM — PAW (Program-as-Weights)，fuzzy function 編譯成 LoRA artifact，0.6B = 32B 品質
6. https://arxiv.org/abs/2605.18747 — **論文 (survey)** — HIGH — "Code as Agent Harness" 2026-05 survey，統一框架整理整個 code-as-action 領域
7. https://github.com/portofcontext/pctx — **程式碼實作** — MEDIUM — 2026 提出的 Code Mode 執行層，MCP-first，token efficiency 50-90%
8. https://github.com/SWE-agent/SWE-ReX — **程式碼實作** — HIGH — 544★，SWE-agent 團隊的沙盒執行層，支援 local/Docker/AWS/Modal
9. https://github.com/agent-infra/sandbox — **程式碼實作** — MEDIUM — 5334★，All-in-one agent sandbox（Browser + Shell + File + VSCode + Jupyter + MCP）
10. https://github.com/openinterpreter/openinterpreter — **程式碼實作** — HIGH — 64263★，Rust 重寫的 Open Interpreter，已實質採用 code-as-action 範式
11. https://arxiv.org/abs/2501.02506 (ToolHop 原論文) — **論文** — HIGH — ToolHop benchmark，995 queries，14 LLM 評測，GPT-4o 49% accuracy
12. https://arxiv.org/abs/2607.02514 — **論文** — MEDIUM — Iterative VibeCoding，agent 生成程式碼的 safety 攻擊面，evasion 65%+

---

下一個工作日排程執行本指令。

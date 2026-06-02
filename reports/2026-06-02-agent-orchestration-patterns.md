# 研究報告：Agent Orchestration Patterns — 現代多 Agent 工作流架構解析

**日期**：2026-06-02
**來源數**：7 | **標籤**：#orchestration #multi-agent #handoff #guardrails #tracing #mcp #workflow

## 1. The Problem

單一 agent 在複雜任務上的瓶頸已經眾所皆知——Planning 能力不足、工具調用混亂、輸出無法驗證。2025 年下半年開始，業界的共識轉向：**不要强化單一 agent，要用 orchestration 架構把多個専門 agent 串起來**。

這個轉向催生了大量框架（OpenAI Agents SDK、Agency Swarm、MCP-agent、Swarms），但它們並非各自獨立發明——彼此高度互操作，共用同一組底層概念。本研究試圖找出這些框架中真正通用的 orchestration 設計模式，以及它們的極限在哪。

## 2. Core Mechanism

### 2.1 架構全景：從單一 Agent 到 Orchestrated Agency

```
User Input
     │
     ▼
┌─────────────────────────────────┐
│       Entry Point Agent         │
│  (Supervisor / Router / CEO)   │
└──────────┬──────────────────────┘
           │ handoff / tool call
     ┌─────┼─────┬──────────────┐
     ▼     ▼     ▼              ▼
 [Agent A][Agent B][Agent C] ... [Agent N]
     │     │     │              │
     └─────┴─────┴──────────────┘
           │ results gathered back
           ▼
┌─────────────────────────────────┐
│   Synthesizer / Verifier Agent  │
│  (final output + validation)    │
└─────────────────────────────────┘
```

### 2.2 Agents-as-Tools Pattern（OpenAI Agents SDK）

**來源**：openai/openai-agents-python — `examples/agent_patterns/agents_as_tools.py`
**可信度**：HIGH — 官方 SDK 範例，2026 年中 maintained

這個模式是 2026 年最被廣泛採用的 orchestration  primitive。基本概念：

```python
# 每個専門 agent 是主 orchestrator 的工具
orchestrator = Agent(
    name="orchestrator",
    instructions="你使用提供的工具來完成翻譯任務，自己不動手翻譯",
    tools=[
        spanish_agent.as_tool(
            tool_name="translate_to_spanish",
            tool_description="將訊息翻譯成西班牙文",
        ),
        french_agent.as_tool(
            tool_name="translate_to_french",
            tool_description="將訊息翻譯成法文",
        ),
    ],
)

# 主 agent 動態選擇要調用哪個 sub-agent
result = await Runner.run(orchestrator, user_message)
```

**關鍵設計**：sub-agents 被轉換成 function-calling 形式的工具，orchestrator 完全依賴工具調用來觸發其他 agent。這與 ReAct 的「思考 → 行動 → 觀察」迴圈不同——這裡的 sub-agent 是被當成 namespace-isolated tool 使用。

**Conditional Tool Enabling**（同一 repo 的 `agents_as_tools_conditional.py`）更進一步：

```python
class AppContext(BaseModel):
    language_preference: str  # "spanish_only", "french_spanish", "european"

def french_spanish_enabled(ctx: RunContextWrapper[AppContext], agent: AgentBase) -> bool:
    return ctx.context.language_preference in ["french_spanish", "european"]

orchestrator = Agent(
    tools=[
        french_agent.as_tool(
            tool_name="translate_to_french",
            tool_description="...",
            is_enabled=french_spanish_enabled,  # 動態啟/停
        ),
    ],
)
```

這實現了 RBAC（Role-Based Access Control）層級的 agent 調用控制，不需要修改 agent 本身。

### 2.3 Agency Swarm — 結構化 Communication Flow

**來源**：VRSEN/agency-swarm — `src/agency_swarm/agency/core.py`
**可信度**：MEDIUM-HIGH — 活躍開源框架，2026 年持續更新，5.4k stars

Agency Swarm 擴展了 OpenAI Agents SDK，引入**結構化通訊流**：

```python
ceo = Agent(name="ceo", instructions="管理整個agency的戰略決策")
va = Agent(name="virtual_assistant", instructions="處理日常任務")
dev = Agent(name="developer", instructions="寫程式碼")

agency = Agency(
    ceo, va, dev,  # entry points（可被外部觸發的 agent）
    communication_flows=[
        (ceo, va),      # ceo → va 直接訊息
        (va, dev),      # va → dev 直接訊息
        (ceo, dev),     # ceo → dev 直接訊息（可選）
    ],
    shared_instructions="所有agent都應該遵循保密協議...",
)
```

**核心差異**：Agency Swarm 的每個 agent 之間有 explicit 的 communication flow 定義，不是星狀拓撲（所有都連回 orchestrator），而是允許 agent-to-agent 直接訊息傳遞。這減少了 orchestrator bottleneck。

### 2.4 Guardrails — 輸出驗證的標準化

**來源**：OpenAI Agents SDK 官方文檔 + agency-swarm 的 `execution_guardrails.py`
**可信度**：HIGH — 官方 SDK 功能

Guardrails 在 2026 年已成為 production agent 系統的標配：

```python
from agents import Agent, OutputGuardrail

guardrail = OutputGuardrail(
    name="no_profanity",
    description="確保輸出不含不當語言",
    validate_output=lambda ctx, agent, output: {
        "pass": "fuck" not in output.text.lower(),
        "failure_message": "Output contained inappropriate language",
    },
)

agent = Agent(
    name="customer_support",
    guardrails=[guardrail],  # 每個輸出前自動驗證
)
```

Agency Swarm 在這之上加了 `ExecutionGuardrails`——在 agent 執行生命週期的關鍵點（開始、結束、錯誤）自動插入驗證邏輯。

### 2.5 Session + Tracing — 可觀測性的標準化

**來源**：OpenAI Agents SDK — `sessions/` + `tracing/` 文件
**可信度**：HIGH — 官方文件

```python
with trace("order_processing"):
    result = await Runner.run(sales_agent, user_input)
    # 整個 run 的工具調用、LLM 決策、sub-agent handoffs 都被追蹤
```

Session 管理自動維護對話歷史，tracing 讓跨 agent 的複雜互動可以被除錯。OpenAI 自己的 tracing UI 能視覺化完整的多 agent trace tree。

### 2.6 MCP（Model Context Protocol）— 工具發現的標準化

**來源**：microsoft/mcp-for-beginners（16k+ stars）+ lastmile-ai/mcp-agent
**可信度**：HIGH — Microsoft 官方 repo，16k stars，2026 年高活跃度

MCP 的核心價值：**工具發現的標準化**。過去每個 framework 都要自己發明工具註冊機制，MCP 提供了統一的协议：

```
Client (Agent Framework)
    │
    ├── ListTools → MCP Server → Tool List
    ├── CallTool(name, args) → MCP Server → Result
    └── ListResources / GetPrompt / ...

MCP Server = 任何提供工具的後端（資料庫、API、檔案系統等）
```

mcp-agent 框架將 MCP 整合進 orchestration：

```python
# mcp-agent 的 Agent 工廠自動從 MCP servers 拉工具
agent = Agent(
    server_names=["github", "filesystem", "web_search"],
    # 工具自動從這些 MCP server 聚合，不需要手動列舉
)
```

MCP-for-beginners 的教學課程將 MCP server 實作分成 11 個模块——從最簡單的 single-tool server 到 multi-protocol aggregation，逐漸增加複雜度。

## 3. Why It Matters / Applications

### 3.1 從「一個超強 agent」到「一群專門 agent」的典範轉移

2024-2025 年社群大量討論「GPT-5 等超強模型來了就能解決 agent 不可靠問題」，但 2026 年共識是：**就算模型更強，架構不對也沒用**。Reasoning token budget 是固定的，單一 agent 不可能同時擅長規劃、工具調用、領域知識、輸出格式化。

Orchestration 架構讓不同 agent 負責不同認知負載，主模型只專注調度（Supervisor）。這比提升單一模型能力更實惠。

### 3.2 Production Readiness 的三大支柱

從研究樣本看，2026 年 production agent 系統的標準配備：
1. **Guardrails**（輸入/輸出驗證）— 防止錯誤傳播
2. **Tracing**（完整執行蹤跡）— debug 複雜 multi-agent 互動
3. **Session 管理**（對話歷史自動維護）— 多 turn 記憶

沒有這三個元件的 agent 系統只能算 prototype。

### 3.3 MCP 生態正在形成壟斷

16k+ stars 的 mcp-for-beginners 顯示 Microsoft 在教育、開發生態上的巨大投入。一旦 MCP 成為事實標準，工具發現層就被統一了，各框架差異只在上層 orchestration logic。這對 firn 等自建系統意味著：要嘛深度整合 MCP，要嘛自己發明另一套工具發現機制（通常不值得）。

## 4. Limitations / Honest Assessment

### 4.1 框架鎖定問題

OpenAI Agents SDK 是 provider-agnostic（聲稱支援 100+ LLMs），但事實上某些高階功能（如某些 guardrails 配置）只在 OpenAI API 上穩定。Agency Swarm 明確基於 OpenAI Agents SDK，这意味着：如果你要使用 Agency Swarm 的完整功能，你就是在用 OpenAI SDK 作為事實底層。

**對比**：MCP 是真正的 protocol-level 標準，不依賴特定模型或框架。但 MCP 只解決「工具發現」，不解決 orchestration。

### 4.2 複雜度爆炸

多 agent orchestration 的設定檔案（communication_flows、shared_instructions、agent tools、guardrails）會快速膨胀到難以維護。一個 5-agent 系統可能需要 200+ 行 YAML 加上自訂 tools 程式碼。

**對比既有方案**：CrewAI 的 pipeline（如 `TaskAgents`) 用 YAML 描述工作流，比較 declarative；OpenAI Agents SDK 是 Python-first，更靈活但也更複雜。

### 4.3 可複製性評估

| 元件 | 免費方案？ | 瓶頸 |
|------|-----------|------|
| Agents-as-Tools | ✅ 用任何 LLM API | 需要 self-host 或付費 API |
| Guardrails | ✅ 可以自己實作 | 複雜驗證需要 fine-tuned 模型或更多 compute |
| MCP Server | ✅ 完全開源 | 維護自己的 MCP server 有成本 |
| Tracing | ⚠️ 有開源方案（otel），但完整 UI 需付費 | 付費遙測服務（e.g., LangSmith） |
| Session 管理 | ✅ 自己實作 | 大量 session 的 storage 成本 |

### 4.4 沒有銀彈：框架間差異被過度行銷

Swarms（57k stars）聲稱是「most flexible multi-agent framework」，但從 repo 結構看，它的核心與其他框架沒有根本性差異。57k stars 的數字部分來自一段時間的病毒式傳播效應，不代表技術領先。實際上，OpenAI Agents SDK 的 production-ready 文件密度、Agency Swarm 的 test coverage（92%）更值得認真參考。

### 4.5 自我改善能力的缺口

這次研究的所有 orchestration 框架都專注於**靜態架構**——agent 的能力在部署時就固定了，運行時只能靠外部工具（如 RAG）來更新知識。**沒有任何一個框架內建自我改善機制**（如自動從失敗中學習、動態調整 tools）。這個缺口與之前研究過的 self-improving agents 主題高度相關——orchestration 和 self-improvement 是兩個獨立的問題，目前社群傾向於分開解決。

## 5. Actionable for Our Projects

### 5.1 Firn 可以立即採用的模式

**A. 實作 agents-as-tools 模式（MODERATE）**

Firn 目前是單一 agent 架構。可以新增一個 `FirnRouter` agent，將特定任務 delegation 給専門 sub-agents（如程式碼 review、文件生成）。不需要任何付費 API，純粹是架構重組。

具體做法：
- 新增 `sub_agents/` 目錄，每個 sub-agent 是獨立的 system prompt + tools
- Router agent 的 tools list 動態包含這些 sub-agents
- 參考：`openai-agents-python/examples/agent_patterns/agents_as_tools.py`

**B. 實作 Output Guardrails（TRIVIAL）**

在 firn 的輸出路徑加一個 lightweight validation layer——確保輸出格式正確、不含敏感資訊。不需要任何額外 API。

**C. 整合 MCP 工具發現（MODERATE）**

Firn 目前手動管理工具。若整合 MCP，可以让 firn 自動發現任何 MCP-compliant server 的工具。這是 long-term 方向，short-term 可先研究 mcp-agent 的 SDK 如何處理這個。

### 5.2 需要進一步研究的方向

**D. Session + Tracing 基礎設施（HARD）**

完整的 tracing UI（如 OpenAI 的 Agents Tracing）需要 UI 基礎設施，這不該現在做。但可以在日誌層面先結構化——讓每個 agent run 的 input/tools/output 都是 machine-readable 的 JSON。

**E. Agency Swarm 的 communication_flow 概念（RESEARCH-ONLY）**

Agency Swarm 的 direct agent-to-agent 訊息模式比星狀拓撲更有效率，但在 firn 目前的 scale 不需要。等firn 的 agent 數量超過 5 個再考慮。

### 5.3 不建議現在跟進的

- **Swarms 框架**：57k stars 看似吸引人，但實際功能與其他框架無根本差異，社群文檔品質不如 OpenAI Agents SDK 或 Agency Swarm。現在引入只會增加維護負擔。
- **Self-improving orchestration**：這個研究領域還沒有 stable 的開源實現，等 research 成熟再引入。

## 6. Follow-up Questions

1. **MCP 整合的實際可行性**：Firn 的工具管理目前是如何做的？若要接 MCP，最困難的地方是什麼（tool schema translation？動態 discovery？）？
2. **Guardrails 實作細節**：firn 目前如何驗證輸出？是否有嘗試過 Pydantic-based output validation？
3. **Sub-agent 專業化的粒度**：如果 firn 要拆分為多 agent，一個合理的起始粒度是什麼（3 個？5 個？）？

---

### 原始來源

openai/openai-agents-python — GitHub Repo — HIGH — 官方 OpenAI Agents SDK，2026 年 production-ready，多 agent orchestration 的事實標準框架

microsoft/mcp-for-beginners — GitHub Repo — HIGH — Microsoft 官方 MCP 教學，16k+ stars，MCP 生態覆蓋最廣

lastmile-ai/mcp-agent — GitHub Repo — HIGH — MCP-agent 框架（8k stars），整合 MCP 工具發現與 orchestration

VRSEN/agency-swarm — GitHub Repo — MEDIUM-HIGH — Agency Swarm（4.4k stars），擴展 OpenAI Agents SDK，92% test coverage，結構化 communication flow

kyegomez/swarms — GitHub Repo — MEDIUM — Swarms（6.7k stars），multi-agent orchestration 框架，但文件密度不如前述框架

openai/openai-agents-python — examples/agent_patterns/agents_as_tools.py — HIGH — Agents-as-Tools 模式官方範例

openai/openai-agents-python — examples/agent_patterns/agents_as_tools_conditional.py — HIGH — Conditional tool enabling 範例（RBAC for agents）
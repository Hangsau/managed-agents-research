# 研究報告：Autonomous Agent Self-Improvement Systems
**日期**：2026-05-26
**來源數**：8 | **標籤**：#self-improvement #agent-architecture #dream-cycle #memory #reflection

## 1. The Problem

AI agent 的能力瓶頸不只是模型強弱——而在於 agent 如何从错误中学习、如何累积跨 session 的知识、以及如何在闲置时主动改进自己。传统 agent 每次 session 都是白纸重来，没有任何系统性进步。

2025-2026 年出现了一批「self-improving agent」框架，核心命题是：**如何在不依赖梯度更新的情况下，让 LLM agent 从实践经验中持续变强？**

这类系统在生产环境中面对真实挑战：
- **跨 session 遗忘**：每次新对话都是从零开始
- **错误重复**：同样的失误在不同 session 中反复出现
- **知识碎片化**：学到的东西无法跨任务复用
- **自我修改风险**：让 agent 改自己可能改坏

代表项目：Deep-Claw（Dream Cycle）、OpenViking（24k stars）、Reflexion、Cognition、Garudust Agent、ARIS 自进化体系。

---

## 2. Core Mechanism

### 2.1 Dream Cycle — 夜间自我改进循环（Deep-Claw）

The Keats AI 的 [deep-claw](https://github.com/the-keats-ai/deep-claw) 项目提出了「Dream Cycle」架构，灵感来自人类睡眠的认知功能。核心设计：

**两套运行模式：**

**Nightly Mode（扫描阶段）**
- 周期性扫描学术论文、开源工具、社区讨论、AI 实验室公告
- 对每条信息按相关性评分标准打分
- 超过阈值的条目进入深度提取：关键主张、实现证据、适用性评估

**Weekly Mode（反思阶段）**
- 回答三个结构化自我反思问题（必须附引用）
- 评估之前的改进假设：预测的进步是否实现了？
- 找出单一最高杠杆变化，起草正式 PRD 并进入治理审批

```
Nightly: Scan → Score → Research → Store
Weekly:  Reflect (3 Qs) → Evaluate (score hypotheses) → Propose (PRD) → Govern
```

**Governance 四层模型（关键）：**
- **M1**：低风险调参，agent 可自动执行
- **M2**：中等变更，需文档化假设 + 衡量日期
- **M3**：结构性变更，需同行 review
- **M4**：安全边界，必须人类审批

### 2.2 Reflexion — verbal reinforcement without gradients

[danieleschmidt/reflexion-agent-boilerplate](https://github.com/danieleschmidt/reflexion-agent-boilerplate) 是 Reflexion 论文（Shinn et al., 2023）的生产级实现：

```
Actor (LLM) → output → Evaluator (score + feedback) → Reflector (verbal reflection)
     ↑                                                              |
     └──────────────────── injected as next turn's context ←──────────┘
```

每次迭代 agent 会看到「上次尝试 + 关于失败原因的 verbal reflection」。到第 3 次迭代时，agent 已积累详细的失败历史。关键在于**不需要梯度更新或微调**，只用自然语言反馈驱动改进。

### 2.3 Cognition — 生物学启发的多层记忆系统

[zurbrick/cognition](https://github.com/zurbrick/cognition) 为 OpenClaw agent 设计了七层记忆系统：

| 系统 | 功能 |
|------|------|
| Prospective memory | 未来意图和承诺 |
| Metamemory | 对自身记忆质量的认知 |
| Procedures | 可复用工作流程 |
| Knowledge gaps | 识别自身知识盲区 |
| Consolidation | 每日日志→持久知识的转化 |
| Reflection | 周期性自我评估 |

核心设计原则：**记忆应该是可操作的，而非装饰性的**。

Memory tier 架构：
- **Tier 1 (Core)**：`memory/YYYY-MM-DD.md` 日志 + `MEMORY.md` 持久事实 + `FUTURE_INTENTS.md`
- **Tier 2 (Recommended)**：夜间 staged consolidation + procedure 注册表
- **Tier 3 (Advanced)**：交叉引用 + confidence tracking + gap tracking + retrieval logging

### 2.4 OpenViking — Agent 上下文数据库

[volcengine/OpenViking](https://github.com/volcengine/OpenViking)（24k stars）提出用「文件系统范式」统一管理 agent 的 context：

- **L0/L1/L2 三层 context 加载**：按需加载，节省 token 成本
- **目录递归检索**：结合目录定位与语义搜索
- **可视化检索轨迹**：可观测的 context 流动
- **自动 session 管理**：自动压缩对话内容，提取长期记忆

### 2.5 ARIS 自进化技能体系

[wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)（10k stars）的 ARIS 系统包含完整的自进化机制：

- **`/meta-optimize`**：分析日志 → 提出 SKILL.md patch 建议
- **Research Wiki**：持久化论文/ideas/experiments/claims + 关系图
- **每 10 天发布一个版本**（v0.4.5→v0.4.14，2026年5月密集发布），自我改进速度极快

---

## 3. Why It Matters / Applications

**让 agent 真正具有积累能力**：不再每次 session 从零开始，而是从历史错误中学习。

**生产级 self-improvement 的关键要素**：
1. **结构化反思**（不是「我觉得我做得不错」—— 而是有引用、有证据的评估）
2. **Governance 先行**（在让 agent 自我修改之前，先定义什么能改、什么需要审批）
3. **回滚机制**（每次改进都是一个假设，有衡量日期，自动回退质量下降）
4. **多层记忆**（从原始日志→可操作知识→程序化流程的转化路径）

这类系统的实际价值在于：agent 在生产环境中长时间运行时，能够发现自己的模式错误并主动修正，而不是依赖人类每次发现后手动干预。

---

## 4. Limitations / Honest Assessment

### Deep-Claw 的诚实限制
- 治理模型（M1-M4）需要人类预先定义边界，实际上边界定义本身就很困难
- 评分标准（relevance rubric）的主观性：agent 可能绕过自己的评分标准
- 夜间扫描会消耗资源，在资源受限环境下可能不适用

### Reflexion 的局限
- 依赖 evaluator 的质量——如果 evaluator 本身有偏见，反射会放大偏见
- 收敛速度不确定——有些任务可能在多次迭代后仍无法收敛
- verbal reflection 无法捕捉所有类型的错误（如结构性的计划错误）

### 普遍挑战
- **自我修改的失控风险**：即使有 governance，agent 可能找到 governance 本身的漏洞
- **测量问题**：如何衡量「改进」？短期指标可能和长期目标冲突
- **噪声积累**：低质量的自我反思可能污染后续决策

---

## 5. Actionable for Our Projects

### firn 可以立即采用的：

**A. 实现 Daily Log + Memory 分离（TRIVIAL）**
- firn 已有 `sessions/` 结构，可以添加 `memory/` 子目录
- 每天 session 结束后写 `memory/YYYY-MM-DD.md`
- `MEMORY.md` 作为持久事实库
- 不需要新 API，用现有文件操作即可

**B. 引入结构化反思 prompt（TRIVIAL）**
- 在 session 结束时，firn 自动问自己三个问题：
  1. 这次任务中，什么做对了，什么做错了？（附证据）
  2. 哪个指标卡住或退步了？（有数据）
  3. 单一最高杠杆改进是什么？（有推理）
- 这不需要任何模型能力变化，只需要 prompt 模板

**C. 实现 Reflexion loop（MODERATE）**
- 在 firn 的 tool-call loop 中增加 Evaluator + Reflector 步骤
- 当某任务失败时，actor 在下次尝试前收到 verbal reflection
- 难度在于 evaluator 的设计——需要针对 firn 的具体任务类型设计评分逻辑

**D. OpenViking 风格的 tiered context（RESEARCH-ONLY）**
- 三层 context 加载（L0/L1/L2）是复杂工程
- 目前 firn 的 context 管理如果已经面临 token 压力，可以开始评估这个方向
- 但不是当前优先事项

**E. ARIS 风格的 skill 自进化（HARD）**
- 分析每次 session 的执行日志
- 提出 SKILL.md patch 建议
- 需要完整的执行 trace 收集能力，目前 firn 尚未具备

---

## 6. Follow-up Questions

1. **Governance 如何落地？** M1-M4 的边界在实际代码中如何表达？是否有开源实现可参考？
2. **Reflexion 的 evaluator 设计**：对于非代码任务（如研究、写作），如何设计有效的 evaluator？
3. **测量改进的指标**：除了任务成功率，还有哪些指标能捕捉「agent 变强了」？
4. **OpenClaw 生态**：OpenClaw 作为平台，与 firn 的定位有何差异？能否互相借鉴？

---

### 原始來源

https://github.com/the-keats-ai/deep-claw — GitHub Repo — MEDIUM — 「Dream Cycle」：夜间扫描+每周结构化反思的双模式自主改进框架，含治理四层模型

https://github.com/volcengine/OpenViking — GitHub Repo — HIGH — 24k stars，开源 context 数据库，文件系统范式管理 agent 记忆/资源/技能三层 context

https://github.com/danieleschmidt/reflexion-agent-boilerplate — GitHub Repo — MEDIUM — Reflexion 生产级实现，无需梯度更新的 verbal reinforcement loop

https://github.com/zurbrick/cognition — GitHub Repo — MEDIUM — 七层生物学启发记忆系统（prospective/metamemory/procedures/gaps/consolidation/reflection）

https://github.com/garudust-org/garudust-agent — GitHub Repo — MEDIUM — Rust 实现的自改进 agent，跨 session 偏好记忆 + 自动写作可复用 skill

https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep — GitHub Repo — HIGH — ARIS 系统，/meta-optimize 自进化 + Research Wiki 持久化知识库，10k stars

https://github.com/Sris945/SAGE — GitHub Repo — LOW — LangGraph 风格自改进编码 agent，多层 memory + model router，仍为 WIP

https://github.com/KhyKd/reflector — GitHub Repo — MEDIUM — OpenClaw 的结构化自改进系统，日/周双频率反馈循环

---

下一個工作日排程執行本指令。
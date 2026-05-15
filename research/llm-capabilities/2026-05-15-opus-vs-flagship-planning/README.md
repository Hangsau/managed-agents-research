# Opus 規劃能力研究

**日期**：2026-05-15
**研究問題**：為什麼 Claude Opus 4.7 的規劃能力贏過 Sonnet 4.6 / DeepSeek V4 Pro / MiniMax M2.7 / Kimi K2.6 / GPT-5.5 Codex？
**研究方法**：4 phase 迭代研究 + Haiku 事實核對 + Sonnet 同行評審

## 主要結論

「Opus 規劃強」**有條件成立**：
- **plan-heavy 場景**（Aider Polyglot / SWE-Bench Pro）：Opus 領先 5.7-15.2 pt，**證據強**
- **agentic loop**（Terminal-Bench）：GPT-5.5 反超 Opus 13 pt
- **D4/D5 規格 quality**：公開 benchmark 完全沒量化，H1（真實能力差距）與 H1-alt（selection effect）並陳

詳見 [`OPUS_PLANNING_ADVANTAGE.md`](./OPUS_PLANNING_ADVANTAGE.md)。

## 檔案結構

```
2026-05-15-opus-vs-flagship-planning/
├── README.md                          (本檔)
├── OPUS_PLANNING_ADVANTAGE.md         (最終整合報告)
└── study/
    ├── 00_framework.md                (Phase 1: 7 維度定義 + 模型版本)
    ├── 01_benchmarks.md               (Phase 2: 公開 benchmark 矩陣)
    ├── 02_mechanism.md                (Phase 3: 訓練機制分析)
    └── 03_field_evidence.md           (Phase 4: 實戰證據)
```

每份 Phase 文件含修訂歷史（v1 → v2），顯示 Haiku/Sonnet 評審後的修正軌跡。

## 研究方法論

每 Phase 結束後派發：
- **Haiku 4.5** 核對所有事實聲明（模型版本、benchmark 數字、技術細節）
- **Sonnet 4.6** 做同行評審（論證邏輯、競爭假設、結構嚴謹度）

評審意見直接整合進 v2，不隱藏初稿錯誤。

## 已知局限

- 自建 micro-eval（補 D4/D5 缺口）設計已寫但未執行
- 用戶 claudehome memory 缺跨家族規劃對照（無 GPT-5.5 規劃 vs Opus 規劃 counterfactual）
- 模型快速迭代，結論可能 1-3 個月內過時

## 給用戶的具體建議

最簡單的 disambiguation 實驗（成本 ≈ 一個工作天）：取一個 plan-check，分別交 Opus / GPT-5.5 / Kimi K2.6 規劃，三份規格各發包 Kimi 執行，比較執行 quality。

詳細實驗設計見 [`OPUS_PLANNING_ADVANTAGE.md` §6](./OPUS_PLANNING_ADVANTAGE.md)。

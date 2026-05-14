# OBS-001 長期追蹤計畫

問題：怎麼知道 observational memory 在變好，不是變肥？

## 一、追蹤維度（四指標）

### 1. 累積健康度
| 指標 | 算法 | 警訊 |
|---|---|---|
| facts/day | 近 7 天新增數 ÷ 7 | < 1 → distiller 沒在做事 |
| 去重率 | rejected / (rejected + added) | > 0.7 → 沒新東西可學 |
| category 失衡 | max_cat / total | > 0.6 → 只學一類，偏食 |
| high-conf 佔比 | high / total | < 0.5 → distiller 太保守 |

### 2. 事實品質（spot-check）
每週隨機抽 5 則，人工/LLM 評「這則事實有用嗎？」
- ✅ actionable：下次 agent 會用到的
- ⚠️ trivia：對但用不上
- ❌ wrong/hallucinated：錯的

目標：✅ ≥ 80%

### 3. 注入穿透率
- briefing.py 每次跑完 → 確認 facts 段落存在
- 模擬：agent session 啟動時，briefing 內容是否能正確引用
- 可以透過 grep consolidation_briefing.md 檢查 `## Observational Facts` 存在

### 4. 實際引用的閉環證據（終極指標）
最難但最有意義的指標：agent 是否在 session 中引用了 fact store 的內容？
- 搜 session transcript 中「根據 briefing」「事實庫顯示」「之前學到」等關鍵字
- 或用 session_search 每隔一陣子確認

---

## 二、實作：track_memory_growth.py

一個 script，定期 dump 四卡片到 `~/.hermes/knowledge/memory_report.md`：
```bash
python3 ~/.hermes/scripts/track_memory_growth.py
```

產出：
```markdown
# Memory Health Report — 2026-05-14 16:00

## Accumulation
- Total facts: 23
- 7d avg: 3.3/day
- Dedup rate: 22%
- Category balance: pitfall=38% tech=35% env=18% pref=9%

## Injection
- Last briefing: 2026-05-14 15:46
- Observational section: ✅ present (5 facts)
- Total chars: 982 / 1000

## Drift (7d change)
- pitfall ↑ +4
- technical ↑ +2
- preference ↓ (0 new)
```

---

## 三、追蹤節奏

| 頻率 | 什麼事 | 誰做 |
|---|---|---|
| 每次 briefing | 確認 facts 段存在 | `briefing.py` 自己寫入 |
| 每日 | 生成 memory_report.md | cron `memory-tracker` |
| 每週 | 品質 spot-check（5 則隨機） | 新的 cron 或手動觸發 |
| 每月 | review 去重率 / 分類失衡 / 實際引用 | 手動 |

---

## 四、警訊觸發規則

| 條件 | 含義 | 行動 |
|---|---|---|
| facts/day < 0.5 連續 3 天 | distiller 卡住或沒內容 | 檢查 distiller cron 狀態 |
| dedup rate > 0.8 | 沒有新知識進來了 | review sessions 是否重複 |
| high-conf < 40% | distiller 不敢下結論 | 檢查 prompt 是否太嚴格 |
| 連續 2 天無 briefing update | briefing-updater 壞了 | 重跑 cron |
| spot-check ❌ 超過 30% | hallucination 問題 | audit distiller prompt |

---

## 五、實作優先序

1. `track_memory_growth.py` — 輕量，只讀 stats 不跑 LLM（即刻可做）
2. cron `memory-tracker` — 每日凌晨跑一次，deliver=local（5 分鐘）
3. spot-check 腳本 — 抽樣 + 簡單 heuristic 評分（下週）
4. 引用檢測 — grep session logs（月底，等 facts 累積夠）

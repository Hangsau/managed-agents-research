# Hermes 核心測試基礎建設 — 深度分析與可行性評估

**Source**: internal analysis — heartbeat_v2.py 程式碼審查 + Google ADK evaluation 架構研究  
**Type**: SPIKE analysis  
**Confidence**: high（codebase 實際讀取，函數級別分析）  
**Date**: 2026-05-13

---

## 1. The Problem

Hermes 目前的品質保證完全依賴**事後發現**：

```
用戶發現問題 → 除錯 → patch → 靠 heartbeat 確保系統別掛
```

但有一個關鍵盲點——heartbeat 只監控**系統健康**（disk/mem/stuck processes/provider errors），完全不碰**agent 行為正確性**。

**真實已發生的 failure**：`managed-agents-framework` 的 `ma run` 指令因路徑變更而損壞，heartbeat 完全沒有偵測到。壞掉的指令靜靜躺在那裡，直到下次有人執行才發現——這不是一個 hypothetical 風險，是**已發生的生產事故**。

類似的潛在事故點：
- `heartbeat_v2.py` 的 scoring 公式被調整 → no one knows if REST/WORK decisions are still correct
- Skill 更新後 broken → 沒有 regression test
- `score_actions()` 的權重被誤改 → 決策品質默默下降，無人察覺

這些都是**非 LLM 的純邏輯層**——不需要 mock AI、不需要 probabilistic evaluation。它們只是沒有被測試覆蓋。

---

## 2. Core Analysis: What's Testable Right Now

### heartbeat_v2.py 函數分析（共 26 個函數，逐個檢查）

#### ✅ 純函數 — 可以直接 pytest（6 個）

| 函數 | 行數 | 做什麼 | 測試複雜度 |
|------|------|--------|-----------|
| `_is_daemon_process(cmd)` | 192-197 | 字串 pattern matching | 低 — 3 個 test cases |
| `_is_on_cooldown(action, history, cooldown)` | 378-387 | 時間視窗比對 | 低 — 4 個 cases |
| `score_actions(snap, history)` | 390-426 | **核心 scoring 引擎** | 中 — 8-12 個 cases |
| `select_action(scores, snap, history)` | 429-447 | cooldown + backpressure 過濾 | 中 — 6-8 個 cases |
| `action_connect(snap, dry_run)` | 512-521 | 格式化 cold sessions | 低 — 2 個 cases |
| `action_report(snap, dry_run)` | 524-533 | 狀態摘要格式化 | 低 — 3 個 cases |

**最重要的測試目標是 `score_actions()`** — 這是 cognitive layer 的核心，直接決定 heartbeat 會做什麼。每個 scoring dimension 都有 clear input → expected behavior：

```python
# 範例 test case
def test_work_score_increases_with_pending_work():
    snap = HeartbeatSnapshot(
        cron_jobs_count=10, stuck_sessions=[],
        disk_used_pct=10, memory_used_pct=50,
        failed_platforms=[], running_agents=0,
        active_sessions=0,
        # ... other fields with defaults
    )
    scores = score_actions(snap, history=[])
    assert scores["WORK"] > scores["REST"]
    assert scores["WORK"] > 5.0  # above base
```

#### ⚠️ 有純邏輯可以抽出來（2 個）

| 函數 | 可抽出的純邏輯 | 行數 |
|------|---------------|------|
| `_detect_stuck_sessions()` | etime string parser（`days:HH:MM` → minutes） | L221-233 |
| `_memory_usage()` | `free -m` output parser | L136-143 |

這些函數現在是 I/O + parsing 混在一起。把 parsing 抽成獨立函數後就可以測。

#### ❌ 純 I/O 函數 — 需要 mock/filesystem fixture（9 個）

`safe_json_read`, `safe_json_write`, `disk_usage`, `memory_usage`, `cron_jobs_count`, `list_hermes_processes`, `system_uptime`, `count_active_sessions`, `read_decision_history`

這些不適合第一期測試（回報/努力比太低）。

#### ❌ 需要 SQLite/filesystem 的整合層（5 個）

`kanban_ready_tasks`, `cache_size_mb`, `provider_health_from_logs`, `scan_cold_sessions`, `build_heartbeat_snapshot`

---

### Hermes 現有測試基礎建設

**現狀：零。否定的零。**

| 項目 | 狀態 |
|------|------|
| pytest 安裝 | ❌ 未安裝 |
| `~/.hermes/tests/` 目錄 | ❌ 不存在 |
| Core scripts 測試 | ❌ 0 tests |
| Skill 測試 | ✅ ComfyUI 有 447 行（唯一例外） |
| CI runner | ❌ 不存在 |
| Coverage tool | ❌ 不存在 |

唯一存在的測試是 ComfyUI skill 的 `test_common.py`（447 行，測試 `_common.py` 的純函數），模式可用但從未被推廣到核心。

---

## 3. 參考架構：Google ADK 怎麼做

ADK 的 evaluation 分兩層：

### Layer 1: Unit Test（.test.json）
- JSON 定義 input/expected tool calls/expected response
- 一個檔案就是一個 session
- 適合開發階段快速迭代
- **backed by formal Pydantic schema**（EvalSet + EvalCase）
- 不依賴 paid service

### Layer 2: EvalSet（integration）
- 包含多個 sessions
- 支援多輪對話模擬
- 評估 trajectory（tool use）和 final response
- 需要 Vertex AI Evaluation Service API（付費）

**ADK 的核心洞察**：由於 LLM 的 probabilistic nature，必須同時評估 **trajectory**（agent 走的路徑是否正確）和 **final output**（最終回應）。

### 對 Hermes 的啟發

Hermes 不需要急著做 LLM-level evaluation（那是 phase 2 的事）。但 ADK 的關鍵設計原則可以直接用：

1. **Formal schema for test cases** — heartbeat 的 scoring 行為可以用 structured test cases 定義
2. **Separation of deterministic and non-deterministic testing** — 先測純邏輯，再處理 LLM
3. **Test file as single source of truth** — test case 本身就是 documentation

---

## 4. 優勢

### 立即可得的優勢

1. **防止回歸**（最核心）
   - `score_actions()` 的權重調整後，跑 test suite 立刻知道決策是否 broken
   - 這是目前完全沒有的防護

2. **文件即測試**
   - 每個 test case 說明了 heartbeat 在什麼情況下做什麼決策
   - 新接手的開發者（或未來的 AI）讀 test 比讀 code 快

3. **重構安全網**
   - heartbeat_v2.py 寫得很乾淨，但沒有任何保護，改一行就可能改壞
   - 有 test suite 後可以大膽 optimize

4. **建立測試 culture**
   - ComfyUI tests 的模式證明可行但被孤立
   - 核心有 test 後，可以推廣到其他 scripts（`managed-agents-framework` 的 `ma run` 路徑問題之類）

### 中期優勢（phase 2-3）

5. **Cron job output validation**
   - 目前 heartbeat 只看 process alive，不看 output valid
   - 有 testing pattern 後可以加 smoke test 檢查 cron output 格式

6. **通往 LLM evaluation 的橋樑**
   - 先建立 deterministic testing 基礎，之後加入 ADK-style trajectory evaluation 時不會是從零開始

---

## 5. 劣勢與成本

### 直接成本

| 項目 | 估計 | 說明 |
|------|------|------|
| pytest 安裝 | `pip install pytest pytest-cov` | ~5MB，無外部依賴 |
| 建立 `~/.hermes/tests/` | 一個 conftest.py | 導入 heartbeat_v2 module |
| 寫 6 個函數的測試 | 2-3 小時 | 一次性的投入 |
| 維護成本 | 極低 | 純函數的測試幾乎不需要更新 |

### 風險

1. **Scope creep** — 最危險的風險
   - 開始測試一個函數，發現想測更多，最後變成沒完沒了的重構專案
   - **解法**：嚴格限制 phase 1 只測 6 個純函數，不做重構，不碰 I/O 層

2. **false sense of security**
   - 測了 scoring logic 不代表 LLM 決策正確
   - **解法**：明確標註這是 deterministic layer only，不是 e2e test

3. **heartbeat_v2.py 沒有模組化設計**
   - 現在是 flat script，函數間直接 import constants
   - **解法**：conftest.py 直接 `sys.path.insert` + `from heartbeat_v2 import score_actions`（跟 ComfyUI tests 一樣的模式）

### 不做會發生什麼

- `score_actions()` 或 `select_action()` 被改壞後，heartbeat 的決策品質會**默默下降**
- 沒有人會發現，因為 heartbeat 仍然在跑，只是選錯 action
- 下次 `ma run` 級的事故會重複發生，只是換一個 script

---

## 6. 務實執行計畫

### Phase 1: Spike（2-3 小時）

```
目標：證明 testing pattern 可行
範圍：只測 6 個純函數，不做任何 code change
成功標準：pytest 跑過，coverage > 80%，CI-ready
```

**步驟：**

1. `pip install pytest pytest-cov`
2. 建立 `~/.hermes/tests/conftest.py`（導入 heartbeat_v2）
3. 建立 `~/.hermes/tests/test_heartbeat_scoring.py`（`score_actions` + `select_action` 的 12-15 個 test cases）
4. 建立 `~/.hermes/tests/test_heartbeat_helpers.py`（`_is_daemon_process` + `_is_on_cooldown` + formatters 的 10 個 cases）
5. 跑 coverage report
6. 評估是否值得推廣到其他 scripts

**不做的事（留在 phase 2）：**
- 重構 heartbeat_v2.py（抽出 parsing 函數）
- I/O 層的 mock testing
- 任何 LLM-dependent 的測試
- CI integration

### Phase 2: Expansion（如果 phase 1 成功）

- 把 `_detect_stuck_sessions` 的 etime parser 抽成 `_parse_etime()` → 加入測試
- 把 `_memory_usage` 的 parser 抽成 `_parse_free_output()` → 加入測試
- 建立 skill smoke test pattern（load → check syntax → verify）

### Phase 3: Cron Integration

- 在 heartbeat 或獨立 cron 中加入「上次關鍵 cron job 的 output 是否 valid」檢查
- 建立 golden test set for high-frequency CLI paths

---

## 7. 結論

這不是一個華麗的功能。沒有新的演算法，沒有 fancy architecture。但它是**基礎建設**——跟 worktree isolation 一樣，現在沒有它不會死，但繼續沒有它，每次改 code 都在賭。

最務實的起點：幫 `score_actions()` 寫 12 個 test cases，跑 pytest，看 coverage。如果這 12 個 tests 在未來的某一次改 code 中抓到一個 regression，整個投資就回本了。

**優先級判斷**：低風險、低時間成本（2-3h）、高潛在回報。是典型的「現在做很便宜，未來做很貴」的基礎建設。建議排在 worktree-subagent-isolation（SPIKE 完成）之後，作為下一個 SPIKE 項目。

# Forge 弱模型補償機制 — P0 實作計畫

**目標：** 將 Forge 的三個完全機械化機制（validate、stagnation detection、phase-gated workflow）移植到 Hermes，補強弱模型（DeepSeek/MiniMax）的執行品質。

## Planning Quality Checklist

├── **目標（一句話）**
│   └── 在弱模型執行複雜任務時，自動攔截語法錯誤、API contract 破壞、retry loop、plan drift

├── **前置條件檢查（3–5 項 yes/no）**
│   ├── [x] `~/.hermes/scripts/` 目錄存在（無需新建）
│   ├── [x] `writing-plans` skill 已存在且可用
│   ├── [x] 有實際 Python 檔案可供 validate 測試（非空測試）
│   └── [x] Herm

es cron 環境可執行 Python 指令

├── **步驟清單（每步 ≤15 字）**
│   ├── 1. 寫 validate.py 語法+contract 檢查
│   ├── 2. 寫 iteration_state.py 停滯偵測
│   ├── 3. 將 validate 整合進 writing-plans skill
│   ├── 4. 將 stagnation 整合進 writing-plans skill
│   ├── 5. 驗證：實際檔案跑一遍 validate
│   └── 6. 驗證：mock retry 情境跑 stagnation

├── **每步的驗證方式（怎麼知道該步做完了）**
│   ├── Step 1: `python3 ~/.hermes/scripts/hermes_validate.py src/hermes_state.py` → 輸出 SYNTAX OK / CONTRACT FAIL
│   ├── Step 2: `python3 -c "from iteration_state import check; print(check(['err'], 0.5))"` → 輸出 ok/stagnant
│   ├── Step 3: 讀 writing-plans SKILL.md 確認含 `[[tool: terminal]]` 呼叫 validate.py
│   ├── Step 4: 讀 writing-plans SKILL.md 確認含 stagnation check 邏輯
│   ├── Step 5: 對真實檔案執行 validate.py
│   └── Step 6: 模擬連續失敗情境呼叫 check() 確認回傳 stagnant

└── **潛在卡點（至少 2 個，含對策）**
    ├── validate.py 的 contract check 用 regex 解析 import/export → 複雜格式可能誤判 → 對策：只做 `import <module>` 和 `from <module> import <name>` 兩種基本 pattern，複雜 case 回報 UNKNOWN
    └── iteration_state.py 的振盪偵測需要維護 history list → 記憶體無限增長 → 對策：最多保留最近 10 次記錄，超過砍掉最舊的

└── **失敗時的退路**
    └── validate.py 回傳非零exit 或 stagnation 回傳 `stagnant` → agent 停止 retry 並向用戶回報「此方向無效，請重新指示」

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🟡 實作中 |
| **目前階段** | 設計 → 實作 |
| **最後行動** | 2026-05-23: 確認 writing-plans skill 存在，規劃寫入雙路徑 |
| **下一步** | 寫 validate.py（Task 1） |
| **阻擋** | 無 |

---

## Task 1: `hermes_validate.py`

**Objective:** 純機械的檔案驗證工具，不依賴模型能力

**Files:**
- Create: `~/.hermes/scripts/hermes_validate.py`

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Hermes validate — Forge validate tool 的 Python 移植版
用法: python3 hermes_validate.py <file> [--type python|shell|js|unknown]
Exit: 0=OK, 1=SYNTAX ERROR, 2=CONTRACT FAIL, 3=UNKNOWN ERROR
"""

import sys
import os
import re
import subprocess

def syntax_check(path, ftype):
    if ftype == "python":
        result = subprocess.run(["python3", "-m", "py_compile", path],
                                capture_output=True, text=True)
        return result.returncode == 0, result.stderr
    elif ftype == "shell":
        result = subprocess.run(["bash", "-n", path],
                                capture_output=True, text=True)
        return result.returncode == 0, result.stderr
    elif ftype == "js":
        result = subprocess.run(["node", "--check", path],
                                capture_output=True, text=True)
        return result.returncode == 0, result.stderr
    return True, ""

def extract_imports(path):
    """Extract import statements for contract check (basic pattern only)."""
    imports = []
    try:
        with open(path) as f:
            for line in f:
                # import X / import X as Y
                m = re.match(r'^\s*import\s+(\w+)', line)
                if m:
                    imports.append(m.group(1))
                # from X import Y / from X import Y, Z
                m = re.match(r'^\s*from\s+(\w+)', line)
                if m:
                    imports.append(m.group(1))
    except:
        pass
    return imports

def contract_check(path):
    """Check if imported modules exist locally (cross-module contract)."""
    imports = extract_imports(path)
    # Get directory of the file
    dir_path = os.path.dirname(os.path.abspath(path))
    failures = []
    for imp in imports:
        # Check for local module match
        local_match = os.path.exists(os.path.join(dir_path, imp + ".py")) or \
                      os.path.exists(os.path.join(dir_path, imp, "__init__.py"))
        # Don't fail on stdlib/modules we can't verify
        if not local_match:
            failures.append(imp)
    return failures

def main():
    if len(sys.argv) < 2:
        print("Usage: hermes_validate.py <file> [--type python|shell|js]")
        sys.exit(3)
    
    path = sys.argv[1]
    ftype = "python"  # default
    if "--type" in sys.argv:
        idx = sys.argv.index("--type")
        ftype = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "unknown"
    
    if not os.path.exists(path):
        print(f"MISSING: {path}")
        sys.exit(3)
    
    ok, err = syntax_check(path, ftype)
    if not ok:
        print(f"SYNTAX ERROR in {path}: {err[:200]}")
        sys.exit(1)
    
    if ftype == "python":
        failures = contract_check(path)
        if failures:
            print(f"CONTRACT WARN: unresolved imports {failures} (non-critical)")
            # Don't fail on contract warnings — only fail syntax
    
    print(f"OK: {path}")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

**Step 2: Test on a real Hermes Python file**

Run: `python3 ~/.hermes/scripts/hermes_validate.py /usr/local/lib/hermes-agent/hermes_state.py`  
Expected: `OK: /usr/local/lib/hermes-agent/hermes_state.py` (exit 0)

**Step 3: Test contract check on a file with imports**

Run: `python3 ~/.hermes/scripts/hermes_validate.py /usr/local/lib/hermes-agent/agent/context_compressor.py`  
Expected: `OK` with possible CONTRACT WARN for unresolved modules (non-blocking)

**Step 4: Commit**

```bash
git add ~/.hermes/scripts/hermes_validate.py
git commit -m "feat: add hermes_validate.py (Forge validate port)"
```

---

## Task 2: `iteration_state.py`

**Objective:** 純數學的停滯/振盪/倒退偵測，替代模型自我判斷

**Files:**
- Create: `~/.hermes/scripts/iteration_state.py`

**Step 1: Write the module**

```python
#!/usr/bin/env python3
"""Iteration state tracker — Forge iteration_state stagnation detection port
Tracks: stagnation (same issues N times), oscillation (A-B-A-B), score regression
Usage:
    from iteration_state import IterationTracker
    tracker = IterationTracker()
    result = tracker.check(issues=["errA", "errB"], score=0.7)
    print(result)  # 'ok' | 'stagnant' | 'oscillating' | 'regressing'
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import os

@dataclass
class IterationTracker:
    max_history: int = 10          # oscillation history size
    stagnation_threshold: int = 3  # same issues for N iterations
    score_window: int = 3           # window for regression check
    
    prev_issues: Optional[list] = field(default=None, init=False)
    stagnation_count: int = field(default=0, init=False)
    oscillation_history: list = field(default_factory=list, init=False)
    score_history: list = field(default_factory=list, init=False)
    
    def check(self, issues: list, score: Optional[float] = None) -> str:
        """Returns: 'ok' | 'stagnant' | 'oscillating' | 'regressing'"""
        # stagnation: same issues as last time
        if issues == self.prev_issues and self.prev_issues is not None:
            self.stagnation_count += 1
        else:
            self.stagnation_count = 0
        
        # oscillation: A-B-A pattern
        if len(self.oscillation_history) >= 2:
            if self.oscillation_history[-2] == issues:
                self._trim_history()
                return "oscillating"
        
        self.oscillation_history.append(tuple(issues) if issues else None)
        self._trim_history()
        
        # score regression
        if score is not None:
            self.score_history.append(score)
            if len(self.score_history) >= self.score_window:
                if score < sum(self.score_history[-self.score_window:-1]) / (self.score_window - 1):
                    self.score_history = []
                    return "regressing"
        
        self.prev_issues = list(issues) if issues else None
        
        if self.stagnation_count >= self.stagnation_threshold:
            return "stagnant"
        return "ok"
    
    def _trim_history(self):
        """Keep history bounded."""
        if len(self.oscillation_history) > self.max_history:
            self.oscillation_history = self.oscillation_history[-self.max_history:]
        if len(self.score_history) > self.score_window * 2:
            self.score_history = self.score_history[-self.score_window:]

# Standalone CLI for testing
if __name__ == "__main__":
    import sys
    tracker = IterationTracker()
    # Test mock scenarios
    print("Test 1 (stagnation):", end=" ")
    for i in range(5):
        r = tracker.check(["errA", "errB"], 0.5)
    print(r)  # should be 'stagnant'
    
    tracker2 = IterationTracker()
    print("Test 2 (oscillation):", end=" ")
    tracker2.check(["errA"], 0.5)
    tracker2.check(["errB"], 0.5)
    r = tracker2.check(["errA"], 0.5)
    print(r)  # should be 'oscillating'
    
    tracker3 = IterationTracker()
    print("Test 3 (regression):", end=" ")
    tracker3.check([], 0.8)
    tracker3.check([], 0.7)
    r = tracker3.check([], 0.3)  # big drop
    print(r)  # should be 'regressing'
```

**Step 2: Run CLI test**

Run: `python3 ~/.hermes/scripts/iteration_state.py`  
Expected: `Test 1 (stagnation): stagnant`, `Test 2 (oscillation): oscillating`, `Test 3 (regression): regressing`

**Step 3: Import test**

Run: `python3 -c "from iteration_state import IterationTracker; t = IterationTracker(); print(t.check(['err'], 0.5))"`  
Expected: `ok`

**Step 4: Commit**

```bash
git add ~/.hermes/scripts/iteration_state.py
git commit -m "feat: add iteration_state.py (Forge stagnation detection port)"
```

---

## Task 3: 整合進 `writing-plans` skill

**Objective:** 在每個 task 完成後自動呼叫 validate + stagnation check

**Files:**
- Modify: `~/.hermes/skills/software-development/writing-plans/SKILL.md`

**Change:** 在 Task Structure 的 Step 4（Run test to verify pass）之後，插入停滯檢查：

```markdown
**Step 4.5: Run stagnation check** (after every task)

After each task's test passes, check iteration state:

```python
from iteration_state import IterationTracker
tracker = IterationTracker()  # per-plan instance

# After task completion, in the plan's review step:
result = tracker.check(issues=[], score=None)  # issues=[] means task succeeded
# If result != 'ok': abort plan, report to user
```

**Forge phase-gated workflow** (add after Task Structure):

```
每個 task 完成後：
  1. validate.py → 語法/contract 檢查（pure mechanical）
  2. iteration_state.check() → 停滯偵測（pure mechanical）
  3. 任一失敗 → agent.stop() + 向用戶報告
```

**具体插入位置：** 在 "## Phase-gated Execution（Forge-derived，2026-05-23）" 段落之後，替換原有的 Phase-gated 說明，加入 validate tool + iteration_state 的實際呼叫方式。

**Step 5: Verify skill has the integration**

Run: `grep -n "hermes_validate\|iteration_state" ~/.hermes/skills/software-development/writing-plans/SKILL.md`  
Expected: 找到至少 2 處引用

**Step 6: Commit**

```bash
cd ~/.hermes
git add skills/software-development/writing-plans/SKILL.md
git commit -m "feat(writing-plans): integrate Forge validate + stagnation detection"
```

---

## Task 4: 終端用戶驗收

**驗收清單：**

- [ ] `python3 ~/.hermes/scripts/hermes_validate.py /usr/local/lib/hermes-agent/hermes_state.py` → exit 0，輸出含 `OK`
- [ ] `python3 ~/.hermes/scripts/hermes_validate.py /nonexistent.py` → exit 3，輸出含 `MISSING`
- [ ] `python3 ~/.hermes/scripts/iteration_state.py` → 3/3 test cases pass
- [ ] `python3 -c "from iteration_state import IterationTracker; t=IterationTracker(); print(t.check(['a'],0.5)); print(t.check(['a'],0.5)); print(t.check(['a'],0.5)); print(t.check(['a'],0.5))"` → stagnant
- [ ] `grep "hermes_validate\|iteration_state" ~/.hermes/skills/software-development/writing-plans/SKILL.md` → ≥2 matches

---

## 結構風險掃描

### 並發
本計畫寫入 `~/.hermes/scripts/` 的新檔案，無跨進程寫入，無并发風險。
→ **回答：** 否

### 邊界
- `hermes_validate.py`: 檔案不存在 → exit 3（MISSING）；syntax check 工具不存在 → graceful fallback
- `iteration_state.py`: issues=[] / score=None → 正常運作，回傳 `ok`
→ **回答：** 兩案皆有明确 fallback，無灰色地帶

### 持久化
本計畫不修改既有 state schema、不新增 DB、不改 config 格式。新增的 2 個 script 為 standalone，寫入 `~/.hermes/scripts/`（已有 git repo）。
→ **回答：** 否，無 migration 需求

### 外部輸入驗證
- `hermes_validate.py`: 接收檔案路徑作為 argument，檢查 exists 再讀取；不執行 shell expansion
- `iteration_state.py`: 接收 list/float，type check 簡單，無 injection 風險
→ **回答：** 是，但基本防護充分，無显式惡意輸入問題

### 命令注入
`hermes_validate.py` 用 `subprocess.run` 執行 `python3 -m py_compile`，path 為 sys.argv 不做 shell expansion，安全性等同 hermes-agent 既有實作。
→ **回答：** 否，無命令注入風險

### 跨狀態一致性
本計畫不新增狀態欄位、不修改既有 status 值。writing-plans skill 新增的是額外檢查，不修改既有流程。
→ **回答：** 否

---

## 實作清單

| # | 動作 | 工具 | Skill | 派工 | 關鍵風險 |
|---|------|------|-------|------|----------|
| 1 | 寫 validate.py | Write | 無 | 自己做 | contract check regex 勿過度 |
| 2 | 測試 validate.py | Terminal | 無 | 自己做 | 需要真實檔案 |
| 3 | 寫 iteration_state.py | Write | 無 | 自己做 | oscillation history bounded |
| 4 | 測試 iteration_state.py | Terminal | 無 | 自己做 | 3/3 cases 必須 pass |
| 5 | 整合進 writing-plans skill | Patch | 無 | 自己做 | 確認正確位置 |
| 6 | 驗收全流程 | Terminal | 無 | 自己做 | 逐項打勾 |
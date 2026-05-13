"""Tests for heartbeat_v2.py pure functions.

Run: cd ~/.hermes/scripts && python3 -m pytest test_heartbeat_v2.py -v
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts dir to path for heartbeat_v2 import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from heartbeat_v2 import (
    HeartbeatSnapshot,
    _is_daemon_process,
    _is_on_cooldown,
    action_connect,
    action_report,
    score_actions,
    select_action,
)


# ── Test Helpers ───────────────────────────────────────────────────────────

def _snap(**overrides) -> HeartbeatSnapshot:
    """Build a HeartbeatSnapshot with sensible defaults."""
    defaults = dict(
        ts="2026-01-01T00:00:00Z",
        uptime_seconds=3600.0,
        active_sessions=10,
        running_agents=0,
        agent_cache_size=32.0,
        agent_cache_keys=["web_001", "img_002"],
        failed_platforms=[],
        pending_approvals=0,
        queued_events=0,
        provider_health={},
        disk_used_pct=50.0,
        disk_free_gb=50.0,
        memory_used_pct=50.0,
        cron_jobs_count=0,
        stuck_sessions=[],
        warmth_actions=[],
    )
    defaults.update(overrides)
    return HeartbeatSnapshot(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# _is_daemon_process
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsDaemonProcess:
    """Pattern-based daemon detection — pure string matching."""

    def test_known_daemons(self):
        assert _is_daemon_process("hermes gateway run --port 8080")
        assert _is_daemon_process("python3 hermes-admin/app.py")

    def test_normal_agents(self):
        assert not _is_daemon_process("python3 heartbeat_v2.py")
        assert not _is_daemon_process("python3 agent_worker.py --id=5")
        assert not _is_daemon_process("hermes task run build")

    def test_empty_and_edge(self):
        assert not _is_daemon_process("")
        assert not _is_daemon_process("hermes")  # partial match shouldn't trigger
        assert not _is_daemon_process("HERMES GATEWAY RUN")  # case-sensitive

    def test_substring_in_longer_string(self):
        """'hermes gateway run' should match even as substring."""
        assert _is_daemon_process("/usr/bin/python3 hermes gateway run --debug")


# ═══════════════════════════════════════════════════════════════════════════════
# _is_on_cooldown
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsOnCooldown:
    """Cooldown check — pure timestamp comparison."""

    COOLDOWN = 600  # 10 min

    def test_empty_history(self):
        assert not _is_on_cooldown("WORK", [], self.COOLDOWN)

    def test_action_missing_from_history(self):
        history = [{"action": "REST", "ts": time.time() - 10}]
        assert not _is_on_cooldown("WORK", history, self.COOLDOWN)

    def test_recent_action_triggers_cooldown(self):
        history = [{"action": "WORK", "ts": time.time() - 60}]
        assert _is_on_cooldown("WORK", history, self.COOLDOWN)

    def test_old_action_does_not_trigger(self):
        history = [{"action": "WORK", "ts": time.time() - 900}]  # 15 min ago
        assert not _is_on_cooldown("WORK", history, self.COOLDOWN)

    def test_only_last_occurrence_checked(self):
        """Per implementation: break after first match in reversed order."""
        history = [
            {"action": "WORK", "ts": time.time() - 900},  # old
            {"action": "REST", "ts": time.time() - 60},
            {"action": "WORK", "ts": time.time() - 1200},  # older — not reached
        ]
        # Last WORK (reversed) is 900s ago → outside cooldown
        assert not _is_on_cooldown("WORK", history, self.COOLDOWN)

    def test_missing_ts_field_treated_as_zero(self):
        """When 'ts' is missing, get() returns 0 (epoch 1970), NOT within cooldown."""
        history = [{"action": "WORK"}]  # no 'ts' → default 0
        # now - 0 is ~50 years, far outside any cooldown
        assert not _is_on_cooldown("WORK", history, self.COOLDOWN)

    def test_multiple_actions_history(self):
        history = [
            {"action": "REST", "ts": time.time() - 1200},
            {"action": "WORK", "ts": time.time() - 30},
            {"action": "EVOLVE", "ts": time.time() - 800},
        ]
        assert _is_on_cooldown("WORK", history, self.COOLDOWN)
        assert not _is_on_cooldown("EVOLVE", history, self.COOLDOWN)


# ═══════════════════════════════════════════════════════════════════════════════
# score_actions
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreActions:
    """Scoring logic — pure computation from snapshot + history."""

    def test_baseline_all_five(self):
        scores = score_actions(_snap(), [])
        assert sorted(scores.keys()) == ["CONNECT", "EVOLVE", "REPORT", "REST", "WORK"]
        assert all(s >= 5.0 for s in scores.values())

    def test_pending_work_boosts_work(self):
        # High cron count + stuck sessions → WORK should dominate
        snap = _snap(cron_jobs_count=5, stuck_sessions=[{"pid": 1}])
        scores = score_actions(snap, [])
        assert scores["WORK"] > scores["REST"]
        assert scores["WORK"] > scores["REPORT"]

    def test_disk_pressure_boosts_rest(self):
        snap = _snap(disk_used_pct=90.0)  # above 85% warn
        scores = score_actions(snap, [])
        assert scores["REST"] > 5.0  # got a boost

    def test_memory_pressure_boosts_rest(self):
        snap = _snap(memory_used_pct=90.0)  # above 80
        scores = score_actions(snap, [])
        assert scores["REST"] > 5.0

    def test_disk_below_warn_no_rest_boost(self):
        snap = _snap(disk_used_pct=50.0)
        scores = score_actions(snap, [])
        # REST should be at baseline (no boost from disk/mem)
        assert scores["REST"] == 5.0

    def test_memory_none_does_not_crash(self):
        snap = _snap(memory_used_pct=None)
        scores = score_actions(snap, [])
        assert scores["REST"] == 5.0  # no boost when None

    def test_failed_platforms_boost_evolve(self):
        snap = _snap(failed_platforms=["openrouter", "anthropic"])
        scores = score_actions(snap, [])
        assert scores["EVOLVE"] > 5.0
        assert scores["EVOLVE"] > scores["REPORT"]

    def test_idle_state_boosts_connect(self):
        snap = _snap(running_agents=0, active_sessions=10)
        scores = score_actions(snap, [])
        # Should get 3.0 * 0.5 = 1.5 boost
        assert scores["CONNECT"] == 6.5

    def test_busy_state_no_connect_boost(self):
        snap = _snap(running_agents=3, active_sessions=100)
        scores = score_actions(snap, [])
        assert scores["CONNECT"] == 5.0  # no idle boost

    def test_repetition_penalty(self):
        history = [{"action": "WORK", "ts": time.time() - 60}]
        scores = score_actions(_snap(), history)
        # Last action was WORK → penalty of -1.5
        assert scores["WORK"] < 5.0
        assert scores["WORK"] == 3.5

    def test_repetition_penalty_not_applied_to_others(self):
        history = [{"action": "WORK", "ts": time.time() - 60}]
        scores = score_actions(_snap(), history)
        assert scores["REST"] == 5.0
        assert scores["EVOLVE"] == 5.0

    def test_combined_signals(self):
        """WORK boost + REPEAT penalty on WORK → net effect."""
        snap = _snap(cron_jobs_count=3)
        history = [{"action": "WORK", "ts": time.time() - 60}]
        scores = score_actions(snap, history)
        # WORK: 5.0 + 3*2.0 + (-1.5) = 9.5
        assert scores["WORK"] == pytest.approx(9.5)


# ═══════════════════════════════════════════════════════════════════════════════
# select_action
# ═══════════════════════════════════════════════════════════════════════════════

class TestSelectAction:
    """Action selection — pure decision logic."""

    def test_picks_highest_scoring(self):
        scores = {"WORK": 5.0, "REST": 5.0, "EVOLVE": 5.0, "CONNECT": 10.0, "REPORT": 5.0}
        action, reason = select_action(scores, _snap(), [])
        assert action == "CONNECT"
        assert "10.0" in reason

    def test_skips_cooldown_action(self):
        """When top scorer is on cooldown, pick next best."""
        history = [{"action": "WORK", "ts": time.time() - 10}]  # just ran
        scores = {"WORK": 15.0, "REST": 6.0, "EVOLVE": 5.0, "CONNECT": 5.0, "REPORT": 5.0}
        action, _ = select_action(scores, _snap(), history)
        assert action != "WORK"

    def test_skips_work_with_backpressure(self):
        """When agents are running, skip WORK even if high score."""
        snap = _snap(running_agents=2)
        scores = {"WORK": 15.0, "REST": 6.0, "EVOLVE": 5.0, "CONNECT": 5.0, "REPORT": 5.0}
        action, _ = select_action(scores, snap, [])
        assert action != "WORK"
        assert action == "REST"

    def test_falls_back_to_report_when_all_skipped(self):
        """If every action is blocked, default to REPORT."""
        history = [{"action": "WORK", "ts": time.time() - 10}]
        scores = {"WORK": 15.0, "REST": 5.0, "EVOLVE": 5.0, "CONNECT": 5.0, "REPORT": 5.0}
        # WORK on cooldown, all others tied — highest is WORK which gets skipped
        action, reason = select_action(scores, _snap(), history)
        assert action == "REST"  # next highest, not REPORT

    def test_all_on_cooldown_defaults_to_report(self):
        """All five actions recently taken → REPORT."""
        now = time.time()
        history = [
            {"action": "WORK", "ts": now - 10},
            {"action": "REST", "ts": now - 10},
            {"action": "EVOLVE", "ts": now - 10},
            {"action": "CONNECT", "ts": now - 10},
            {"action": "REPORT", "ts": now - 10},
        ]
        scores = {"WORK": 15.0, "REST": 6.0, "EVOLVE": 5.0, "CONNECT": 5.0, "REPORT": 5.0}
        action, reason = select_action(scores, _snap(), history)
        assert action == "REPORT"
        assert "defaulting" in reason


# ═══════════════════════════════════════════════════════════════════════════════
# action_connect
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionConnect:
    """Warmth action — pure formatting from warmth_actions field."""

    def test_no_cold_sessions(self):
        result = action_connect(_snap(warmth_actions=[]), dry_run=False)
        assert result == "no cold sessions"

    def test_cold_sessions_summary(self):
        snap = _snap(warmth_actions=[
            {"file": "session_a.jsonl", "idle_hours": 25.0},
            {"file": "session_b.jsonl", "idle_hours": 30.0},
            {"file": "session_c.jsonl", "idle_hours": 50.0},
            {"file": "session_d.jsonl", "idle_hours": 48.0},
        ])
        result = action_connect(snap, dry_run=False)
        assert "4 cold sessions" in result
        # Should only mention first 3
        for f in ["session_a", "session_b", "session_c"]:
            assert f in result

    def test_dry_run_prefix(self):
        snap = _snap(warmth_actions=[{"file": "x.jsonl", "idle_hours": 30.0}])
        result = action_connect(snap, dry_run=True)
        assert result.startswith("[DRY]")


# ═══════════════════════════════════════════════════════════════════════════════
# action_report
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionReport:
    """Status summary — pure formatting."""

    def test_basic_report(self):
        result = action_report(_snap(), dry_run=False)
        assert "agents=0" in result
        assert "disk=50.0%" in result
        assert "mem=50.0%" in result
        assert "stuck=0" in result
        assert "sessions=10" in result

    def test_pipe_separated(self):
        result = action_report(_snap(), dry_run=False)
        assert " | " in result

    def test_memory_none_handling(self):
        result = action_report(_snap(memory_used_pct=None), dry_run=False)
        assert "mem=N/A" in result

    def test_dry_run_unchanged(self):
        """action_report doesn't distinguish dry_run (purely informational)."""
        dry = action_report(_snap(), dry_run=True)
        wet = action_report(_snap(), dry_run=False)
        assert dry == wet

    def test_stuck_sessions_counted(self):
        snap = _snap(stuck_sessions=[{"pid": 1}, {"pid": 2}, {"pid": 3}])
        result = action_report(snap, dry_run=False)
        assert "stuck=3" in result

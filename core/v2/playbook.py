"""Playbook system: predefined workflows that reduce planning burden.

A Playbook is a JSON file (*.playbook) containing:
  - name: human-readable name
  - vars: default variables (can be overridden at runtime)
  - steps: ordered list of actions to execute

Variable substitution uses {{var_name}} syntax.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure imports resolve when running standalone
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core.v2 import action_executor, db

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@dataclass
class Step:
    """A single step in a Playbook."""
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    name: str = ""
    condition: str | None = None
    timeout: int = 60  # seconds
    label: str = ""      # jump target identifier
    goto: str | None = None  # jump to label after execution


@dataclass
class Playbook:
    """A loaded Playbook with metadata and steps."""
    name: str
    description: str = ""
    vars: dict[str, Any] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    output_schema: dict[str, Any] | None = None  # JSON schema for result validation

    def with_vars(self, overrides: dict[str, Any]) -> Playbook:
        """Return a new Playbook with vars merged."""
        return Playbook(
            name=self.name,
            description=self.description,
            vars={**self.vars, **overrides},
            steps=list(self.steps),
        )


def _interpolate(value: Any, ctx: dict[str, Any]) -> Any:
    """Recursively substitute {{var}} in strings, lists, and dicts."""
    if isinstance(value, str):
        def _replacer(m: re.Match) -> str:
            key = m.group(1)
            return str(ctx.get(key, m.group(0)))
        return _VAR_RE.sub(_replacer, value)
    if isinstance(value, list):
        return [_interpolate(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _interpolate(v, ctx) for k, v in value.items()}
    return value


def resolve_args(args: dict[str, Any], vars: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *args* with all {{variable}} placeholders substituted.

    Missing variables are left as the original placeholder.
    """
    return _interpolate(args, vars)


def _evaluate_condition(condition: str | None, ctx: dict[str, Any]) -> bool:
    """Return True if the step should run.

    - No condition → always run.
    - After interpolating, a truthy string runs; empty/falsy skips.
    """
    if condition is None:
        return True
    interpolated = _interpolate(condition, ctx)
    if isinstance(interpolated, str):
        return bool(interpolated.strip()) and interpolated.strip().lower() not in ("false", "null", "none", "0", "")
    return bool(interpolated)


def _validate_schema(data: Any, schema: dict, path: str = "") -> list[str]:
    """Minimal JSON schema validator (type, required, properties, items, enum)."""
    errors: list[str] = []
    expected_type = schema.get("type")

    if expected_type == "object":
        if not isinstance(data, dict):
            errors.append(f"{path}: expected object, got {type(data).__name__}")
        else:
            for key in schema.get("required", []):
                if key not in data:
                    errors.append(f"{path}: missing required field '{key}'")
            for key, prop_schema in schema.get("properties", {}).items():
                if key in data:
                    errors.extend(_validate_schema(data[key], prop_schema, f"{path}.{key}"))
    elif expected_type == "array":
        if not isinstance(data, list):
            errors.append(f"{path}: expected array, got {type(data).__name__}")
        else:
            item_schema = schema.get("items", {})
            for i, item in enumerate(data):
                errors.extend(_validate_schema(item, item_schema, f"{path}[{i}]"))
    elif expected_type == "string":
        if not isinstance(data, str):
            errors.append(f"{path}: expected string, got {type(data).__name__}")
    elif expected_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            errors.append(f"{path}: expected integer, got {type(data).__name__}")
    elif expected_type == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            errors.append(f"{path}: expected number, got {type(data).__name__}")
    elif expected_type == "boolean":
        if not isinstance(data, bool):
            errors.append(f"{path}: expected boolean, got {type(data).__name__}")

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']}, got {data!r}")

    return errors


def load_playbook(path_or_name: str) -> Playbook | None:
    """Parse a *.playbook JSON file and return a Playbook dataclass.

    Accepts either a full path or just the playbook name (e.g. 'research'
    resolves to '<project_root>/core/v2/playbooks/research.playbook').
    """
    # Try as full path first (must be a file)
    p = Path(path_or_name)
    if p.exists() and p.is_file():
        pass  # use as-is
    else:
        # Try built-in playbooks directory
        builtin_dir = Path(__file__).parent / "playbooks"
        p = builtin_dir / f"{path_or_name}.playbook"
        if not p.exists() or not p.is_file():
            return None

    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    raw_steps = data.get("steps", [])
    steps: list[Step] = []
    for rs in raw_steps:
        rs = dict(rs)
        action = rs.pop("action", "")
        name = rs.pop("name", "")
        condition = rs.pop("condition", None) if "condition" in rs else None
        timeout = rs.pop("timeout", 60)
        label = rs.pop("label", "")
        goto = rs.pop("goto", None)
        steps.append(
            Step(
                name=name,
                action=action,
                args=rs,
                condition=condition,
                timeout=timeout,
                label=label,
                goto=goto,
            )
        )

    return Playbook(
        name=data.get("name", p.stem),
        description=data.get("description", ""),
        vars=data.get("vars", {}),
        steps=steps,
        output_schema=data.get("output_schema"),
    )


def run_playbook(
    playbook: Playbook,
    session_id: str,
    llm_context: dict[str, Any] | None = None,
    stop_on_error: bool = True,
) -> list[dict]:
    """Execute every step of *playbook* via action_executor.run().

    Args:
        playbook: The Playbook to run.
        session_id: Session identifier for logging.
        llm_context: Runtime variables that override playbook.vars.
        stop_on_error: If True, abort on the first step that returns an error.

    Returns:
        A list of result dicts, one per step attempted.  Each dict contains:
        - step_name
        - action
        - skipped (bool)
        - result (the action output, or None if skipped)
        - error (bool)
    """
    ctx = {**playbook.vars, **(llm_context or {})}
    results: list[dict] = []

    # Build label → index map for goto resolution
    label_index = {step.label: i for i, step in enumerate(playbook.steps) if step.label}
    max_steps = len(playbook.steps) * 10  # safety limit to prevent infinite loops
    steps_executed = 0
    idx = 0

    while 0 <= idx < len(playbook.steps) and steps_executed < max_steps:
        steps_executed += 1
        step = playbook.steps[idx]
        step_name = step.name or f"step_{idx}"

        if not _evaluate_condition(step.condition, ctx):
            results.append(
                {
                    "step_name": step_name,
                    "action": step.action,
                    "skipped": True,
                    "result": None,
                    "error": False,
                }
            )
            idx += 1
            continue

        resolved_args = resolve_args(step.args, ctx)
        print(f"[{session_id}] Playbook step '{step_name}': {step.action} | Args: {list(resolved_args.keys())}")

        result = action_executor.run(step.action, resolved_args, session_id, timeout=step.timeout)

        # Merge result values back into context so later steps can reference them
        if isinstance(result, dict):
            ctx[f"{step_name}_result"] = result
            for k, v in result.items():
                ctx[f"{step_name}_{k}"] = v

        has_error = "error" in result
        results.append(
            {
                "step_name": step_name,
                "action": step.action,
                "skipped": False,
                "result": result,
                "error": has_error,
            }
        )

        db.log_event(
            session_id,
            "playbook_step",
            {
                "playbook": playbook.name,
                "step": step_name,
                "action": step.action,
                "args": resolved_args,
                "result": result,
                "skipped": False,
            },
        )

        if has_error and stop_on_error:
            print(f"[{session_id}] Playbook stopped due to error in step '{step_name}'")
            break

        # Dynamic jump: goto takes precedence over sequential flow
        if step.goto and step.goto in label_index:
            idx = label_index[step.goto]
            print(f"[{session_id}] Playbook goto '{step.goto}' (step {idx})")
        else:
            idx += 1

    # Validate against output schema if defined
    if playbook.output_schema:
        errors = _validate_schema(results, playbook.output_schema)
        if errors:
            print(f"[{session_id}] Playbook output validation failed:")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"[{session_id}] Playbook output validation passed")

    return results

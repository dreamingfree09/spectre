from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from spectre.execution_plan import build_execution_plan
from spectre.simulator_stub import simulate_execution_plan


def _load(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = argv or sys.argv[1:]
    if len(argv) != 3:
        print("Usage: python -m spectre.shadow_run <facts.json> <decision.json> <portfolio_state.json>")
        return 2

    facts_path, decision_path, state_path = argv
    facts = _load(facts_path)
    decision = _load(decision_path)
    state = _load(state_path)

    plan = build_execution_plan(facts, decision, facts_path, decision_path)
    report = simulate_execution_plan(plan, state, all_or_nothing=True)

    out = {
        "inputs": {
            "facts_path": facts_path,
            "decision_path": decision_path,
            "portfolio_state_path": state_path,
        },
        "execution_plan": plan,
        "simulation_report": report,
    }

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

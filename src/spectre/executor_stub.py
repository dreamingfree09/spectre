from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_execution_plan(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Execution plan not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def preview_execution_plan(plan: Dict[str, Any]) -> str:
    action = plan.get("plan", {}).get("action")
    orders = plan.get("plan", {}).get("orders", [])
    refusals = plan.get("refusals", [])

    lines: list[str] = []
    lines.append(f"Action: {action}")
    lines.append(f"Orders: {len(orders)}")

    for i, o in enumerate(orders, start=1):
        lines.append(
            f"  {i}. {o['side']} {o['symbol']} "
            f"notional={o['notional_quote']} "
            f"price={o.get('price_used')} "
            f"qty={o.get('quantity_base')}"
        )

    lines.append(f"Refusals: {len(refusals)}")
    for r in refusals:
        lines.append(f"  - {r.get('code')}: {r.get('message')}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("Usage: python -m spectre.executor_stub <execution_plan.json>")
        return 2

    plan = load_execution_plan(argv[0])
    print(preview_execution_plan(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

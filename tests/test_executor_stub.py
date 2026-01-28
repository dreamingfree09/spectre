from __future__ import annotations

import json
from pathlib import Path

from spectre.executor_stub import load_execution_plan, preview_execution_plan


def test_executor_preview_is_deterministic(tmp_path: Path):
    plan = {
        "plan": {
            "action": "no_action",
            "orders": [],
        },
        "refusals": [
            {"code": "NO_PRICE", "message": "No valid price for BTCUSDT"},
        ],
    }

    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan), encoding="utf-8")

    loaded = load_execution_plan(p)
    preview = preview_execution_plan(loaded)

    expected = (
        "Action: no_action\n"
        "Orders: 0\n"
        "Refusals: 1\n"
        "  - NO_PRICE: No valid price for BTCUSDT"
    )

    assert preview == expected

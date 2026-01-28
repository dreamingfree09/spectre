from __future__ import annotations

from spectre.simulator_stub import simulate_execution_plan


def test_simulator_all_or_nothing_aborts_on_insufficient_balance():
    plan = {
        "plan": {
            "action": "rebalance",
            "orders": [
                {"symbol": "BTCUSDT", "side": "BUY", "notional_quote": 60.0, "price_used": 90000.0},
                {"symbol": "ETHUSDT", "side": "BUY", "notional_quote": 60.0, "price_used": 3000.0},
            ],
        },
        "refusals": [],
    }

    state = {"balances": {"USDT": 100.0, "BTC": 0.0, "ETH": 0.0}}

    report = simulate_execution_plan(plan, state, all_or_nothing=True)

    assert report["action"] == "no_action"
    assert report["accepted_orders"] == []
    assert any(r["reason"] == "INSUFFICIENT_BALANCE" for r in report["rejected_orders"])
    assert any(r["reason"] == "ALL_OR_NOTHING_ABORT" for r in report["rejected_orders"])
    assert report["resulting_balances"]["USDT"] == 100.0

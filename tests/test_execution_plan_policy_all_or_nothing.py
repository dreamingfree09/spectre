from __future__ import annotations

import spectre.execution_plan as ep
from tests._helpers import FakeResponse, fake_ticker_payload, minimal_decision, minimal_facts


def test_any_refusal_forces_no_action(monkeypatch):
    # Prices are fine for both symbols.
    def fake_get(url, timeout=10):
        return FakeResponse(fake_ticker_payload({"BTCUSDT": 90000.0, "ETHUSDT": 3000.0}))

    # BTC has valid rules; ETH is intentionally missing rules -> refusal must occur.
    def fake_fetch_exchange_info(symbols):
        return {
            "BTCUSDT": {
                "step_size": 1e-5,
                "min_qty": 1e-5,
                "min_notional": 5.0,
                "base_asset": "BTC",
                "quote_asset": "USDT",
            }
        }

    monkeypatch.setattr(ep.requests, "get", fake_get)
    monkeypatch.setattr(ep, "fetch_exchange_info", fake_fetch_exchange_info)

    plan = ep.build_execution_plan(
        minimal_facts(),
        minimal_decision(),
        "facts.json",
        "decision.json",
    )

    # Policy: any refusal must cancel the entire rebalance.
    assert plan["plan"]["orders"] == []
    assert plan["plan"]["action"] == "no_action"
    assert any(r["code"] == "NO_EXCHANGE_RULES" for r in plan["refusals"])

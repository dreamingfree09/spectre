
from __future__ import annotations

import spectre.execution_plan as ep
from tests._helpers import FakeResponse, fake_ticker_payload, minimal_decision, minimal_facts


def test_unknown_strategy_mode_no_action(monkeypatch):
    def fake_get(url, timeout=10):
        return FakeResponse(fake_ticker_payload({"BTCUSDT": 90000.0, "ETHUSDT": 3000.0}))

    def fake_fetch_exchange_info(symbols):
        return {}

    monkeypatch.setattr(ep.requests, "get", fake_get)
    monkeypatch.setattr(ep, "fetch_exchange_info", fake_fetch_exchange_info)

    facts = minimal_facts()
    decision = minimal_decision(strategy_mode="weird_mode")
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    assert plan["plan"]["action"] == "no_action"
    assert any(r["code"] == "UNRECOGNIZED_STRATEGY_MODE" for r in plan["refusals"])


def test_pricing_http_failure_sets_prices_none(monkeypatch):
    def fake_get(url, timeout=10):
        raise RuntimeError("network down")

    def fake_fetch_exchange_info(symbols):
        # Provide valid rules so price is the only failure cause
        return {
            s: {
                "step_size": 1e-5,
                "min_qty": 1e-5,
                "min_notional": 5.0,
                "base_asset": s.replace("USDT", ""),
                "quote_asset": "USDT",
            }
            for s in symbols
        }

    monkeypatch.setattr(ep.requests, "get", fake_get)
    monkeypatch.setattr(ep, "fetch_exchange_info", fake_fetch_exchange_info)

    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    # With no prices, we must refuse orders.
    assert plan["plan"]["orders"] == []
    assert plan["plan"]["action"] == "no_action"
    assert any(r["code"] == "NO_PRICE" for r in plan["refusals"])

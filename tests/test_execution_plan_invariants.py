from __future__ import annotations

import spectre.execution_plan as ep
from tests._helpers import FakeResponse, fake_ticker_payload, minimal_decision, minimal_facts


def _patch_prices_ok(monkeypatch):
    def fake_get(url, timeout=10):
        return FakeResponse(fake_ticker_payload({"BTCUSDT": 90000.0, "ETHUSDT": 3000.0}))
    monkeypatch.setattr(ep.requests, "get", fake_get)


def _patch_rules_ok(monkeypatch):
    def fake_fetch_exchange_info(symbols):
        return {
            s: {
                "step_size": 1e-5 if s == "BTCUSDT" else 1e-4,
                "min_qty": 1e-5 if s == "BTCUSDT" else 1e-4,
                "min_notional": 5.0,
                "base_asset": s.replace("USDT", ""),
                "quote_asset": "USDT",
            }
            for s in symbols
        }
    monkeypatch.setattr(ep, "fetch_exchange_info", fake_fetch_exchange_info)


def test_action_matches_orders_nonempty(monkeypatch):
    _patch_prices_ok(monkeypatch)
    _patch_rules_ok(monkeypatch)

    plan = ep.build_execution_plan(minimal_facts(), minimal_decision(), "facts.json", "decision.json")

    orders = plan["plan"]["orders"]
    action = plan["plan"]["action"]

    assert (action == "rebalance") == bool(orders)

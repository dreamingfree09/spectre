
from __future__ import annotations

import os
from decimal import Decimal

import spectre.execution_plan as ep
from tests._helpers import (
    FakeResponse,
    fake_exchange_rules,
    fake_ticker_payload,
    minimal_decision,
    minimal_facts,
    load_schema,
    validate_jsonschema,
)


def _patch_prices(monkeypatch, prices):
    def fake_get(url, timeout=10):
        assert "ticker/price" in url
        return FakeResponse(fake_ticker_payload(prices))

    monkeypatch.setattr(ep.requests, "get", fake_get)


def _patch_exchange_rules(monkeypatch, rules):
    def fake_fetch_exchange_info(symbols):
        # return only the symbols requested
        out = {}
        for s in symbols:
            if s in rules:
                out[s] = rules[s]
        return out

    monkeypatch.setattr(ep, "fetch_exchange_info", fake_fetch_exchange_info)


def _std_rules():
    return fake_exchange_rules(
        {
            "BTCUSDT": {
                "step_size": 1e-5,
                "min_qty": 1e-5,
                "min_notional": 5.0,
                "base_asset": "BTC",
                "quote_asset": "USDT",
            },
            "ETHUSDT": {
                "step_size": 1e-4,
                "min_qty": 1e-4,
                "min_notional": 5.0,
                "base_asset": "ETH",
                "quote_asset": "USDT",
            },
        }
    )


def test_schema_valid_default(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_exchange_rules(monkeypatch, _std_rules())

    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    schema = load_schema("execution_plan.schema.json")
    validate_jsonschema(plan, schema)
    assert plan["schema_version"] == ep.SCHEMA_VERSION
    assert plan["venue"] == ep.VENUE
    assert plan["mode"] == ep.MODE
    assert plan["plan"]["action"] in ("rebalance", "no_action")


def test_do_nothing_forces_no_action(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_exchange_rules(monkeypatch, _std_rules())

    facts = minimal_facts()
    decision = minimal_decision(strategy_mode="do_nothing")
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    assert plan["plan"]["action"] == "no_action"
    assert plan["plan"]["orders"] == []
    assert any(r["code"] == "STRATEGY_DO_NOTHING" for r in plan["refusals"])


def test_zero_gross_exposure_forces_no_action(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_exchange_rules(monkeypatch, _std_rules())

    facts = minimal_facts()
    decision = minimal_decision(max_gross_exposure=0)
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    assert plan["plan"]["action"] == "no_action"
    assert plan["plan"]["orders"] == []
    assert any(r["code"] == "ZERO_GROSS_EXPOSURE" for r in plan["refusals"])


def test_empty_allowed_symbols_forces_no_action(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_exchange_rules(monkeypatch, _std_rules())

    facts = minimal_facts([])
    decision = minimal_decision(allowed_symbols=[])
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    assert plan["plan"]["action"] == "no_action"
    assert plan["plan"]["orders"] == []
    assert any(r["code"] == "NO_ALLOWED_SYMBOLS" for r in plan["refusals"])


def test_missing_price_refuses_order(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0})  # ETH missing
    _patch_exchange_rules(monkeypatch, _std_rules())

    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    # BTC should be fine; ETH should be refused due to missing price.
    codes = [r["code"] for r in plan["refusals"]]
    assert "NO_PRICE" in codes


def test_missing_exchange_rules_refuses_order(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    only_btc = _std_rules()
    only_btc.pop("ETHUSDT")
    _patch_exchange_rules(monkeypatch, only_btc)

    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    codes = [r["code"] for r in plan["refusals"]]
    assert "NO_EXCHANGE_RULES" in codes


def test_rounding_never_exceeds_raw_qty(monkeypatch):
    # Ensure step size rounding is ROUND_DOWN.
    _patch_prices(monkeypatch, {"BTCUSDT": 100.0, "ETHUSDT": 100.0})
    rules = fake_exchange_rules(
        {
            "BTCUSDT": {
                "step_size": 0.1,
                "min_qty": 0.1,
                "min_notional": 5.0,
                "base_asset": "BTC",
                "quote_asset": "USDT",
            },
            "ETHUSDT": {
                "step_size": 0.1,
                "min_qty": 0.1,
                "min_notional": 5.0,
                "base_asset": "ETH",
                "quote_asset": "USDT",
            },
        }
    )
    _patch_exchange_rules(monkeypatch, rules)

    # Budget 50 -> per order 25 -> raw_qty=0.25 -> rounded down to 0.2 with step 0.1
    monkeypatch.setenv("SPECTRE_BUDGET_QUOTE", "50")
    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    assert plan["plan"]["action"] == "rebalance"
    for o in plan["plan"]["orders"]:
        assert Decimal(str(o["quantity_base"])) in (Decimal("0.2"), Decimal("0.2"))


def test_min_qty_enforced(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    rules = _std_rules()
    rules["BTCUSDT"]["min_qty"] = 1.0  # impossible under $25 notional at these prices
    _patch_exchange_rules(monkeypatch, rules)

    monkeypatch.setenv("SPECTRE_BUDGET_QUOTE", "50")
    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    codes = [r["code"] for r in plan["refusals"]]
    assert "BELOW_MIN_QTY" in codes


def test_min_notional_enforced(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    rules = _std_rules()
    rules["BTCUSDT"]["min_notional"] = 30.0  # per-order notional is 25.0
    _patch_exchange_rules(monkeypatch, rules)

    monkeypatch.setenv("SPECTRE_BUDGET_QUOTE", "50")
    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    codes = [r["code"] for r in plan["refusals"]]
    assert "BELOW_MIN_NOTIONAL" in codes


def test_budget_override_invalid_emits_refusal_but_uses_default(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_exchange_rules(monkeypatch, _std_rules())

    monkeypatch.setenv("SPECTRE_BUDGET_QUOTE", "abc")
    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    assert any(r["code"] == "BAD_BUDGET_OVERRIDE" for r in plan["refusals"])
    # Default is 50.0 in output portfolio if override invalid.
    assert float(plan["portfolio"]["notional_budget_quote"]) == 50.0


def test_budget_override_small_forces_no_action_when_no_orders(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_exchange_rules(monkeypatch, _std_rules())

    monkeypatch.setenv("SPECTRE_BUDGET_QUOTE", "8")  # per order 4, below MIN_ORDER_NOTIONAL=5
    facts = minimal_facts()
    decision = minimal_decision()
    plan = ep.build_execution_plan(facts, decision, "facts.json", "decision.json")

    assert plan["plan"]["orders"] == []
    assert plan["plan"]["action"] == "no_action"
    assert all(r["code"] == "BELOW_MIN_NOTIONAL" for r in plan["refusals"])

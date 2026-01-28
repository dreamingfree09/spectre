from __future__ import annotations

from tests._helpers import FakeResponse, fake_ticker_payload, minimal_decision, minimal_facts
import spectre.execution_plan as ep


def _patch_prices(monkeypatch, prices: dict[str, float] | None):
    if prices is None:
        def fake_get(url, timeout=10):
            raise RuntimeError("pricing failure")
        monkeypatch.setattr(ep.requests, "get", fake_get)
        return

    def fake_get(url, timeout=10):
        return FakeResponse(fake_ticker_payload(prices))
    monkeypatch.setattr(ep.requests, "get", fake_get)


def _patch_rules(monkeypatch, rules: dict):
    def fake_fetch_exchange_info(symbols):
        # Return only what we were told to return; symbols not present simulate missing rules.
        return {s: rules[s] for s in symbols if s in rules}
    monkeypatch.setattr(ep, "fetch_exchange_info", fake_fetch_exchange_info)


def _std_rules():
    return {
        "BTCUSDT": {"step_size": 1e-5, "min_qty": 1e-5, "min_notional": 5.0, "base_asset": "BTC", "quote_asset": "USDT"},
        "ETHUSDT": {"step_size": 1e-4, "min_qty": 1e-4, "min_notional": 5.0, "base_asset": "ETH", "quote_asset": "USDT"},
    }


def _codes(plan) -> set[str]:
    return {r["code"] for r in plan.get("refusals", [])}


def test_invariant_no_orders_implies_no_action(monkeypatch):
    _patch_prices(monkeypatch, None)
    _patch_rules(monkeypatch, _std_rules())
    plan = ep.build_execution_plan(minimal_facts(), minimal_decision(), "facts.json", "decision.json")
    assert plan["plan"]["orders"] == []
    assert plan["plan"]["action"] == "no_action"


def test_bad_budget_override_records_refusal(monkeypatch):
    monkeypatch.setenv("SPECTRE_BUDGET_QUOTE", "abc")
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_rules(monkeypatch, _std_rules())
    plan = ep.build_execution_plan(minimal_facts(), minimal_decision(), "facts.json", "decision.json")
    assert "BAD_BUDGET_OVERRIDE" in _codes(plan)


def test_zero_gross_exposure_no_action(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_rules(monkeypatch, _std_rules())
    decision = minimal_decision(max_gross_exposure=0.0)
    plan = ep.build_execution_plan(minimal_facts(), decision, "facts.json", "decision.json")
    assert plan["plan"]["action"] == "no_action"
    assert "ZERO_GROSS_EXPOSURE" in _codes(plan)


def test_no_allowed_symbols_no_action(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0})
    _patch_rules(monkeypatch, _std_rules())
    decision = minimal_decision(allowed_symbols=[])
    plan = ep.build_execution_plan(minimal_facts([]), decision, "facts.json", "decision.json")
    assert plan["plan"]["action"] == "no_action"
    assert "NO_ALLOWED_SYMBOLS" in _codes(plan)


def test_below_min_notional_per_order_records_refusal(monkeypatch):
    # Force a tiny budget so per-order notional drops below MIN_ORDER_NOTIONAL (5.0).
    monkeypatch.setenv("SPECTRE_BUDGET_QUOTE", "1.0")
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    _patch_rules(monkeypatch, _std_rules())
    plan = ep.build_execution_plan(minimal_facts(), minimal_decision(), "facts.json", "decision.json")
    assert plan["plan"]["orders"] == []
    assert plan["plan"]["action"] == "no_action"
    assert "BELOW_MIN_NOTIONAL" in _codes(plan)


def test_missing_exchange_rules_records_refusal(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    # Provide rules for only one symbol; the other must produce NO_EXCHANGE_RULES.
    rules = _std_rules()
    rules.pop("ETHUSDT")
    _patch_rules(monkeypatch, rules)
    plan = ep.build_execution_plan(minimal_facts(), minimal_decision(), "facts.json", "decision.json")
    assert plan["plan"]["action"] == "no_action"  # orders should be empty due to missing rules
    assert "NO_EXCHANGE_RULES" in _codes(plan)


def test_bad_exchange_rules_records_refusal(monkeypatch):
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    rules = _std_rules()
    # Corrupt one required numeric field so Decimal conversion fails.
    rules["BTCUSDT"]["step_size"] = "not-a-number"
    _patch_rules(monkeypatch, rules)
    plan = ep.build_execution_plan(minimal_facts(), minimal_decision(), "facts.json", "decision.json")
    assert plan["plan"]["action"] == "no_action"
    assert "BAD_EXCHANGE_RULES" in _codes(plan)


def test_rounding_to_zero_records_refusal(monkeypatch):
    # Make step_size enormous so rounding drives qty to zero.
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0, "ETHUSDT": 3000.0})
    rules = _std_rules()
    rules["BTCUSDT"]["step_size"] = 1.0
    rules["BTCUSDT"]["min_qty"] = 0.000001
    rules["BTCUSDT"]["min_notional"] = 0.0
    _patch_rules(monkeypatch, rules)
    plan = ep.build_execution_plan(minimal_facts(["BTCUSDT"]), minimal_decision(allowed_symbols=["BTCUSDT"]), "facts.json", "decision.json")
    assert plan["plan"]["action"] == "no_action"
    assert "ROUNDING_TO_ZERO" in _codes(plan)


def test_below_min_qty_records_refusal(monkeypatch):
    # Make min_qty higher than the computed qty.
    _patch_prices(monkeypatch, {"BTCUSDT": 90000.0})
    rules = {
        "BTCUSDT": {"step_size": 1e-5, "min_qty": 1.0, "min_notional": 0.0, "base_asset": "BTC", "quote_asset": "USDT"},
    }
    _patch_rules(monkeypatch, rules)
    plan = ep.build_execution_plan(minimal_facts(["BTCUSDT"]), minimal_decision(allowed_symbols=["BTCUSDT"]), "facts.json", "decision.json")
    assert plan["plan"]["action"] == "no_action"
    assert "BELOW_MIN_QTY" in _codes(plan)

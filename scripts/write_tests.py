from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SCHEMAS = ROOT / "src" / "spectre" / "schemas"


def w(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    # pytest.ini: quiet output, ensure src imports work without installing package
    w(
        ROOT / "pytest.ini",
        textwrap.dedent(
            """\
            [pytest]
            addopts = -q
            pythonpath = src
            """
        ),
    )

    # Shared helpers
    w(
        TESTS / "_helpers.py",
        textwrap.dedent(
            """
            from __future__ import annotations

            import json
            from dataclasses import dataclass
            from pathlib import Path
            from typing import Any, Dict, List, Optional


            def minimal_facts(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
                syms = symbols or ["BTCUSDT", "ETHUSDT"]
                # Facts pack structure is not heavily used by Pass 4 right now,
                # but we keep it realistic to avoid regressions later.
                return {
                    "schema_version": "1.0",
                    "as_of_utc": "2026-01-01T00:00:00Z",
                    "venue": "binance",
                    "symbols": syms,
                    "candles": {s: [] for s in syms},
                }


            def minimal_decision(
                strategy_mode: str = "trend",
                allowed_symbols: Optional[List[str]] = None,
                max_gross_exposure: float = 1.0,
                risk_score: int = 40,
            ) -> Dict[str, Any]:
                syms = allowed_symbols if allowed_symbols is not None else ["BTCUSDT", "ETHUSDT"]
                return {
                    "schema_version": "1.0",
                    "as_of_utc": "2026-01-01T00:00:00Z",
                    "regime": "risk_on",
                    "risk_score": risk_score,
                    "strategy_mode": strategy_mode,
                    "allowed_symbols": syms,
                    "blocked_symbols": [],
                    "max_gross_exposure": max_gross_exposure,
                }


            @dataclass
            class FakeResponse:
                payload: Any
                status_code: int = 200

                def raise_for_status(self) -> None:
                    if self.status_code >= 400:
                        raise RuntimeError(f"HTTP {self.status_code}")

                def json(self) -> Any:
                    return self.payload


            def fake_ticker_payload(prices: Dict[str, float]) -> List[Dict[str, str]]:
                return [{"symbol": s, "price": str(p)} for s, p in prices.items()]


            def fake_exchange_rules(
                rules: Dict[str, Dict[str, Any]]
            ) -> Dict[str, Dict[str, Any]]:
                # rules mapping: symbol -> {step_size, min_qty, min_notional, base_asset, quote_asset}
                return rules


            def load_schema(name: str) -> Dict[str, Any]:
                schema_path = Path(__file__).resolve().parents[1] / "src" / "spectre" / "schemas" / name
                return json.loads(schema_path.read_text(encoding="utf-8"))


            def validate_jsonschema(instance: Dict[str, Any], schema: Dict[str, Any]) -> None:
                import jsonschema
                jsonschema.validate(instance=instance, schema=schema)
            """
        ),
    )

    # Core invariants for execution plan under many conditions, with NO network.
    w(
        TESTS / "test_execution_plan_offline_unit.py",
        textwrap.dedent(
            """
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
            """
        ),
    )

    # Tests that ensure the plan is stable with different symbol sets and odd inputs.
    w(
        TESTS / "test_execution_plan_edge_cases.py",
        textwrap.dedent(
            """
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
            """
        ),
    )

    print("Wrote tests:")
    for p in sorted(TESTS.glob("test_*.py")):
        print(" -", p.name)
    print("Also wrote pytest.ini and tests/_helpers.py")


    # Sanity check: generated tests must be valid Python modules.
    import py_compile
    for tf in sorted(TESTS.glob("test_*.py")):
        py_compile.compile(str(tf), doraise=True)


if __name__ == "__main__":
    main()

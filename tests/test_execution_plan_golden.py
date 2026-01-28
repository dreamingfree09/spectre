from __future__ import annotations

import json
from pathlib import Path

import spectre.execution_plan as ep
from tests._helpers import FakeResponse, fake_ticker_payload, minimal_decision, minimal_facts


GOLDEN = Path(__file__).resolve().parent / "golden_execution_plan.json"


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


def _normalise(plan: dict) -> dict:
    # Remove volatile timestamps so the golden comparison is deterministic.
    plan = json.loads(json.dumps(plan))  # deep copy
    plan.pop("as_of_utc", None)
    if "pricing" in plan:
        plan["pricing"].pop("as_of_utc", None)
    if "exchange_rules" in plan:
        plan["exchange_rules"].pop("as_of_utc", None)
    return plan


def test_execution_plan_matches_golden(monkeypatch):
    _patch_prices_ok(monkeypatch)
    _patch_rules_ok(monkeypatch)

    plan = ep.build_execution_plan(minimal_facts(), minimal_decision(), "facts.json", "decision.json")
    plan_n = _normalise(plan)

    if not GOLDEN.exists():
        GOLDEN.write_text(json.dumps(plan_n, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise AssertionError("Golden file was missing; created it. Re-run the test.")

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert plan_n == golden

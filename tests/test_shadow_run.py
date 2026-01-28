from __future__ import annotations

import json
from pathlib import Path

import spectre.execution_plan as ep
from spectre.shadow_run import main as shadow_main
from tests._helpers import FakeResponse, fake_ticker_payload, minimal_decision, minimal_facts


def test_shadow_run_produces_deterministic_report(monkeypatch, tmp_path: Path, capsys):
    # Patch pricing + rules to be deterministic.
    def fake_get(url, timeout=10):
        return FakeResponse(fake_ticker_payload({"BTCUSDT": 90000.0, "ETHUSDT": 3000.0}))

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

    monkeypatch.setattr(ep.requests, "get", fake_get)
    monkeypatch.setattr(ep, "fetch_exchange_info", fake_fetch_exchange_info)

    facts_p = tmp_path / "facts.json"
    decision_p = tmp_path / "decision.json"
    state_p = tmp_path / "state.json"

    facts_p.write_text(json.dumps(minimal_facts()), encoding="utf-8")
    decision_p.write_text(json.dumps(minimal_decision()), encoding="utf-8")
    state_p.write_text(json.dumps({"balances": {"USDT": 100.0, "BTC": 0.0, "ETH": 0.0}}), encoding="utf-8")

    rc = shadow_main([str(facts_p), str(decision_p), str(state_p)])
    assert rc == 0

    out = capsys.readouterr().out
    payload = json.loads(out)

    # Normalise timestamps so the test is deterministic.
    plan = payload["execution_plan"]
    plan.pop("as_of_utc", None)
    if "pricing" in plan:
        plan["pricing"].pop("as_of_utc", None)
    if "exchange_rules" in plan:
        plan["exchange_rules"].pop("as_of_utc", None)

    # Sanity: must contain both plan + simulation report
    assert payload["simulation_report"]["action"] in ("rebalance", "no_action")
    assert "execution_plan" in payload
    assert "simulation_report" in payload

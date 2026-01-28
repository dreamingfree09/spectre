
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

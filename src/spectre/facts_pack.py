from datetime import datetime, timezone
from dateutil import parser

SCHEMA_VERSION = "1.0"


def build_facts_pack(symbols, lookback_days, candles_by_symbol, vol_by_symbol, corr_symbols, corr_matrix, sample_size, provenance_note=None, warnings=None):
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
    facts = {
        "schema_version": SCHEMA_VERSION,
        "as_of_utc": now_utc,
        "universe": {
            "venue": "binance",
            "symbols": symbols
        },
        "timeframe": {
            "candle": "1d",
            "lookback_days": lookback_days
        },
        "market_data": {
            "candles": candles_by_symbol
        },
        "computed": {
            "realised_vol_annualised": {s: vol_by_symbol[s] for s in symbols},
            "correlation": {
                "symbols": corr_symbols,
                "matrix": corr_matrix
            }
        },
        "provenance": {
            "sources": [
                {
                    "name": "Binance Spot Public REST",
                    "type": "market_data",
                    "retrieved_at_utc": now_utc,
                    "note": provenance_note or "/api/v3/klines"
                }
            ]
        }
    }
    if warnings:
        facts["warnings"] = warnings
    return facts

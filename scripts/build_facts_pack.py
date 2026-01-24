import os
import sys
import argparse
import json
from jsonschema import validate, Draft202012Validator, ValidationError
from spectre.binance_public import fetch_daily_candles
from spectre.compute import compute_realised_vol_annualised, compute_correlation_matrix, InsufficientDataError
from spectre.facts_pack import build_facts_pack

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'schemas', 'facts_pack.schema.json')
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'artifacts')


def main():
    parser = argparse.ArgumentParser(description="Build facts pack from Binance public data.")
    parser.add_argument('--symbols', required=True, help='Comma-separated symbols (e.g. BTCUSDT,ETHUSDT)')
    parser.add_argument('--lookback-days', type=int, required=True, help='Number of days to look back')
    parser.add_argument('--out', required=True, help='Output path for facts pack JSON')
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(',') if s.strip()]
    lookback_days = args.lookback_days
    out_path = args.out
    from pathlib import Path
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    candles_by_symbol = {}
    for symbol in symbols:
        try:
            candles = fetch_daily_candles(symbol, lookback_days)
        except Exception as e:
            print(f"ERROR: Failed to fetch candles for {symbol}: {e}")
            sys.exit(1)
        if not candles:
            print(f"ERROR: No candles returned for {symbol}")
            sys.exit(1)
        candles_by_symbol[symbol] = candles

    vol_by_symbol = {}
    for symbol, candles in candles_by_symbol.items():
        try:
            vol = compute_realised_vol_annualised(candles)
        except InsufficientDataError as e:
            print(f"ERROR: {symbol}: {e}")
            sys.exit(1)
        vol_by_symbol[symbol] = vol

    try:
        corr_symbols, corr_matrix, sample_size = compute_correlation_matrix(candles_by_symbol)
    except InsufficientDataError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    warnings = None
    # If sample_size < lookback_days, warn
    if sample_size < lookback_days:
        warnings = [f"Aligned sample size reduced to {sample_size} due to timestamp intersection."]

    facts_pack = build_facts_pack(
        symbols=symbols,
        lookback_days=lookback_days,
        candles_by_symbol=candles_by_symbol,
        vol_by_symbol=vol_by_symbol,
        corr_symbols=corr_symbols,
        corr_matrix=corr_matrix,
        sample_size=sample_size,
        provenance_note="/api/v3/klines",
        warnings=warnings
    )

    # Validate
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema)
    try:
        validator.validate(facts_pack)
    except ValidationError as e:
        print(f"ERROR: Facts pack failed schema validation: {e.message}")
        sys.exit(1)

    # Write
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(facts_pack, f, indent=2)

    print("FACTS PACK VALID")
    print(f"Symbols: {', '.join(symbols)}")
    for symbol in symbols:
        print(f"  {symbol}: {len(candles_by_symbol[symbol])} candles")
    print(f"Sample size used for returns/correlation: {sample_size}")
    sys.exit(0)

if __name__ == "__main__":
    main()

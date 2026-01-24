import requests
from datetime import datetime, timezone
from dateutil import parser


BINANCE_EXCHANGE_INFO_API = "https://api.binance.com/api/v3/exchangeInfo"
BINANCE_API = "https://api.binance.com/api/v3/klines"

import decimal
from decimal import Decimal

def fetch_exchange_info(symbols: list[str]) -> dict:
    """
    Fetch exchange info for given symbols from Binance public API.
    Returns dict keyed by symbol with fields:
      step_size, min_qty, min_notional, base_asset, quote_asset
    """
    if not symbols:
        return {}
    url = BINANCE_EXCHANGE_INFO_API
    import json as _json
    # Binance expects no spaces in the symbols param
    symbols_param = _json.dumps(symbols, separators=(',', ':'))
    params = {"symbols": symbols_param}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    result = {}
    for s in data.get("symbols", []):
        symbol = s.get("symbol")
        base_asset = s.get("baseAsset")
        quote_asset = s.get("quoteAsset")
        step_size = None
        min_qty = None
        min_notional = None
        # Parse filters robustly
        for f in s.get("filters", []):
            ftype = f.get("filterType")
            if ftype == "LOT_SIZE":
                step_size = Decimal(f.get("stepSize", "0"))
                min_qty = Decimal(f.get("minQty", "0"))
            elif ftype == "MIN_NOTIONAL":
                try:
                    min_notional = float(f.get("minNotional", 0.0))
                except Exception:
                    min_notional = 0.0
            elif ftype == "NOTIONAL":
                # Only set if not already set by MIN_NOTIONAL
                if min_notional is None or min_notional == 0.0:
                    # Try keys in order
                    for key in ["minNotional", "notionalMin", "minNotionalValue", "minNotionalAmount"]:
                        val = f.get(key)
                        if val is not None:
                            try:
                                min_notional = float(val)
                                break
                            except Exception:
                                continue
        # Fallbacks
        if step_size is None:
            step_size = Decimal("0.00000001")
        if min_qty is None:
            min_qty = Decimal("0")
        if min_notional is None:
            min_notional = 0.0
        result[symbol] = {
            "step_size": float(step_size),
            "min_qty": float(min_qty),
            "min_notional": float(min_notional),
            "base_asset": base_asset,
            "quote_asset": quote_asset
        }
    return result


def fetch_daily_candles(symbol, lookback_days):
    candles = []
    max_limit = 1000
    end_time = None
    fetched = 0
    while fetched < lookback_days:
        limit = min(max_limit, lookback_days - fetched)
        params = {
            "symbol": symbol,
            "interval": "1d",
            "limit": limit
        }
        if end_time:
            params["endTime"] = end_time
        resp = requests.get(BINANCE_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        for k in data:
            t = datetime.utcfromtimestamp(k[0] / 1000).replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
            candle = {
                "t": t,
                "o": float(k[1]),
                "h": float(k[2]),
                "l": float(k[3]),
                "c": float(k[4]),
                "v": float(k[5])
            }
            candles.append(candle)
        # Pagination: set end_time to one ms before earliest candle
        end_time = data[0][0] - 1 if data else None
        fetched += len(data)
        if len(data) < limit:
            break
    # Return most recent N candles
    candles = sorted(candles, key=lambda x: x["t"], reverse=True)[:lookback_days]
    return list(reversed(candles))

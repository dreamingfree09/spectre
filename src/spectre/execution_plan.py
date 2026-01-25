

import json
from typing import Dict, Any, List
import requests
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from spectre.binance_public import fetch_exchange_info


SCHEMA_VERSION = "1.3"
VENUE = "binance"
MODE = "dry_run"
QUOTE_CURRENCY = "USDT"
NOTIONAL_BUDGET_QUOTE = 50.0  # Default value, can be overridden by env var
MIN_ORDER_NOTIONAL = 5.0


def build_execution_plan(facts_pack: Dict[str, Any], decision_packet: Dict[str, Any], facts_pack_path: str, decision_packet_path: str) -> Dict[str, Any]:
    import os
    # Allow override of NOTIONAL_BUDGET_QUOTE via env var
    env_budget = os.environ.get("SPECTRE_BUDGET_QUOTE", "")
    budget_quote = NOTIONAL_BUDGET_QUOTE
    budget_override_invalid = False
    budget_override_value = None
    if env_budget:
        try:
            budget_override_value = float(env_budget)
            if budget_override_value > 0:
                budget_quote = budget_override_value
            else:
                budget_override_invalid = True
        except Exception:
            budget_override_invalid = True

    # Fetch public prices from Binance
    # Fetch public prices from Binance
    allowed_symbols = decision_packet.get("allowed_symbols", [])
    pricing = {
        "as_of_utc": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z'),
        "source": "binance_public",
        "prices": {}
    }
    try:
        resp = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=10)
        resp.raise_for_status()
        all_prices = {item["symbol"]: float(item["price"]) for item in resp.json()}
        for symbol in allowed_symbols:
            price = all_prices.get(symbol)
            if price and price > 0:
                pricing["prices"][symbol] = price
    except Exception:
        for symbol in allowed_symbols:
            pricing["prices"][symbol] = None

    # Fetch exchange rules for allowed_symbols
    exchange_rules = {
        "as_of_utc": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z'),
        "source": "binance_exchange_info",
        "symbols": {}
    }
    rules = fetch_exchange_info(allowed_symbols)
    for symbol, rule in rules.items():
        exchange_rules["symbols"][symbol] = rule
    as_of_utc = decision_packet.get("as_of_utc")
    strategy_mode = decision_packet.get("strategy_mode")
    max_gross_exposure = decision_packet.get("max_gross_exposure", 0)
    allowed_symbols = decision_packet.get("allowed_symbols", [])
    risk_score = decision_packet.get("risk_score", None)

    refusals: List[Dict[str, Any]] = []
    if budget_override_invalid:
        refusals.append({
            "code": "BAD_BUDGET_OVERRIDE",
            "symbol": "*",
            "message": f"Invalid SPECTRE_BUDGET_QUOTE={env_budget}; using default 50.0"
        })
    plan_action = None
    orders: List[Dict[str, Any]] = []

    if strategy_mode == "do_nothing":
        plan_action = "no_action"
        refusals.append({
            "code": "STRATEGY_DO_NOTHING",
            "symbol": "*",
            "message": "Strategy mode is do_nothing. No action taken."
        })
    elif max_gross_exposure == 0:
        plan_action = "no_action"
        refusals.append({
            "code": "ZERO_GROSS_EXPOSURE",
            "symbol": "*",
            "message": "Max gross exposure is zero. No action taken."
        })
    elif not allowed_symbols:
        plan_action = "no_action"
        refusals.append({
            "code": "NO_ALLOWED_SYMBOLS",
            "symbol": "*",
            "message": "No allowed symbols. No action taken."
        })
    elif strategy_mode in ("trend", "mean_revert", "reduce_risk"):
        per_order_notional = round(budget_quote / len(allowed_symbols), 2) if allowed_symbols else 0
        if per_order_notional < MIN_ORDER_NOTIONAL:
            plan_action = "rebalance"
            for symbol in allowed_symbols:
                refusals.append({
                    "code": "BELOW_MIN_NOTIONAL",
                    "symbol": symbol,
                    "message": f"Per-order notional ({per_order_notional}) below minimum ({MIN_ORDER_NOTIONAL}). No orders created."
                })
        else:
            plan_action = "rebalance"
            for symbol in allowed_symbols:
                price_used = pricing["prices"].get(symbol)
                if not price_used or price_used <= 0:
                    refusals.append({
                        "code": "NO_PRICE",
                        "symbol": symbol,
                        "message": f"No valid price for {symbol}. Order not created."
                    })
                    continue
                rule = rules.get(symbol)
                if not rule:
                    refusals.append({
                        "code": "NO_EXCHANGE_RULES",
                        "symbol": symbol,
                        "message": f"No exchange rules for {symbol}. Order not created."
                    })
                    continue
                try:
                    step_size = Decimal(str(rule["step_size"]))
                    min_qty = Decimal(str(rule["min_qty"]))
                    min_notional = Decimal(str(rule["min_notional"]))
                except (KeyError, InvalidOperation):
                    refusals.append({
                        "code": "BAD_EXCHANGE_RULES",
                        "symbol": symbol,
                        "message": f"Invalid exchange rules for {symbol}. Order not created."
                    })
                    continue
                try:
                    raw_qty = Decimal(str(per_order_notional)) / Decimal(str(price_used))
                except (InvalidOperation, ZeroDivisionError):
                    refusals.append({
                        "code": "BAD_PRICE",
                        "symbol": symbol,
                        "message": f"Invalid price for {symbol}. Order not created."
                    })
                    continue
                # Round DOWN to step size
                if step_size > 0:
                    qty = (raw_qty // step_size) * step_size
                else:
                    qty = Decimal("0")
                # Defensive: avoid float drift
                qty = qty.quantize(step_size, rounding=ROUND_DOWN) if step_size > 0 else Decimal("0")
                # Refusal if qty rounds to zero
                if qty <= 0:
                    refusals.append({
                        "code": "ROUNDING_TO_ZERO",
                        "symbol": symbol,
                        "message": f"{symbol}: raw_qty={raw_qty}, qty={qty}, step_size={step_size} rounded to zero."
                    })
                    continue
                # Enforce min_qty
                if qty < min_qty:
                    refusals.append({
                        "code": "BELOW_MIN_QTY",
                        "symbol": symbol,
                        "message": f"{symbol}: qty={qty} < min_qty={min_qty}. raw_qty={raw_qty}, step_size={step_size}"
                    })
                    continue
                # Enforce min_notional (only if min_notional > 0)
                notional = qty * Decimal(str(price_used))
                if min_notional > 0 and notional < min_notional:
                    refusals.append({
                        "code": "BELOW_MIN_NOTIONAL",
                        "symbol": symbol,
                        "message": f"{symbol}: qty={qty}, notional={notional} < min_notional={min_notional}. raw_qty={raw_qty}, step_size={step_size}, price_used={price_used}, effective_notional={notional}"
                    })
                    continue
                orders.append({
                    "symbol": symbol,
                    "side": "BUY",
                    "order_type": "MARKET",
                    "notional_quote": float(per_order_notional),
                    "price_used": float(price_used),
                    "quantity_base": float(qty),
                    "step_size_used": float(step_size),
                    "min_qty_used": float(min_qty),
                    "min_notional_used": float(min_notional),
                    "rationale": f"{strategy_mode} strategy, risk_score={risk_score}"
                })
        # If after processing there are zero orders AND no refusals, treat as no_action
        if not orders and not refusals:
            plan_action = "no_action"
    else:
        plan_action = "no_action"
        refusals.append({
            "code": "UNRECOGNIZED_STRATEGY_MODE",
            "symbol": "*",
            "message": f"Unrecognized strategy_mode: {strategy_mode}. No action taken."
        })

    plan = {
        "action": plan_action,
        "orders": orders
    }
    # Top-level audit fields
    as_of_utc = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_utc": as_of_utc,
        "venue": VENUE,
        "mode": MODE,
        "inputs": {
            "facts_pack_path": facts_pack_path,
            "decision_packet_path": decision_packet_path
        },
        "portfolio": {
            "quote_currency": QUOTE_CURRENCY,
            "notional_budget_quote": budget_quote
        },
        "pricing": pricing,
        "exchange_rules": exchange_rules,
        "plan": plan,
        "refusals": refusals
    }

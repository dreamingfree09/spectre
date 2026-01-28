from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple


def load_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _split_symbol(symbol: str) -> Tuple[str, str]:
    # v0 assumption for Spectre: quote is always USDT.
    if not symbol.endswith("USDT"):
        raise ValueError(f"Unsupported symbol format (expected *USDT): {symbol}")
    return symbol[:-4], "USDT"


def simulate_execution_plan(
    plan: Dict[str, Any],
    portfolio_state: Dict[str, Any],
    *,
    all_or_nothing: bool = True,
) -> Dict[str, Any]:
    balances: Dict[str, float] = dict(portfolio_state.get("balances", {}))
    orders = list(plan.get("plan", {}).get("orders", []))

    accepted: list[Dict[str, Any]] = []
    rejected: list[Dict[str, Any]] = []

    # If the plan itself is no_action, simulation is a no-op.
    if plan.get("plan", {}).get("action") != "rebalance" or not orders:
        return {
            "action": "no_action",
            "accepted_orders": [],
            "rejected_orders": [],
            "resulting_balances": balances,
        }

    # v0: only BUY orders supported.
    # Determine cumulative required quote spend for BUY orders.
    required_quote_total = 0.0
    quote_currency = "USDT"

    for o in orders:
        symbol = o.get("symbol")
        side = o.get("side")
        notional = float(o.get("notional_quote", 0.0))

        if side != "BUY":
            rejected.append({"symbol": symbol, "reason": "UNSUPPORTED_SIDE"})
            continue

        # Validate symbol format.
        _base, quote = _split_symbol(symbol)
        quote_currency = quote

        if notional <= 0:
            rejected.append({"symbol": symbol, "reason": "BAD_NOTIONAL"})
            continue

        required_quote_total += notional

    quote_bal = float(balances.get(quote_currency, 0.0))

    # All-or-nothing: if ANY problem exists OR cumulative spend exceeds balance, abort.
    if all_or_nothing:
        if rejected:
            return {
                "action": "no_action",
                "accepted_orders": [],
                "rejected_orders": rejected + [{"symbol": "*", "reason": "ALL_OR_NOTHING_ABORT"}],
                "resulting_balances": balances,
            }
        if required_quote_total > quote_bal:
            # Reject each order deterministically with insufficient balance.
            for o in orders:
                rejected.append({"symbol": o.get("symbol"), "reason": "INSUFFICIENT_BALANCE"})
            rejected.append({"symbol": "*", "reason": "ALL_OR_NOTHING_ABORT"})
            return {
                "action": "no_action",
                "accepted_orders": [],
                "rejected_orders": rejected,
                "resulting_balances": balances,
            }

    # If partial execution is allowed, we execute sequentially as long as balance remains.
    for o in orders:
        symbol = o.get("symbol")
        side = o.get("side")
        notional = float(o.get("notional_quote", 0.0))
        price = float(o.get("price_used") or 0.0)

        if side != "BUY":
            rejected.append({"symbol": symbol, "reason": "UNSUPPORTED_SIDE"})
            continue

        if notional <= 0:
            rejected.append({"symbol": symbol, "reason": "BAD_NOTIONAL"})
            continue

        base, quote = _split_symbol(symbol)
        quote_bal = float(balances.get(quote, 0.0))

        if price <= 0:
            rejected.append({"symbol": symbol, "reason": "MISSING_PRICE_USED"})
            if all_or_nothing:
                return {
                    "action": "no_action",
                    "accepted_orders": [],
                    "rejected_orders": rejected + [{"symbol": "*", "reason": "ALL_OR_NOTHING_ABORT"}],
                    "resulting_balances": balances,
                }
            continue

        if quote_bal < notional:
            rejected.append({"symbol": symbol, "reason": "INSUFFICIENT_BALANCE"})
            if all_or_nothing:
                return {
                    "action": "no_action",
                    "accepted_orders": [],
                    "rejected_orders": rejected + [{"symbol": "*", "reason": "ALL_OR_NOTHING_ABORT"}],
                    "resulting_balances": balances,
                }
            continue

        qty = notional / price
        balances[quote] = quote_bal - notional
        balances[base] = float(balances.get(base, 0.0)) + qty

        accepted.append(
            {
                "symbol": symbol,
                "side": "BUY",
                "notional_quote": notional,
                "price_used": price,
                "quantity_base_simulated": qty,
            }
        )

    final_action = "rebalance" if accepted else "no_action"
    if all_or_nothing and rejected:
        final_action = "no_action"
        accepted = []

    return {
        "action": final_action,
        "accepted_orders": accepted,
        "rejected_orders": rejected,
        "resulting_balances": balances,
    }


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print("Usage: python -m spectre.simulator_stub <execution_plan.json> <portfolio_state.json>")
        return 2

    plan = load_json(argv[0])
    state = load_json(argv[1])
    report = simulate_execution_plan(plan, state, all_or_nothing=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

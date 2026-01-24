"""
decision_rules.py
Deterministic decision packet builder for spectre.
"""
from typing import Dict, Any, List
import statistics

def build_decision_packet(facts_pack: Dict[str, Any]) -> Dict[str, Any]:
    symbols = facts_pack.get("universe", {}).get("symbols", [])
    symbol_stats = facts_pack.get("symbol_stats", {})
    correlations = facts_pack.get("correlations", {})
    warnings = facts_pack.get("warnings", [])
    as_of_utc = facts_pack.get("as_of_utc")

    # Extract realised_vol_annualised for all symbols
    vols = [symbol_stats[s].get("realised_vol_annualised", 0.0) for s in symbols if s in symbol_stats]
    max_vol = max(vols) if vols else 0.0
    min_vol = min(vols) if vols else 0.0

    # Compute average pairwise correlation (off-diagonal only)
    corr_matrix = correlations.get("matrix", [])
    n = len(corr_matrix)
    off_diag = []
    for i in range(n):
        for j in range(n):
            if i != j:
                off_diag.append(corr_matrix[i][j])
    avg_corr = statistics.mean(off_diag) if off_diag else 0.0

    # Regime
    if any(v > 0.80 for v in vols):
        global_regime = "risk_off"
    elif all(v < 0.45 for v in vols) and avg_corr < 0.60:
        global_regime = "risk_on"
    else:
        global_regime = "neutral"

    # Risk score
    risk_score = 50
    if max_vol > 0.80:
        risk_score += 20
    if max_vol > 0.65:
        risk_score += 10
    if avg_corr > 0.75:
        risk_score += 10
    if max_vol < 0.45:
        risk_score -= 10
    risk_score = max(0, min(100, risk_score))

    # Vol target
    if global_regime == "risk_off":
        vol_target_annualised = 0.10
    elif global_regime == "risk_on":
        vol_target_annualised = 0.25
    else:
        vol_target_annualised = 0.20

    # Max gross exposure
    if global_regime == "risk_off":
        max_gross_exposure = 0.20
    elif global_regime == "neutral":
        max_gross_exposure = 0.50
    else:
        max_gross_exposure = 1.00

    # Strategy mode
    if global_regime == "risk_off":
        strategy_mode = "reduce_risk"
    elif global_regime == "neutral":
        strategy_mode = "do_nothing"
    else:
        strategy_mode = "trend"

    # Allowed/blocked symbols
    allowed_symbols = list(symbols)
    blocked_symbols = []
    for idx, s in enumerate(symbols):
        v = symbol_stats.get(s, {}).get("realised_vol_annualised", 0.0)
        if v > 1.00:
            blocked_symbols.append(s)
    allowed_symbols = [s for s in allowed_symbols if s not in blocked_symbols]

    # Top risks (schema: each must have 'risk' and 'rationale')
    top_risks = [
        {
            "risk": "Volatility",
            "rationale": f"Max realised volatility is {max_vol:.2f}."
        },
        {
            "risk": "Correlation",
            "rationale": f"Average pairwise correlation is {avg_corr:.2f}."
        }
    ]
    if warnings:
        top_risks.append({
            "risk": "Data quality",
            "rationale": f"Warnings present: {', '.join(str(w) for w in warnings)}"
        })

    # Kill switch
    if global_regime == "risk_off":
        max_daily_drawdown = 0.03
    elif global_regime == "neutral":
        max_daily_drawdown = 0.05
    else:
        max_daily_drawdown = 0.08
    kill_switch = {
        "max_daily_drawdown": max_daily_drawdown,
        "conditions": [
            "Schema validation failure",
            "Daily drawdown breach",
            "Missing data / insufficient samples"
        ]
    }

    # Build packet
    decision_packet = {
        "schema_version": "1.0",
        "as_of_utc": as_of_utc,
        "global_regime": global_regime,
        "risk_score": risk_score,
        "vol_target_annualised": vol_target_annualised,
        "max_gross_exposure": max_gross_exposure,
        "strategy_mode": strategy_mode,
        "allowed_symbols": allowed_symbols,
        "blocked_symbols": blocked_symbols,
        "top_risks": top_risks,
        "kill_switch": kill_switch
    }
    # If as_of_utc missing, set to current UTC
    if not decision_packet["as_of_utc"]:
        from datetime import datetime, timezone
        decision_packet["as_of_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return decision_packet


import math
import statistics

class InsufficientDataError(Exception):
    pass


def compute_realised_vol_annualised(candles):
    closes = [c["c"] for c in candles]
    returns = []
    for i in range(1, len(closes)):
        returns.append(math.log(closes[i] / closes[i-1]))
    if len(returns) < 30:
        raise InsufficientDataError("Insufficient data: need at least 30 return observations.")
    vol = statistics.stdev(returns) * math.sqrt(365)
    return float(vol)


def compute_correlation_matrix(candles_by_symbol):
    # Align by intersection of timestamps
    symbols = list(candles_by_symbol.keys())
    ts_sets = [set(c["t"] for c in candles_by_symbol[s]) for s in symbols]
    common_ts = set.intersection(*ts_sets)
    if not common_ts:
        raise InsufficientDataError("No overlapping timestamps across symbols.")
    aligned = []
    for s in symbols:
        ts_to_candle = {c["t"]: c for c in candles_by_symbol[s]}
        aligned.append([ts_to_candle[t]["c"] for t in sorted(common_ts)])

    # Compute log returns for each symbol
    returns_by_symbol = []
    for closes in aligned:
        returns = [math.log(closes[i] / closes[i-1]) for i in range(1, len(closes))]
        returns_by_symbol.append(returns)

    sample_size = len(returns_by_symbol[0]) if returns_by_symbol else 0
    if sample_size < 30:
        raise InsufficientDataError("Insufficient data: need at least 30 aligned return observations.")

    # Compute correlation matrix
    n = len(symbols)
    corr_matrix = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            x = returns_by_symbol[i]
            y = returns_by_symbol[j]
            if i == j:
                corr_matrix[i][j] = 1.0
            else:
                mean_x = statistics.mean(x)
                mean_y = statistics.mean(y)
                cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / (sample_size - 1)
                stdev_x = statistics.stdev(x)
                stdev_y = statistics.stdev(y)
                if stdev_x == 0 or stdev_y == 0:
                    corr = 0.0
                else:
                    corr = cov / (stdev_x * stdev_y)
                corr_matrix[i][j] = corr
    return symbols, corr_matrix, sample_size

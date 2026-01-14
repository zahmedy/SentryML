from __future__ import annotations

import math
from typing import Sequence, List, Tuple

def _quantile(sorted_vals: Sequence[float], q: float) -> float:
    """
    q in [0, 1] Linear interpolation between closest ranks.
    Assumes sorted_vals is sorted ascending.
    """
    n = len(sorted_vals)
    if n == 0:
        raise ValueError("Empty data")
    if n == 1:
        return float(sorted_vals[0])
    
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac)


def quantile_edges(baseline: Sequence[float], num_bins: int) -> List[float]:
    """
    Compute bin edges from baseline quantiles: q0..q1 (num_bins+1 edges).
    Ensure edges are strictly increasing by nudging ties slightly.
    """
    if num_bins <= 1:
        raise ValueError("num_bins must be > 1")
    b = sorted(float(x) for x in baseline)
    if len(b) == 0:
        raise ValueError("baseline is empty")
    
    edges = [_quantile(b, n / num_bins) for n in range(num_bins + 1)]

    # Ensure strictly increasing edges (handle constant/near-constant distributions)
    # Nudge ties by a tiny epsilon that grows with magnitude.
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            eps = 1e-12 if edges[i - 1] == 0 else abs(edges[i - 1]) * 1e-12
            edges[i] = edges[i - 1] + eps
    
    return edges


def _histogram(values: Sequence[float], edges: Sequence[float]) -> List[int]:
    """
    Bin values into edges (len = num_bins+1). Last bin includes right edge.
    """
    counts = [0] * (len(edges) - 1)
    for x in values:
        x = float(x)
        # fast path: outside range goes to end bins
        if x < edges[0]:
            counts[0] += 1
            continue
        if x > edges[-1]:
            counts[-1] += 1
            continue

        # linear scan is OK for <= 50 bins; can binary search later
        for i in range(len(edges) - 1):
            left, right = edges[i], edges[i + 1]
            if i == len(edges) - 2:
                if left <= x <= right:
                    counts[i] += 1
                    break
            else:
                if left <= x < right:
                    counts[i] += 1
                    break
    return counts

def winsorize(values: Sequence[float], lo: float, hi: float) -> List[float]:
    """
    Clip values to [lo, hi] (outlier protection).
    """
    out = []
    for x in values:
        x = float(x)
        if x < lo:
            out.append(lo)
        elif x > hi:
            out.append(hi)
        else:
            out.append(x)
    return out

def psi_quantile(
        baseline: Sequence[float],
        current: Sequence[float],
        num_bins: int = 10,
        eps: float = 1e-6,
        winsor_q: float = 0.01, # clip current to baseline [q, 1-q]
) -> float:
    """
    PSI with quantile bins derived from baseline.
    Works for unbounded scores.
    
    - Compute edges from baseline quantiles.
    - Winsorize current to baseline [q, 1-q] range to reduce extreme outliner impact.
    """
    if len(baseline) == 0 or len(current) == 0:
        return 0.0
    
    edges = quantile_edges(baseline, num_bins)

    # Winsorize current using baseline's inner quantiles
    b_sorted = sorted(float(x) for x in baseline)
    lo = _quantile(b_sorted, winsor_q)
    hi = _quantile(b_sorted, 1.0 - winsor_q)
    cur = winsorize(current, lo, hi)

    b_counts = _histogram(baseline, edges)
    c_counts = _histogram(cur, edges)

    b_total = sum(b_counts)
    c_total = sum(c_counts)
    if b_total == 0 or c_total == 0:
        return 0.0
    
    score = 0.0
    for b, c in zip(b_counts, c_counts):
        b_pct = max(b / b_total, eps)
        c_pct = max(c / c_total, eps)
        score += (c_pct - b_pct) * math.log(c_pct / b_pct)

    return float(score)
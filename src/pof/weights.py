"""
Weighted descriptive statistics over Polars/NumPy data.

POF is a complex sample survey: every consumption unit (UC) carries an expansion
weight (PESO_FINAL) that says how many real households it represents. Unweighted
means/medians describe the *sample*, not the *population*. All point estimates in
the thesis should be weighted.

These helpers are deliberately small and pure (NumPy in, scalar out) so they are
trivial to unit-test and reuse inside Polars `group_by().agg()` is not possible
for medians/modes — Polars has no built-in weighted median — so the household
builder calls these per group via `map_groups` / pandas where needed.
"""
from __future__ import annotations

import numpy as np


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Population mean E[x] = sum(w*x) / sum(w)."""
    values = np.asarray(values, dtype="float64")
    weights = np.asarray(weights, dtype="float64")
    mask = ~np.isnan(values) & ~np.isnan(weights) & (weights > 0)
    if not mask.any():
        return float("nan")
    return float(np.sum(values[mask] * weights[mask]) / np.sum(weights[mask]))


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """
    Weighted median: the value where the cumulative weight crosses 50%.

    Uses linear interpolation between the two straddling order statistics, which
    matches the standard definition used by survey packages.
    """
    values = np.asarray(values, dtype="float64")
    weights = np.asarray(weights, dtype="float64")
    mask = ~np.isnan(values) & ~np.isnan(weights) & (weights > 0)
    if not mask.any():
        return float("nan")
    v, w = values[mask], weights[mask]
    order = np.argsort(v)
    v, w = v[order], w[order]
    cum = np.cumsum(w) - 0.5 * w
    cum /= np.sum(w)
    return float(np.interp(0.5, cum, v))


def weighted_mode(values: np.ndarray, weights: np.ndarray) -> float:
    """
    Weighted mode: the value carrying the largest total weight.

    Appropriate for ORDINAL/CATEGORICAL variables (e.g. NIVEL_INSTRUCAO), where a
    mean has no semantic meaning. Ties are broken by the smaller value.
    """
    values = np.asarray(values, dtype="float64")
    weights = np.asarray(weights, dtype="float64")
    mask = ~np.isnan(values) & ~np.isnan(weights) & (weights > 0)
    if not mask.any():
        return float("nan")
    v, w = values[mask], weights[mask]
    uniq = np.unique(v)
    totals = np.array([w[v == u].sum() for u in uniq])
    return float(uniq[int(np.argmax(totals))])

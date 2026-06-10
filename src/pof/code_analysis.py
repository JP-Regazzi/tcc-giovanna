"""
Per-code analysis: which debt types are relatively higher for LOWER education?

For EVERY candidate debt product code (active or commented-out; see code_catalog),
we measure how the household debt-to-income ratio for that single code moves with
education:

  1. Aggregate the code's deflated + annualized spending per UC.
  2. Join to the household table (education value, UC income, PESO_FINAL weight).
  3. debt_to_income = code_debt / household_income.
  4. Weighted OLS: debt_to_income ~ education  (population-weighted by PESO_FINAL).
     - slope sign > 0  => debt rises with education (more relevant to HIGH education)
     - slope sign < 0  => debt falls with education (more relevant to LOW education)
  5. Also report the weighted Pearson correlation r, its p-value, the number of UCs
     with any spend, and the weighted mean debt/income in the lowest vs highest
     education band (a model-free read of the direction).

Codes are SORTED by slope so the most "low-education" debts sit at one end and the
most "high-education" debts at the other. Output: a machine-readable CSV and a
human-readable Markdown report, produced for each requested education variable.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import polars as pl

from .config import AnalysisConfig
from .code_catalog import full_catalog, CodeInfo
from .debt import DebtAggregator


@dataclass
class CodeResult:
    code: str
    label: str
    category: str
    active: bool
    n_with_spend: int
    weighted_mean_ratio: float
    slope: float
    slope_p: float
    corr_r: float
    direction: str           # "higher with education" / "lower with education" / "flat/none"
    ratio_low_band: float
    ratio_high_band: float

    def as_row(self) -> Dict:
        return {
            "code": self.code,
            "label": self.label,
            "category": self.category,
            "active": self.active,
            "n_ucs_with_spend": self.n_with_spend,
            "weighted_mean_debt_to_income": self.weighted_mean_ratio,
            "slope_vs_education": self.slope,
            "slope_p_value": self.slope_p,
            "weighted_corr_r": self.corr_r,
            "direction": self.direction,
            "ratio_lowest_edu_band": self.ratio_low_band,
            "ratio_highest_edu_band": self.ratio_high_band,
        }


class PerCodeAnalysis:
    """Runs the per-code debt-vs-education analysis for one education variable."""

    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.aggregator = DebtAggregator(config)

    def run(self, households: pl.DataFrame, despesa_ind, despesa_col) -> pd.DataFrame:
        """
        ``households`` must contain the UC keys, ``education`` (the configured
        measure), ``household_income``, ``weight`` and ``education_band``.
        Returns a DataFrame of CodeResult rows, sorted by slope (ascending:
        most 'lower-with-education' first).
        """
        c = self.config
        keys = list(c.uc_keys)
        hh = households.select([*keys, "education", "household_income", "weight",
                                "education_band"]).to_pandas()
        hh["education"] = pd.to_numeric(hh["education"], errors="coerce")
        bands = c.education_band_spec()[1]
        low_band, high_band = bands[0], bands[-1]

        results: List[CodeResult] = []
        for info in full_catalog():
            res = self._analyze_code(info, hh, despesa_ind, despesa_col, low_band, high_band)
            if res is not None:
                results.append(res)

        df = pd.DataFrame([r.as_row() for r in results])
        if not df.empty:
            df = df.sort_values("slope_vs_education", ascending=True).reset_index(drop=True)
        return df

    # -- internals ----------------------------------------------------------
    def _analyze_code(self, info: CodeInfo, hh: pd.DataFrame, despesa_ind, despesa_col,
                      low_band: str, high_band: str) -> Optional[CodeResult]:
        c = self.config
        keys = list(c.uc_keys)
        per_uc = self.aggregator.aggregate_category(
            despesa_ind, despesa_col, [info.code], out_name="code_debt"
        ).select([*keys, "code_debt"]).to_pandas()

        data = hh.merge(per_uc, on=keys, how="left")
        data["code_debt"] = data["code_debt"].fillna(0.0)
        data = data[data["household_income"] > 0].copy()
        data["debt_to_income"] = data["code_debt"] / data["household_income"]

        n_with = int((data["code_debt"] > 0).sum())
        w = data["weight"].to_numpy()
        ratio = data["debt_to_income"].to_numpy()
        edu = data["education"].to_numpy()
        wmean_ratio = self._wmean(ratio, w)

        slope, slope_p, r = self._weighted_regression(edu, ratio, w)
        low = self._band_mean(data, low_band)
        high = self._band_mean(data, high_band)

        direction = self._direction(slope, slope_p, n_with)
        return CodeResult(
            code=info.code, label=info.label, category=info.category, active=info.active,
            n_with_spend=n_with, weighted_mean_ratio=wmean_ratio,
            slope=slope, slope_p=slope_p, corr_r=r, direction=direction,
            ratio_low_band=low, ratio_high_band=high,
        )

    @staticmethod
    def _wmean(values: np.ndarray, weights: np.ndarray) -> float:
        m = ~np.isnan(values) & ~np.isnan(weights) & (weights > 0)
        if not m.any():
            return float("nan")
        return float(np.average(values[m], weights=weights[m]))

    def _band_mean(self, data: pd.DataFrame, band: str) -> float:
        sub = data[data["education_band"] == band]
        if len(sub) == 0:
            return float("nan")
        return self._wmean(sub["debt_to_income"].to_numpy(), sub["weight"].to_numpy())

    @staticmethod
    def _weighted_regression(edu, ratio, w):
        """Weighted OLS slope of ratio on education + weighted Pearson r."""
        m = ~np.isnan(edu) & ~np.isnan(ratio) & ~np.isnan(w) & (w > 0)
        if m.sum() < 10 or np.nanstd(edu[m]) == 0 or np.nanstd(ratio[m]) == 0:
            return float("nan"), float("nan"), float("nan")
        x, y, ww = edu[m], ratio[m], w[m]
        # weighted least squares for slope + p-value via statsmodels
        try:
            import statsmodels.api as sm
            X = sm.add_constant(x)
            model = sm.WLS(y, X, weights=ww).fit()
            slope = float(model.params[1])
            slope_p = float(model.pvalues[1])
        except Exception:
            slope, slope_p = float("nan"), float("nan")
        # weighted Pearson correlation
        mx = np.average(x, weights=ww)
        my = np.average(y, weights=ww)
        cov = np.average((x - mx) * (y - my), weights=ww)
        vx = np.average((x - mx) ** 2, weights=ww)
        vy = np.average((y - my) ** 2, weights=ww)
        r = float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else float("nan")
        return slope, slope_p, r

    @staticmethod
    def _direction(slope: float, slope_p: float, n_with: int) -> str:
        if n_with == 0 or np.isnan(slope):
            return "no data"
        if not np.isnan(slope_p) and slope_p >= 0.05:
            return "flat / not significant"
        return "higher with education" if slope > 0 else "lower with education"


def write_reports(df: pd.DataFrame, config: AnalysisConfig, var_label: str) -> Dict[str, Path]:
    """Write the sorted CSV and a readable Markdown report. Returns the paths."""
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    stem = f"debt_by_code_vs_{var_label.lower()}"
    csv_path = config.outputs_dir / f"{stem}.csv"
    md_path = config.outputs_dir / f"{stem}.md"

    df.to_csv(csv_path, index=False)

    lower = df[df["direction"] == "lower with education"]
    higher = df[df["direction"] == "higher with education"]
    other = df[~df["direction"].isin(["lower with education", "higher with education"])]

    def _table(sub: pd.DataFrame) -> List[str]:
        if sub.empty:
            return ["_(none)_", ""]
        lines = [
            "| code | label | category | active | n UCs | slope | p | r | low-band | high-band |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for _, row in sub.iterrows():
            lines.append(
                f"| {row['code']} | {row['label']} | {row['category']} | "
                f"{'yes' if row['active'] else 'no'} | {int(row['n_ucs_with_spend'])} | "
                f"{row['slope_vs_education']:.3e} | {row['slope_p_value']:.3g} | "
                f"{row['weighted_corr_r']:.3f} | {row['ratio_lowest_edu_band']:.5f} | "
                f"{row['ratio_highest_edu_band']:.5f} |"
            )
        lines.append("")
        return lines

    md = [
        f"# Debt-to-income vs {var_label}: per-code analysis",
        "",
        f"Education measure: **{var_label}** "
        f"(aggregation: {config.education_method}; "
        f"filters: adults={config.filter_adults}, with-income={config.filter_with_income}).",
        "",
        "All statistics are **population-weighted** by PESO_FINAL. `slope` is the "
        "weighted-OLS coefficient of debt/income on the education value; a **negative "
        "slope means the debt is relatively higher for LOWER-education households**. "
        "`low-band`/`high-band` are the weighted mean debt/income in the lowest and "
        "highest education bands. Codes are sorted by slope.",
        "",
        "## Debts that are HIGHER for LOWER education (negative slope)",
        "",
        *_table(lower),
        "## Debts that are HIGHER for HIGHER education (positive slope)",
        "",
        *_table(higher),
        "## Flat / not significant / no data",
        "",
        *_table(other),
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"csv": csv_path, "md": md_path}

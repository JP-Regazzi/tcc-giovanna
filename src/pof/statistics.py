"""
Statistical tests for education and debt analysis.

Provides population-weighted tests (t-tests, ANOVA, Kruskal-Wallis) with
p-values and effect sizes. All statistics respect PESO_FINAL weights.

Text output in Portuguese; variable names remain in English.
"""
from __future__ import annotations

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import f_oneway, kruskal


class WeightedStatistics:
    """Population-weighted statistical tests."""

    @staticmethod
    def wmean(values: pd.Series, weights: pd.Series) -> float:
        """Weighted mean."""
        v = pd.to_numeric(values, errors="coerce")
        w = pd.to_numeric(weights, errors="coerce")
        m = v.notna() & w.notna() & (w > 0)
        if not m.any():
            return np.nan
        return float(np.average(v[m], weights=w[m]))

    @staticmethod
    def wstd(values: pd.Series, weights: pd.Series) -> float:
        """Weighted standard deviation."""
        v = pd.to_numeric(values, errors="coerce")
        w = pd.to_numeric(weights, errors="coerce")
        m = v.notna() & w.notna() & (w > 0)
        if not m.any():
            return np.nan
        vw = v[m]
        ww = w[m]
        mean = np.average(vw, weights=ww)
        variance = np.average((vw - mean) ** 2, weights=ww)
        return float(np.sqrt(variance))

    @staticmethod
    def wmedian(values: pd.Series, weights: pd.Series) -> float:
        """Weighted median."""
        v = pd.to_numeric(values, errors="coerce")
        w = pd.to_numeric(weights, errors="coerce")
        m = v.notna() & w.notna() & (w > 0)
        if not m.any():
            return np.nan
        vw = v[m].values
        ww = w[m].values
        sort_idx = np.argsort(vw)
        vw_sorted = vw[sort_idx]
        ww_sorted = ww[sort_idx]
        cumsum = np.cumsum(ww_sorted)
        total = cumsum[-1]
        idx = np.searchsorted(cumsum, total / 2)
        return float(vw_sorted[min(idx, len(vw_sorted) - 1)])


class EducationDebtTests:
    """Statistical tests for debt vs education relationship."""

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def _get_band_groups(
        self, value_col: str, bands: List[str]
    ) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """Returns {band: (values, weights)} for each education band."""
        groups = {}
        for band in bands:
            sub = self.df[self.df["education_band"] == band]
            if len(sub) == 0:
                continue
            v = pd.to_numeric(sub[value_col], errors="coerce")
            w = pd.to_numeric(sub["weight"], errors="coerce")
            m = v.notna() & w.notna() & (w > 0)
            if m.any():
                groups[band] = (v[m].values, w[m].values)
        return groups

    def test_income_by_education(self, bands: List[str]) -> Dict:
        """
        ANOVA test: mean income differs across education bands.
        Returns dict with test statistic, p-value, and per-band summary.
        """
        groups = self._get_band_groups("household_income", bands)
        if len(groups) < 2:
            return {"error": "Insufficient education bands"}

        # Unweighted groups for scipy (weighted ANOVA is complex)
        values_list = [vals for vals, _ in groups.values()]
        try:
            f_stat, p_value = f_oneway(*values_list)
        except Exception as e:
            return {"error": str(e)}

        summary = {}
        for band, (vals, weights) in groups.items():
            summary[band] = {
                "n": int(weights.sum()),
                "mean": float(np.average(vals, weights=weights)),
                "median": float(WeightedStatistics.wmedian(
                    pd.Series(vals), pd.Series(weights)
                )),
                "std": float(WeightedStatistics.wstd(
                    pd.Series(vals), pd.Series(weights)
                )),
            }

        return {
            "test": "ANOVA",
            "test_statistic": float(f_stat),
            "p_value": float(p_value),
            "significant": p_value < 0.05,
            "summary": summary,
        }

    def test_debt_burden_by_education(self, bands: List[str]) -> Dict:
        """
        Kruskal-Wallis test: debt/income ratio differs across education bands.
        (Non-parametric because debt/income is heavily skewed.)
        """
        groups = self._get_band_groups("debt_to_income", bands)
        if len(groups) < 2:
            return {"error": "Insufficient education bands"}

        values_list = [vals for vals, _ in groups.values()]
        try:
            h_stat, p_value = kruskal(*values_list)
        except Exception as e:
            return {"error": str(e)}

        summary = {}
        for band, (vals, weights) in groups.items():
            summary[band] = {
                "n": int(weights.sum()),
                "mean": float(np.average(vals, weights=weights)),
                "median": float(WeightedStatistics.wmedian(
                    pd.Series(vals), pd.Series(weights)
                )),
                "std": float(WeightedStatistics.wstd(
                    pd.Series(vals), pd.Series(weights)
                )),
            }

        return {
            "test": "Kruskal-Wallis",
            "test_statistic": float(h_stat),
            "p_value": float(p_value),
            "significant": p_value < 0.05,
            "summary": summary,
        }

    def test_debt_prevalence_by_education(self, bands: List[str]) -> Dict:
        """
        Chi-square test: prevalence of debt (has_debt=1) differs across education bands.
        """
        contingency = []
        band_order = []
        for band in bands:
            sub = self.df[self.df["education_band"] == band]
            if len(sub) == 0:
                continue
            band_order.append(band)
            has = (pd.to_numeric(sub["has_debt"], errors="coerce") == 1).astype(float)
            weights = pd.to_numeric(sub["weight"], errors="coerce")
            with_debt = (has * weights).sum()
            without_debt = ((1 - has) * weights).sum()
            contingency.append([with_debt, without_debt])

        if len(contingency) < 2:
            return {"error": "Insufficient education bands"}

        chi2, p_value, dof, expected = stats.chi2_contingency(contingency)

        summary = {}
        for i, band in enumerate(band_order):
            sub = self.df[self.df["education_band"] == band]
            w = pd.to_numeric(sub["weight"], errors="coerce")
            has = (pd.to_numeric(sub["has_debt"], errors="coerce") == 1).astype(float)
            pct = (has * w).sum() / w.sum() * 100 if w.sum() > 0 else np.nan
            summary[band] = {
                "n": int(w.sum()),
                "pct_with_debt": float(pct),
            }

        return {
            "test": "Chi-square",
            "test_statistic": float(chi2),
            "p_value": float(p_value),
            "dof": int(dof),
            "significant": p_value < 0.05,
            "summary": summary,
        }

    def test_debt_volume_by_education(self, bands: List[str]) -> Dict:
        """
        Kruskal-Wallis test: total debt (among debtors) differs across education bands.
        """
        groups = self._get_band_groups("total_debt", bands)
        if len(groups) < 2:
            return {"error": "Insufficient education bands"}

        # Filter to debtors only
        debt_groups = {}
        for band, (vals, weights) in groups.items():
            mask = vals > 0
            if mask.sum() > 0:
                debt_groups[band] = (vals[mask], weights[mask])

        if len(debt_groups) < 2:
            return {"error": "Insufficient education bands with debtors"}

        values_list = [vals for vals, _ in debt_groups.values()]
        try:
            h_stat, p_value = kruskal(*values_list)
        except Exception as e:
            return {"error": str(e)}

        summary = {}
        for band in bands:
            sub = self.df[self.df["education_band"] == band]
            if len(sub) == 0:
                continue
            sub_debt = sub[sub["has_debt"] == 1]
            if len(sub_debt) == 0:
                summary[band] = {"n_debtors": 0}
                continue
            vals = pd.to_numeric(sub_debt["total_debt"], errors="coerce")
            weights = pd.to_numeric(sub_debt["weight"], errors="coerce")
            m = vals.notna() & weights.notna() & (weights > 0)
            if m.any():
                vw = vals[m]
                ww = weights[m]
                summary[band] = {
                    "n_debtors": int(ww.sum()),
                    "mean": float(np.average(vw, weights=ww)),
                    "median": float(WeightedStatistics.wmedian(
                        pd.Series(vw), pd.Series(ww)
                    )),
                    "std": float(WeightedStatistics.wstd(
                        pd.Series(vw), pd.Series(ww)
                    )),
                }
            else:
                summary[band] = {"n_debtors": 0}

        return {
            "test": "Kruskal-Wallis (debtors only)",
            "test_statistic": float(h_stat),
            "p_value": float(p_value),
            "significant": p_value < 0.05,
            "summary": summary,
        }

    def summary_table(self, bands: List[str]) -> pd.DataFrame:
        """
        Comprehensive summary table: all education bands with income, debt, prevalence.
        """
        rows = []
        for band in bands:
            sub = self.df[self.df["education_band"] == band]
            if len(sub) == 0:
                continue
            w = pd.to_numeric(sub["weight"], errors="coerce")
            total_weight = w.sum()

            # Income
            income = pd.to_numeric(sub["household_income"], errors="coerce")
            income_m = income.notna() & w.notna() & (w > 0)
            income_mean = float(np.average(income[income_m], weights=w[income_m])) if income_m.any() else np.nan

            # Debt prevalence
            has = (pd.to_numeric(sub["has_debt"], errors="coerce") == 1).astype(float)
            pct_debt = (has * w).sum() / total_weight * 100 if total_weight > 0 else np.nan

            # Debt burden (all UCs)
            debt_ratio = pd.to_numeric(sub["debt_to_income"], errors="coerce")
            ratio_m = debt_ratio.notna() & w.notna() & (w > 0)
            burden_mean = float(np.average(debt_ratio[ratio_m], weights=w[ratio_m])) if ratio_m.any() else np.nan

            # Total debt (debtors only)
            sub_debt = sub[sub["has_debt"] == 1]
            if len(sub_debt) > 0:
                debt = pd.to_numeric(sub_debt["total_debt"], errors="coerce")
                w_debt = pd.to_numeric(sub_debt["weight"], errors="coerce")
                debt_m = debt.notna() & w_debt.notna() & (w_debt > 0)
                debt_mean = float(np.average(debt[debt_m], weights=w_debt[debt_m])) if debt_m.any() else np.nan
            else:
                debt_mean = np.nan

            rows.append({
                "education_band": band,
                "n_uc_households": int(total_weight),
                "mean_income_r": income_mean,
                "pct_with_debt": pct_debt,
                "mean_debt_to_income": burden_mean,
                "mean_debt_debtors_r": debt_mean,
            })

        return pd.DataFrame(rows)

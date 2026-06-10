"""
Descriptive figures for the thesis.

Every method returns a matplotlib Figure AND (optionally) saves it as a PNG into
``config.figures_dir``. The notebook calls these and lets Jupyter display the
returned figure inline, so the same code produces both the saved artefact and the
in-notebook view — no duplicated plotting logic.

All statistics shown are population-weighted by PESO_FINAL: bar heights are
weighted means / weighted shares, computed with the helpers in this module so the
descriptive figures match the modelling assumptions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import AnalysisConfig


class DescriptivePlots:
    """Produces and saves the descriptive figures."""

    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.config.figures_dir.mkdir(parents=True, exist_ok=True)

    # -- helpers ------------------------------------------------------------
    def _save(self, fig: matplotlib.figure.Figure, filename: str) -> Path:
        path = self.config.figures_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight")
        return path

    @staticmethod
    def _wmean(values: pd.Series, weights: pd.Series) -> float:
        v = pd.to_numeric(values, errors="coerce")
        w = pd.to_numeric(weights, errors="coerce")
        m = v.notna() & w.notna() & (w > 0)
        if not m.any():
            return float("nan")
        return float(np.average(v[m], weights=w[m]))

    def _by_band(self, df: pd.DataFrame, value_col: str) -> pd.Series:
        """Weighted mean of ``value_col`` per education band, ordered."""
        out = {}
        for band in self.config.education_labels:
            sub = df[df["education_band"] == band]
            out[band] = self._wmean(sub[value_col], sub["weight"]) if len(sub) else np.nan
        return pd.Series(out)

    def _share_with_debt(self, df: pd.DataFrame) -> pd.Series:
        out = {}
        for band in self.config.education_labels:
            sub = df[df["education_band"] == band]
            out[band] = self._wmean(sub["has_debt"], sub["weight"]) * 100 if len(sub) else np.nan
        return pd.Series(out)

    # -- figures ------------------------------------------------------------
    def debt_burden_by_education(self, df: pd.DataFrame, save: bool = True) -> matplotlib.figure.Figure:
        """2x2 panel: debt/income, % with debt, mean income, mean abs debt — by band."""
        ratio = self._by_band(df, "debt_to_income")
        share = self._share_with_debt(df)
        income = self._by_band(df, "household_income")
        absdebt = self._by_band(df, "total_debt")

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("Education and household debt (population-weighted)", fontweight="bold")

        panels = [
            (axes[0, 0], ratio, "Mean debt-to-income ratio", "#4C72B0"),
            (axes[0, 1], share, "% of households with any debt", "#C44E52"),
            (axes[1, 0], income, "Mean monthly income (R$)", "#55A868"),
            (axes[1, 1], absdebt, "Mean annual debt service (R$)", "#DD8452"),
        ]
        for ax, series, title, color in panels:
            series.plot(kind="bar", ax=ax, color=color, edgecolor="black", alpha=0.85)
            ax.set_title(title, fontsize=11)
            ax.set_xlabel("")
            ax.tick_params(axis="x", rotation=20)
            ax.grid(axis="y", alpha=0.3)

        fig.tight_layout()
        if save:
            self._save(fig, "debt_burden_by_education.png")
        return fig

    def education_distribution(self, df: pd.DataFrame, save: bool = True) -> matplotlib.figure.Figure:
        """Weighted distribution of UCs across the schooling aggregation methods."""
        methods = {
            "education_min": "min",
            "education_median": "median",
            "education_mode": "mode",
            "education_mean": "mean",
            "education_max": "max",
        }
        fig, axes = plt.subplots(1, len(methods), figsize=(18, 4), sharey=True)
        fig.suptitle("Distribution of households by years of schooling, per aggregation method "
                     "(weighted)", fontweight="bold")
        for ax, (col, label) in zip(axes, methods.items()):
            vals = pd.to_numeric(df[col], errors="coerce")
            w = pd.to_numeric(df["weight"], errors="coerce")
            tmp = pd.DataFrame({"v": vals, "w": w}).dropna()
            counts = tmp.groupby("v")["w"].sum().sort_index()
            counts.plot(kind="bar", ax=ax, color="#4C72B0", edgecolor="black", alpha=0.8)
            ax.set_title(label)
            ax.set_xlabel("Years of schooling")
            ax.tick_params(axis="x", rotation=0)
            ax.grid(axis="y", alpha=0.3)
        axes[0].set_ylabel("Weighted households")
        fig.tight_layout()
        if save:
            self._save(fig, "education_distribution.png")
        return fig

    def debt_by_category(self, df: pd.DataFrame, save: bool = True) -> matplotlib.figure.Figure:
        """Weighted share of households spending in each debt category."""
        rows = []
        for key, cat in self.config.debt_categories.items():
            col = f"debt_{key}"
            if col not in df.columns:
                continue
            has = (pd.to_numeric(df[col], errors="coerce") > 0).astype(float)
            share = self._wmean(has, df["weight"]) * 100
            rows.append((cat.label, share))
        s = pd.Series(dict(rows))

        fig, ax = plt.subplots(figsize=(9, 5))
        s.plot(kind="barh", ax=ax, color="#937860", edgecolor="black", alpha=0.85)
        ax.set_title("% of households with spending, by debt category (weighted)",
                     fontweight="bold")
        ax.set_xlabel("% of households")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        if save:
            self._save(fig, "debt_by_category.png")
        return fig

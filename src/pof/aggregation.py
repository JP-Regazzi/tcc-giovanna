"""
Aggregate person-level records (MORADOR) up to the consumption unit (UC).

A UC ("unidade de consumo") is the group of people sharing a dwelling and its
expenses -- effectively the surveyed household, keyed by
(COD_UPA, NUM_DOM, NUM_UC).

What is parametrized (via AnalysisConfig)
-----------------------------------------
- education_variable : "ANOS_ESTUDO" (years) or "NIVEL_INSTRUCAO" (ordinal level).
- education_method   : which aggregation becomes the headline `education` column
                       (mean / median / mode / min / max). All five are computed
                       and exposed as education_<method>; `education` points at the
                       configured one.
- filter_adults      : keep only members with age >= adult_min_age (V0403).
- filter_with_income : keep only members who had income/work (V0407 == 1).

The education/age statistics are POPULATION-WEIGHTED by PESO_FINAL and computed
fully vectorized in Polars (no per-group Python loop), so a full build is ~1s and
the per-code analysis can rebuild the dataset for several configurations cheaply.

Other decisions
---------------
- Head of household: V0306 == "01" (explicit), not row order.
- Household income (RENDA_TOTAL): identical for every UC member (verified), so we
  take the head's value. A mean would be wrong; a sum would double-count.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from .config import AnalysisConfig


def _weighted_median_from_lists(s) -> float:
    """
    Weighted median with linear interpolation -- the standard survey definition,
    identical to weights.weighted_median: interpolate the value at cumulative
    probability 0.5, where each order statistic sits at
    (cum_weight_inclusive - 0.5*weight) / total_weight.

    Inputs are per-group sorted values (_v), inclusive cumulative weights (_cw) and
    total weight (_tw).
    """
    v = s["_v"]
    cw = s["_cw"]
    total = s["_tw"]
    if total is None or total == 0 or v is None or len(v) == 0:
        return float("nan")
    values = np.asarray(v, dtype="float64")
    cum_inclusive = np.asarray(cw, dtype="float64")
    weights = np.empty_like(cum_inclusive)
    weights[0] = cum_inclusive[0]
    if len(cum_inclusive) > 1:
        weights[1:] = np.diff(cum_inclusive)
    pos = (cum_inclusive - 0.5 * weights) / total
    return float(np.interp(0.5, pos, values))


class HouseholdBuilder:
    """Builds UC-level education / demographic tables from MORADOR."""

    def __init__(self, config: AnalysisConfig):
        self.config = config

    # -- public API ---------------------------------------------------------
    def build(self, morador: pl.DataFrame) -> pl.DataFrame:
        c = self.config
        df = self._normalize_weight(morador)
        pop = self._restrict_population(df)
        education = self._weighted_education_stats(pop)
        head = self._head_and_income(df)
        out = education.join(head, on=list(c.uc_keys), how="inner")
        out = out.with_columns(pl.col(c.education_output_column()).alias("education"))
        return out

    # -- internals ----------------------------------------------------------
    def _normalize_weight(self, df: pl.DataFrame) -> pl.DataFrame:
        """Guarantee PESO_FINAL is on its true scale (undo a stale 1e8 over-division)."""
        c = self.config
        w = pl.col(c.col_weight).cast(pl.Float64)
        median_w = df.select(w.median()).item()
        if median_w is not None and median_w < 1.0:
            return df.with_columns((w * 1e8).alias(c.col_weight))
        return df.with_columns(w.alias(c.col_weight))

    def _restrict_population(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply the configurable adult / income member filters."""
        c = self.config
        conditions = []
        if c.filter_adults:
            conditions.append(pl.col(c.col_age).cast(pl.Float64) >= c.adult_min_age)
        if c.filter_with_income:
            conditions.append(pl.col(c.col_had_income).cast(pl.Float64) == 1)
        if not conditions:
            return df
        mask = conditions[0]
        for cond in conditions[1:]:
            mask = mask & cond
        return df.filter(mask)

    def _weighted_education_stats(self, pop: pl.DataFrame) -> pl.DataFrame:
        """Per-UC weighted education (all 5 methods) + age (mean/median), vectorized."""
        c = self.config
        keys = list(c.uc_keys)
        edu_col = c.education_source_column()

        df = pop.select(
            [*keys, c.col_uf, edu_col, c.col_age, c.col_weight]
        ).with_columns([
            pl.col(edu_col).cast(pl.Float64),
            pl.col(c.col_age).cast(pl.Float64),
            pl.col(c.col_weight).cast(pl.Float64),
        ]).drop_nulls(subset=[edu_col])

        education_cols = self._weighted_value_stats(df, keys, edu_col, "education")
        age_cols = self._weighted_value_stats(
            df, keys, c.col_age, "age", methods=("mean", "median")
        )
        meta = df.group_by(keys).agg([
            pl.col(c.col_uf).first().alias(c.col_uf),
            pl.len().alias("n_members_aggregated"),
        ])

        out = (
            meta
            .join(education_cols, on=keys, how="inner")
            .join(age_cols, on=keys, how="inner")
        )
        round_cols = [
            "education_min", "education_max", "education_mean", "education_median",
            "education_mode", "age_mean", "age_median",
        ]
        out = out.with_columns([
            pl.col(col).round().cast(pl.Int64) for col in round_cols if col in out.columns
        ])
        return out

    def _weighted_value_stats(self, df: pl.DataFrame, keys, value_col: str,
                              prefix: str,
                              methods=("min", "max", "mean", "median", "mode")) -> pl.DataFrame:
        """Per-group weighted statistics for one value column, returned wide."""
        c = self.config
        w = pl.col(c.col_weight)
        v = pl.col(value_col)

        aggs = []
        if "min" in methods:
            aggs.append(v.min().alias(f"{prefix}_min"))
        if "max" in methods:
            aggs.append(v.max().alias(f"{prefix}_max"))
        if "mean" in methods:
            aggs.append(((v * w).sum() / w.sum()).alias(f"{prefix}_mean"))
        base = df.group_by(keys).agg(aggs) if aggs else df.select(keys).unique()

        if "median" in methods:
            med = (
                df.sort(value_col)
                .group_by(keys, maintain_order=True)
                .agg([pl.col(value_col).alias("_v"), w.alias("_w")])
                .with_columns([
                    pl.col("_w").list.eval(pl.element().cum_sum()).alias("_cw"),
                    pl.col("_w").list.sum().alias("_tw"),
                ])
                .with_columns(
                    pl.struct(["_v", "_cw", "_tw"]).map_elements(
                        _weighted_median_from_lists, return_dtype=pl.Float64
                    ).alias(f"{prefix}_median")
                )
                .select([*keys, f"{prefix}_median"])
            )
            base = base.join(med, on=keys, how="left")

        if "mode" in methods:
            mode = (
                df.group_by([*keys, value_col]).agg(w.sum().alias("_tw"))
                .sort(
                    [*keys, "_tw", value_col],
                    descending=[False] * len(keys) + [True, False],
                )
                .group_by(keys, maintain_order=True)
                .agg(pl.col(value_col).first().alias(f"{prefix}_mode"))
            )
            base = base.join(mode, on=keys, how="left")

        return base

    def _head_and_income(self, df: pl.DataFrame) -> pl.DataFrame:
        """Head-of-household sex + UC income + UC weight, one row per UC."""
        c = self.config
        head_rows = df.filter(
            pl.col(c.col_uc_role).str.strip_chars() == c.head_role_code
        )
        return head_rows.group_by(list(c.uc_keys)).agg(
            pl.col(c.col_sex).first().alias("head_sex"),
            pl.col(c.col_household_income).cast(pl.Float64).first().alias("household_income"),
            pl.col(c.col_weight).cast(pl.Float64).first().alias("weight"),
        )

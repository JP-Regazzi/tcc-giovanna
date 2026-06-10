"""
Aggregate person-level records (MORADOR) up to the consumption unit (UC).

A UC ("unidade de consumo") is the group of people sharing a dwelling and its
expenses — effectively the surveyed household. It is keyed by
(COD_UPA, NUM_DOM, NUM_UC).

Design decisions (and why)
--------------------------
- Years of schooling (ANOS_ESTUDO): we expose several aggregation methods
  (min / median / mean / max / weighted-mode). The thesis uses the MEAN over
  adults-with-income as the headline measure, because the correlation analysis
  showed it has the strongest link to income. All methods are population-WEIGHTED
  by PESO_FINAL where a weighted definition exists.
- Schooling level (NIVEL_INSTRUCAO): ordinal 1..7, so the MEAN is not meaningful;
  we report the weighted MODE (and median) as the representative level.
- Head of household: taken from the record with V0306 == "01" (explicit), not by
  relying on row order. (We verified the first row per UC is always the head, but
  filtering on the role code is self-documenting and robust.)
- Household income (RENDA_TOTAL): identical for every member of the UC, so we
  take the head's value (first). A mean would be wrong.
- Sample restriction "adults with income": V0403 >= 18 AND V0407 == 1. This is the
  population whose schooling plausibly shaped the household's earning/credit
  capacity.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd
import polars as pl

from .config import AnalysisConfig
from . import weights as wstats


class HouseholdBuilder:
    """Builds UC-level schooling / demographic tables from MORADOR."""

    def __init__(self, config: AnalysisConfig):
        self.config = config

    # -- public API ---------------------------------------------------------
    def build(self, morador: pl.DataFrame, adults_with_income_only: bool | None = None) -> pl.DataFrame:
        """
        Return one row per UC with weighted schooling, demographic and income
        columns. If ``adults_with_income_only`` is True the schooling/age
        aggregations use only members with V0403>=18 and V0407==1.
        """
        if adults_with_income_only is None:
            adults_with_income_only = self.config.adults_with_income_only

        c = self.config
        df = self._normalize_weight(morador)

        # population used for schooling/age aggregation
        pop = df
        if adults_with_income_only:
            pop = df.filter(
                (pl.col(c.col_age).cast(pl.Float64) >= c.adult_min_age)
                & (pl.col(c.col_had_income).cast(pl.Float64) == 1)
            )

        schooling = self._weighted_group_stats(pop)
        head = self._head_and_income(df)

        return schooling.join(head, on=list(c.uc_keys), how="inner")

    # -- internals ----------------------------------------------------------
    def _normalize_weight(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Guarantee PESO_FINAL is on its true scale regardless of how the parquet
        cache was produced. The genuine per-person weight is on the order of
        hundreds; if the cached file still has it divided by 1e8 (values < 0.01),
        we multiply it back.
        """
        c = self.config
        w = pl.col(c.col_weight).cast(pl.Float64)
        median_w = df.select(w.median()).item()
        if median_w is not None and median_w < 1.0:
            df = df.with_columns((w * 1e8).alias(c.col_weight))
        else:
            df = df.with_columns(w.alias(c.col_weight))
        return df

    def _weighted_group_stats(self, pop: pl.DataFrame) -> pl.DataFrame:
        """Per-UC weighted schooling/level/age statistics via pandas groupby-apply."""
        c = self.config
        cols = [
            *c.uc_keys, c.col_uf,
            c.col_years_study, c.col_instruction, c.col_age, c.col_weight,
        ]
        pdf = pop.select(cols).to_pandas()
        for col in (c.col_years_study, c.col_instruction, c.col_age, c.col_weight):
            pdf[col] = pd.to_numeric(pdf[col], errors="coerce")

        records: List[Dict] = []
        for keys, g in pdf.groupby(list(c.uc_keys), sort=False):
            w = g[c.col_weight].to_numpy()
            study = g[c.col_years_study].to_numpy()
            level = g[c.col_instruction].to_numpy()
            age = g[c.col_age].to_numpy()
            rec = dict(zip(c.uc_keys, keys if isinstance(keys, tuple) else (keys,)))
            rec[c.col_uf] = g[c.col_uf].iloc[0]
            # schooling (years) — every method, weighted where defined
            rec["education_min"] = np.nanmin(study) if len(study) else np.nan
            rec["education_max"] = np.nanmax(study) if len(study) else np.nan
            rec["education_mean"] = wstats.weighted_mean(study, w)
            rec["education_median"] = wstats.weighted_median(study, w)
            rec["education_mode"] = wstats.weighted_mode(study, w)
            # schooling level (ordinal) — mode/median only
            rec["instruction_mode"] = wstats.weighted_mode(level, w)
            rec["instruction_median"] = wstats.weighted_median(level, w)
            # age — weighted mean/median for life-cycle control
            rec["age_mean"] = wstats.weighted_mean(age, w)
            rec["age_median"] = wstats.weighted_median(age, w)
            rec["n_members_aggregated"] = int(np.sum(~np.isnan(study)))
            records.append(rec)

        out = pd.DataFrame.from_records(records)
        # round the integer-scale schooling/level/age columns for readability
        for col in ["education_min", "education_max", "education_mean", "education_median",
                    "education_mode", "instruction_mode", "instruction_median",
                    "age_mean", "age_median"]:
            out[col] = out[col].round().astype("Int64")
        return pl.from_pandas(out)

    def _head_and_income(self, df: pl.DataFrame) -> pl.DataFrame:
        """Head-of-household sex + UC income + UC weight, one row per UC."""
        c = self.config
        head_rows = df.filter(pl.col(c.col_uc_role).str.strip_chars() == c.head_role_code)
        return head_rows.group_by(list(c.uc_keys)).agg(
            pl.col(c.col_sex).first().alias("head_sex"),
            pl.col(c.col_household_income).cast(pl.Float64).first().alias("household_income"),
            pl.col(c.col_weight).cast(pl.Float64).first().alias("weight"),
        )

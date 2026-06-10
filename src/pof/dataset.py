"""
Orchestrate the analytical dataset: persons + debt -> one row per UC.

This is the single place that decides what the final modelling table looks like.
It joins the weighted household table (aggregation.HouseholdBuilder) with every
debt category (debt.DebtAggregator), then builds the derived variables the thesis
relies on:

  - total_debt                : annual deflated debt-service spending (R$)
  - debt_<category>           : same, split by economic function
  - debt_to_income            : total_debt / household_income  (relative burden)
  - has_debt                  : 1 if total_debt > 0             (access to credit)
  - log_debt                  : log(total_debt) for UCs with debt (volume model)
  - log_income                : log(household_income)
  - head_is_woman             : 1 if head_sex == "2"
  - education_band            : categorical schooling band (for descriptive splits)

Why debt/income and not absolute debt? More-educated families earn more and can
service larger nominal debts; the economically meaningful question is what SHARE
of income goes to debt service. debt_to_income is therefore the central variable.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from .config import AnalysisConfig
from .aggregation import HouseholdBuilder
from .debt import DebtAggregator


class AnalyticalDataset:
    """Builds (and holds) the final UC-level analytical table."""

    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.household_builder = HouseholdBuilder(config)
        self.debt_aggregator = DebtAggregator(config)

    def build(self, tables: dict) -> pl.DataFrame:
        """``tables`` is the dict returned by io.PofReader.load_all()."""
        c = self.config
        morador = tables["MORADOR"]
        despesa_ind = tables["DESPESA_INDIVIDUAL"]
        despesa_col = tables["DESPESA_COLETIVA"]

        households = self.household_builder.build(morador)
        debt_frames = self.debt_aggregator.aggregate_all_categories(despesa_ind, despesa_col)

        df = households
        # attach total debt
        total = debt_frames["total"].select([*c.uc_keys, "total_debt"])
        df = df.join(total, on=list(c.uc_keys), how="left")
        # attach each category's debt column
        for key in c.debt_categories:
            col = f"debt_{key}"
            frame = debt_frames[key]
            if col in frame.columns:
                df = df.join(frame.select([*c.uc_keys, col]), on=list(c.uc_keys), how="left")
            else:
                df = df.with_columns(pl.lit(0.0).alias(col))

        # fill debt nulls (UCs with no debt rows) with 0
        debt_cols = ["total_debt"] + [f"debt_{k}" for k in c.debt_categories]
        df = df.with_columns([pl.col(x).fill_null(0.0) for x in debt_cols])

        df = self._quality_filter(df)
        df = self._derived_variables(df)
        return df

    # -- internals ----------------------------------------------------------
    def _quality_filter(self, df: pl.DataFrame) -> pl.DataFrame:
        """Drop UCs with non-positive income (missing/erroneous, not poverty)."""
        if self.config.drop_zero_income:
            df = df.filter(pl.col("household_income") > 0)
        return df

    def _derived_variables(self, df: pl.DataFrame) -> pl.DataFrame:
        c = self.config
        df = df.with_columns([
            (pl.col("total_debt") / pl.col("household_income")).alias("debt_to_income"),
            (pl.col("total_debt") > 0).cast(pl.Int8).alias("has_debt"),
            pl.when(pl.col("total_debt") > 0)
              .then(pl.col("total_debt").log())
              .otherwise(None)
              .alias("log_debt"),
            pl.col("household_income").log().alias("log_income"),
            (pl.col("head_sex").str.strip_chars() == "2").cast(pl.Int8).alias("head_is_woman"),
        ])
        # education band, using bins appropriate for the configured education
        # variable (ANOS_ESTUDO years vs NIVEL_INSTRUCAO ordinal levels) and the
        # headline `education` column (= the configured aggregation method).
        bins, labels = c.education_band_spec()
        df = df.with_columns(
            pl.col("education").cut(
                breaks=bins[1:-1],
                labels=labels,
            ).alias("education_band")
        )
        return df

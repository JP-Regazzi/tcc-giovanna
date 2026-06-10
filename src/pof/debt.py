"""
Build household debt-service spending per UC, by economic category.

Canonical value
---------------
For every expenditure row classified as debt we compute

    value = V8000_DEFLA * FATOR_ANUALIZACAO          (config-controlled)

  - V8000_DEFLA  : nominal value already deflated to the survey's common price
                   reference (the dictionary says this is the column to use for
                   point estimates).
  - FATOR_ANUALIZACAO : 1 / 4 / 12 / 52, turns the reference-period value into an
                   ANNUAL figure. Different questionnaire blocks use different
                   reference periods, so without this we would add monthly and
                   annual reais together — economically meaningless.

Rows whose nominal V8000 equals the "ignored value" sentinel (9999999.99, read as
99999.9999 with two implicit decimals) are dropped before aggregation.

The result is summed over DESPESA_INDIVIDUAL + DESPESA_COLETIVA per UC.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

import polars as pl

from .config import AnalysisConfig, DebtCategory


class DebtAggregator:
    """Aggregates debt-service spending per UC for one or many categories."""

    def __init__(self, config: AnalysisConfig):
        self.config = config

    # -- public API ---------------------------------------------------------
    def aggregate_category(
        self,
        despesa_individual: pl.DataFrame,
        despesa_coletiva: pl.DataFrame,
        codes: Iterable[str],
        out_name: str = "debt_value",
    ) -> pl.DataFrame:
        """Return per-UC summed debt value (annual, deflated R$) for ``codes``."""
        codes = list(codes)
        ind = self._sum_one_table(despesa_individual, codes, "debt_individual")
        col = self._sum_one_table(despesa_coletiva, codes, "debt_collective")

        merged = (
            ind.join(col, on=list(self.config.uc_keys), how="outer", coalesce=True)
            .with_columns(
                pl.col("debt_individual").fill_null(0.0),
                pl.col("debt_collective").fill_null(0.0),
            )
            .with_columns(
                (pl.col("debt_individual") + pl.col("debt_collective")).alias(out_name)
            )
        )
        return merged

    def aggregate_total(
        self, despesa_individual: pl.DataFrame, despesa_coletiva: pl.DataFrame
    ) -> pl.DataFrame:
        """Per-UC total debt across ALL configured debt codes."""
        return self.aggregate_category(
            despesa_individual, despesa_coletiva,
            self.config.all_debt_codes(), out_name="total_debt",
        )

    def aggregate_all_categories(
        self, despesa_individual: pl.DataFrame, despesa_coletiva: pl.DataFrame
    ) -> Dict[str, pl.DataFrame]:
        """
        Mapping {category_key: per-UC frame with column ``debt_<key>``} plus a
        "total_debt" entry covering all codes. Empty categories yield an empty
        frame (the dataset builder fills those UCs with 0).
        """
        result: Dict[str, pl.DataFrame] = {}
        for key, cat in self.config.debt_categories.items():
            col_name = f"debt_{key}"
            result[key] = self.aggregate_category(
                despesa_individual, despesa_coletiva, cat.code_list, out_name=col_name
            )
        result["total"] = self.aggregate_total(despesa_individual, despesa_coletiva)
        return result

    # -- internals ----------------------------------------------------------
    def _value_expr(self) -> pl.Expr:
        c = self.config
        base = pl.col(c.col_value_deflated if c.use_deflated_value else c.col_value_nominal)
        value = base.cast(pl.Float64)
        if c.annualize:
            value = value * pl.col(c.col_annualization).cast(pl.Float64, strict=False).fill_null(1.0)
        return value

    def _sum_one_table(self, table: pl.DataFrame, codes: List[str], out_name: str) -> pl.DataFrame:
        c = self.config
        keys = list(c.uc_keys)
        if table is None or table.height == 0 or not codes:
            schema = {k: pl.Utf8 for k in keys}
            schema[out_name] = pl.Float64
            return pl.DataFrame(schema=schema)

        rows = (
            table
            .filter(pl.col(c.col_product).is_in(codes))
            .filter(pl.col(c.col_value_nominal).cast(pl.Float64) < c.value_sentinel)
        )
        if rows.height == 0:
            schema = {k: pl.Utf8 for k in keys}
            schema[out_name] = pl.Float64
            return pl.DataFrame(schema=schema)

        return rows.group_by(keys).agg(self._value_expr().sum().alias(out_name))

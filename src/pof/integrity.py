"""
Join-integrity checks for the UC (consumption-unit) key.

The analytical dataset joins three POF sources on (COD_UPA, NUM_DOM, NUM_UC):
MORADOR (people), DESPESA_INDIVIDUAL and DESPESA_COLETIVA (expenditures). If the
key does not line up, debt would be attached to the wrong household.

A useful, *valid* cross-check uses RENDA_TOTAL. EMPIRICAL FINDING (verified on the
full extract, documented in docs/01):

  - RENDA_TOTAL is the **UC monthly total**, identical for every member / every
    expenditure row of a UC, in ALL THREE sources -- including DESPESA_INDIVIDUAL
    (it is NOT the individual person's income there; it is just repeated per row).
  - Therefore the per-UC RENDA_TOTAL must be **constant within each UC** and
    **equal across the three sources** for the same UC key.

  - Consequently, SUMMING RENDA_TOTAL across rows/people is meaningless -- it
    multiplies the UC income by the number of rows and double-counts. We expose
    that sum only to demonstrate the trap, never to use it.

This module reports, per source: whether RENDA_TOTAL is constant within each UC,
and whether the per-UC value agrees across sources, plus orphan-key counts. It
returns a structured report and raises (optionally) if a hard check fails.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import polars as pl

from .config import AnalysisConfig


@dataclass
class IntegrityReport:
    """Structured result of the RENDA_TOTAL / join-key checks."""

    checks: Dict[str, bool] = field(default_factory=dict)
    details: Dict[str, object] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())

    def summary_lines(self) -> List[str]:
        lines = ["RENDA_TOTAL / join-key integrity report", "=" * 42]
        for name, ok in self.checks.items():
            lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        lines.append("")
        for k, v in self.details.items():
            lines.append(f"  - {k}: {v}")
        lines.append("")
        lines.append(f"OVERALL: {'PASS' if self.passed else 'FAIL'}")
        return lines

    def __str__(self) -> str:
        return "\n".join(self.summary_lines())


class JoinIntegrityChecker:
    """Validates the UC key alignment of MORADOR / DESPESA_* via RENDA_TOTAL."""

    def __init__(self, config: AnalysisConfig, tolerance: float = 0.01):
        self.config = config
        self.tolerance = tolerance

    def check(self, tables: Dict[str, pl.DataFrame]) -> IntegrityReport:
        c = self.config
        keys = list(c.uc_keys)
        income = c.col_household_income

        mor = tables["MORADOR"]
        ind = tables["DESPESA_INDIVIDUAL"]
        col = tables["DESPESA_COLETIVA"]

        report = IntegrityReport()

        # 1) RENDA_TOTAL constant within each UC, per source
        for name, df in [("MORADOR", mor), ("DESPESA_INDIVIDUAL", ind), ("DESPESA_COLETIVA", col)]:
            varying = (
                df.group_by(keys)
                .agg(pl.col(income).cast(pl.Float64).n_unique().alias("nu"))
                .filter(pl.col("nu") > 1)
                .height
            )
            report.checks[f"{name}: RENDA_TOTAL constant within each UC"] = (varying == 0)
            report.details[f"{name}: UCs where RENDA_TOTAL varies within UC"] = varying

        # 2) per-UC RENDA_TOTAL agrees across the three sources
        def per_uc(df, alias):
            return df.group_by(keys).agg(
                pl.col(income).cast(pl.Float64).first().alias(alias)
            )

        m1 = per_uc(mor, "rt_mor")
        i1 = per_uc(ind, "rt_ind")
        c1 = per_uc(col, "rt_col")
        joined = m1.join(i1, on=keys, how="inner").join(c1, on=keys, how="inner")
        joined = joined.with_columns([
            (pl.col("rt_mor") - pl.col("rt_ind")).abs().alias("d_mi"),
            (pl.col("rt_mor") - pl.col("rt_col")).abs().alias("d_mc"),
        ])
        mism_mi = joined.filter(pl.col("d_mi") > self.tolerance).height
        mism_mc = joined.filter(pl.col("d_mc") > self.tolerance).height
        report.checks["RENDA_TOTAL agrees MORADOR vs DESPESA_INDIVIDUAL"] = (mism_mi == 0)
        report.checks["RENDA_TOTAL agrees MORADOR vs DESPESA_COLETIVA"] = (mism_mc == 0)
        report.details["UCs shared by all 3 sources"] = joined.height
        report.details["mismatches MORADOR vs DESPESA_INDIVIDUAL"] = mism_mi
        report.details["mismatches MORADOR vs DESPESA_COLETIVA"] = mism_mc

        # 3) orphan keys: expenditure UCs with no MORADOR record (would lose people)
        mor_keys = mor.select(keys).unique()
        ind_keys = ind.select(keys).unique()
        col_keys = col.select(keys).unique()
        orphan_ind = ind_keys.join(mor_keys, on=keys, how="anti").height
        orphan_col = col_keys.join(mor_keys, on=keys, how="anti").height
        report.checks["every DESPESA_INDIVIDUAL UC exists in MORADOR"] = (orphan_ind == 0)
        report.checks["every DESPESA_COLETIVA UC exists in MORADOR"] = (orphan_col == 0)
        report.details["orphan UCs in DESPESA_INDIVIDUAL (not in MORADOR)"] = orphan_ind
        report.details["orphan UCs in DESPESA_COLETIVA (not in MORADOR)"] = orphan_col

        # 4) demonstrate (do NOT use) the double-counting trap of summing RENDA_TOTAL
        true_total = mor.group_by(keys).agg(
            pl.col(income).cast(pl.Float64).first()
        ).select(pl.col(income).sum()).item()
        naive_sum_ind = ind.select(pl.col(income).cast(pl.Float64).sum()).item()
        report.details["correct sum of per-UC income (MORADOR, R$)"] = round(true_total, 2)
        report.details["NAIVE row-sum of RENDA_TOTAL in DESPESA_INDIVIDUAL (R$, double-counts!)"] = round(naive_sum_ind, 2)
        report.details["=> naive/correct ratio (should be >> 1, proving the trap)"] = (
            round(naive_sum_ind / true_total, 1) if true_total else None
        )

        return report

    def check_and_report(self, tables, save_to=None, raise_on_fail=False) -> IntegrityReport:
        report = self.check(tables)
        text = str(report)
        print(text)
        if save_to is not None:
            from pathlib import Path
            Path(save_to).parent.mkdir(parents=True, exist_ok=True)
            Path(save_to).write_text(text, encoding="utf-8")
        if raise_on_fail and not report.passed:
            raise AssertionError("Join-integrity check FAILED:\n" + text)
        return report

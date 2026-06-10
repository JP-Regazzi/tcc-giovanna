"""
POF 2017-2018 -- Education and Household Debt analysis package.

A small, SOLID, parametrized toolkit that turns the raw IBGE POF microdata into
the analytical dataset and econometric results used in the thesis (TCC).

The notebook is meant to stay *thin*: it only imports and calls the classes and
functions defined here. No data transformation logic should live in the notebook.

Public surface
--------------
- config.AnalysisConfig          : all tunable parameters (paths, filters, options)
- config.DEBT_CATEGORIES         : the debt taxonomy (English, by economic function)
- io.PofReader                   : reads the fixed-width TXT / Parquet via the dictionary
- aggregation.HouseholdBuilder   : aggregates persons -> consumption units (UCs), weighted
- debt.DebtAggregator            : builds deflated + annualized debt per UC, by category
- dataset.AnalyticalDataset      : orchestrates reader + builders into the final table
- models.DebtModels              : two-part + ratio regressions
- plots.DescriptivePlots         : descriptive figures (saved as PNG and/or shown inline)
- integrity.JoinIntegrityChecker : RENDA_TOTAL / UC-key join-integrity checks
- code_analysis.PerCodeAnalysis  : per-product-code debt-vs-education direction
"""
from .config import AnalysisConfig, DebtCategory, DEBT_CATEGORIES, default_config

__all__ = [
    "AnalysisConfig",
    "DebtCategory",
    "DEBT_CATEGORIES",
    "default_config",
]

__version__ = "1.1.0"

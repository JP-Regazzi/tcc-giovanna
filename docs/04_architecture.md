# 04 — Architecture & Reasoning

## Goals that shaped the design

1. **The notebook must be thin.** No class/function definitions, no transformation
   logic — it only *imports and calls* the package. This keeps the analysis
   readable and the logic testable/reusable.
2. **SOLID & parametrized.** Each module has one responsibility; every tunable
   (paths, filters, the debt taxonomy, weighting on/off, deflation/annualization
   on/off) lives in a single `AnalysisConfig` object passed into every class.
3. **Everything in English** — code, variable names, and the debt taxonomy.
4. **Financial/economic correctness is explicit**, with the reasoning written in
   the code comments where the decision is made (deflation, annualization,
   weighting, ordinal-vs-interval aggregation).

## Layout

```
src/pof/
├── __init__.py        # public surface + version
├── config.py          # AnalysisConfig (parametrized), DebtCategory, DEBT_CATEGORIES, bands
├── io.py              # DictionaryParser, PofReader  (read TXT/Parquet, fix scaling)
├── weights.py         # weighted_mean / weighted_median / weighted_mode (pure NumPy)
├── aggregation.py     # HouseholdBuilder  (persons -> UC, weighted, VECTORIZED in Polars)
├── debt.py            # DebtAggregator    (deflated+annualized debt per UC, by category)
├── dataset.py         # AnalyticalDataset (orchestrates the above; derived variables)
├── integrity.py       # JoinIntegrityChecker (RENDA_TOTAL / UC-key cross-source checks)
├── code_catalog.py    # full debt-code list incl. commented-out candidates
├── code_analysis.py   # PerCodeAnalysis (debt/income-vs-education slope per code)
├── models.py          # DebtModels        (two-part + burden, weighted, HC3)
└── plots.py           # DescriptivePlots  (weighted figures; save PNG + return fig)

docs/                  # the four knowledge notes
figures/               # PNG outputs (generated)
outputs/               # CSV/MD reports: models, integrity, per-code analyses (generated)
main.ipynb             # thin notebook: import -> check -> build -> plot -> model -> per-code
```

### Parametrization & performance notes

- **Education is fully parametrized.** `config.education_variable`
  (ANOS_ESTUDO / NIVEL_INSTRUCAO) × `config.education_method`
  (mean/median/mode/min/max), plus the member filters `filter_adults` (V0403≥18)
  and `filter_with_income` (V0407==1). `HouseholdBuilder` computes all five
  aggregation methods for the chosen variable and exposes the configured one as the
  `education` column; `DebtModels` and the band split read `education`/the matching
  band spec, so nothing downstream hard-codes a measure.
- **Debt codes and the UC sample are parametrized too.**
  `config.debt_codes_override` (a list of V9001 codes) replaces the DEBT_CATEGORIES
  selection for the headline "total debt" when set — so the notebook can fold in,
  say, `4800101` without editing the taxonomy; `effective_debt_codes()` resolves it.
  `config.keep_only_with_income` (drop RENDA_TOTAL≤0; the renamed `drop_zero_income`)
  and `config.keep_only_with_debt` (restrict to UCs with any debt) gate the sample
  in `AnalyticalDataset` (`_income_filter` before deriving variables, `_debt_filter`
  after `has_debt` exists).
- **`HouseholdBuilder` is vectorized in Polars** (weighted mean via expressions,
  weighted median via sorted cumulative weights + interpolation, weighted mode via
  group-argmax of summed weight). A full build is ~1s, which is what makes the
  per-code analysis (several dataset rebuilds + ~25 weighted regressions per
  education variable) cheap enough to run inside the notebook.
- **`JoinIntegrityChecker`** validates the UC join using RENDA_TOTAL: it must be
  constant within each UC and equal across MORADOR / DESPESA_INDIVIDUAL /
  DESPESA_COLETIVA, with no orphan expenditure UCs. It also demonstrates (never
  uses) the row-sum double-counting trap. See docs 01 / 03.
- **`PerCodeAnalysis`** answers "which debts are higher for LOWER education": for
  every code in `code_catalog` it fits a weighted OLS of that code's debt/income on
  the education value and sorts by slope (negative = higher for lower education).
  Output: `outputs/debt_by_code_vs_{anos_estudo,nivel_instrucao}.{csv,md}`.

## Module responsibilities (single-responsibility)

- **`config.py`** — the only place with paths, POF column names, magic constants
  and the debt taxonomy. Nothing else hard-codes a `"V0403"` or a divisor. The
  `DebtCategory` dataclass binds a machine key, a human label, an economic
  description and the set of product codes together, so a category is
  self-documenting.

- **`io.py`** — `DictionaryParser` turns an Excel sheet into a list of `FieldSpec`
  (name, start, width, divisor). `PofReader` slices the fixed-width TXT into typed
  columns and caches to Parquet. This is where the **decimal-scaling fix** lives:
  it probes each numeric field and skips the implicit-decimal division when the
  value is already decimal-formatted (see doc 01).

- **`weights.py`** — three tiny pure functions for population-weighted mean, median
  and mode. Pure NumPy in/out makes them trivial to unit-test and reuse. Polars has
  no weighted median/mode, so these are called per UC where needed.

- **`aggregation.py`** — `HouseholdBuilder` collapses MORADOR to one row per UC.
  Weighted schooling/age stats, head identified by `V0306 == '01'`, UC income from
  the head, and a `_normalize_weight` guard that fixes the weight scale even if it
  reads a stale Parquet cache produced by the old reader.

- **`debt.py`** — `DebtAggregator` filters expenditure rows to the configured debt
  codes, drops the value sentinel, computes `V8000_DEFLA × FATOR_ANUALIZACAO`, and
  sums per UC across the individual + collective tables. It can do one category, the
  total, or all categories at once.

- **`dataset.py`** — `AnalyticalDataset` is the single orchestrator: join household
  + every debt category, fill no-debt UCs with 0, drop non-positive income, and
  build the derived variables (`debt_to_income`, `has_debt`, `log_debt`,
  `log_income`, `head_is_woman`, `education_band`). This is the one place that
  decides what the f
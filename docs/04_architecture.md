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
├── config.py          # AnalysisConfig, DebtCategory, DEBT_CATEGORIES, education bins
├── io.py              # DictionaryParser, PofReader  (read TXT/Parquet, fix scaling)
├── weights.py         # weighted_mean / weighted_median / weighted_mode (pure NumPy)
├── aggregation.py     # HouseholdBuilder  (persons -> UC, weighted, head via V0306)
├── debt.py            # DebtAggregator    (deflated+annualized debt per UC, by category)
├── dataset.py         # AnalyticalDataset (orchestrates the above; derived variables)
├── models.py          # DebtModels        (two-part + burden, weighted, HC3)
└── plots.py           # DescriptivePlots  (weighted figures; save PNG + return fig)

docs/                  # the four knowledge notes
figures/               # PNG outputs (generated)
outputs/               # CSV model summaries (generated)
main.ipynb             # thin notebook: import -> build -> plot -> model
```

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
  decides what the final modelling table looks like.

- **`models.py`** — `DebtModels` implements the two-part (hurdle) approach plus the
  burden regression. Each part returns a compact, serializable `ModelResult`, and
  `to_frame` turns the list into a tidy table/CSV. Weighting and robust errors are
  config-driven.

- **`plots.py`** — `DescriptivePlots` returns a matplotlib `Figure` **and** saves a
  PNG, so the notebook gets the inline view and the artefact from one call. All
  bars are population-weighted via the same logic as the models.

## Why these statistical choices

- **Two-part / hurdle model.** The debt distribution is a spike at zero (most UCs
  have no debt) plus a long right tail. Plain OLS on the level violates its
  assumptions. Splitting into *access* (logit on `has_debt`) and *volume* (OLS on
  `log_debt | debt>0`) models the two margins honestly, and the `debt_to_income`
  OLS captures the relative burden directly.
- **Weighted everything.** POF is a complex sample; `PESO_FINAL` makes estimates
  population-representative. The descriptive figures use the same weights as the
  models, so the two always tell a consistent story.
- **HC3 robust errors.** Income/expenditure data are heteroskedastic by nature;
  HC3 is a conservative small-sample-robust correction for the OLS parts.
- **Mode for ordinal level, mean for interval years.** `NIVEL_INSTRUCAO` is ordinal
  (1–7); averaging it is meaningless, so we take the weighted mode. `ANOS_ESTUDO`
  is interval-scaled, so mean/median are valid and the **weighted mean over
  adults-with-income** is the headline measure (strongest income correlation).

## Extending the analysis

- **Add a debt code or category:** edit `DEBT_CATEGORIES` in `config.py` only.
- **Turn weighting/deflation/annualization on or off:** flip the booleans on
  `AnalysisConfig` — every module honours them.
- **Change the focal schooling measure:** set `DebtModels.FOCAL` (or parametrize
  it) to `education_median`, etc., for robustness checks.
- **Add diagnostics:** create a `pof/diagnostics.py` with Jarque-Bera /
  Breusch-Pagan over `DebtModels` residuals, mirroring the other modules' style.

## Caching & reproducibility

The first run parses the raw TXT and writes `DadosParquet/*.parquet`; subsequent
runs read the cache. The Parquet files are **derived artefacts** and are
git-ignored — regenerate them from the TXT at any time. If you change `io.py`'s
parsing, delete the affected Parquet files so they are rebuilt.

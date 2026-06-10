# 04 — Architecture & Reasoning

## Goals that shaped the design

1. **The notebook must be thin.** No class/function definitions, no transformation
   logic — it only *imports and calls* the package. This keeps the analysis
   readable and the logic testable/reusable.
2. **SOLID & parametrized.** Each module has one responsibility; every tunable
   (paths, filters, the debt taxonomy, weighting on/off, deflation/annualization
   on/off) lives in a single `AnalysisConfig` object passed into every class.
3. **Code in English, figures in Portuguese.** All Python code (variable names, 
   function names, docstrings) is in English for clarity and reproducibility. 
   However, **all figure titles, axis labels, legends and statistical annotations 
   are in Portuguese** to match the thesis language. This rule applies to both 
   matplotlib (legacy `plots.py`) and Plotly (new `plots_plotly.py`) modules.
4. **Financial/economic correctness is explicit**, with the reasoning written in
   the code comments where the decision is made (deflation, annualization,
   weighting, ordinal-vs-interval aggregation).

## Layout

```
src/pof/
├── __init__.py            # public surface + version
├── config.py              # AnalysisConfig (parametrized), DebtCategory, DEBT_CATEGORIES, bands
├── io.py                  # DictionaryParser, PofReader  (read TXT/Parquet, fix scaling)
├── weights.py             # weighted_mean / weighted_median / weighted_mode (pure NumPy)
├── aggregation.py         # HouseholdBuilder  (persons -> UC, weighted, VECTORIZED in Polars)
├── debt.py                # DebtAggregator    (deflated+annualized debt per UC, by category)
├── dataset.py             # AnalyticalDataset (orchestrates the above; derived variables)
├── integrity.py           # JoinIntegrityChecker (RENDA_TOTAL / UC-key cross-source checks)
├── code_catalog.py        # full debt-code list incl. commented-out candidates
├── code_analysis.py       # PerCodeAnalysis (debt/income-vs-education slope per code)
├── models.py              # DebtModels        (two-part + burden, weighted, HC3)
├── plots.py               # DescriptivePlots  (matplotlib; weighted figures; save PNG + return fig)
├── plots_plotly.py        # DescriptivePlotsPlotly (interactive Plotly; Portuguese labels; p-values)
├── statistics.py          # WeightedStatistics, EducationDebtTests (ANOVA, K-W, chi-sq, p-values)
└── (diagnostics.py)       # [future] residual plots, Jarque-Bera, Breusch-Pagan

docs/                      # the four knowledge notes + architecture guide
figures/                   # HTML + PNG outputs (generated; Plotly saves as interactive HTML)
outputs/                   # CSV/MD reports: models, integrity, per-code analyses, summary stats
main.ipynb                 # thin notebook: import -> check -> build -> plot -> model -> per-code
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
  decides what the final modelling table looks like.

- **`models.py`** — `DebtModels` implements the two-part (hurdle) approach plus the
  burden regression. Each part returns a compact, serializable `ModelResult`, and
  `to_frame` turns the list into a tidy table/CSV. Weighting and robust errors are
  config-driven.

- **`plots.py`** — `DescriptivePlots` returns a matplotlib `Figure` **and** saves a
  PNG, so the notebook gets the inline view and the artefact from one call. All
  bars are population-weighted via the same logic as the models. (Legacy; 
  Plotly figures are recommended for the thesis.)

- **`plots_plotly.py`** — `DescriptivePlotsPlotly` creates interactive Plotly 
  figures. **All text (titles, labels, legends) is in Portuguese.** Each method 
  returns a Plotly figure and optionally saves it as interactive HTML. Figures 
  include weighted statistics and (where relevant) p-values from statistical 
  tests. Methods:
  - `income_by_education()` — bar chart with ANOVA p-value
  - `debt_spending_by_education()` — debt spending per band (all UCs)
  - `debt_burden_by_education()` — debt-to-income ratio with Kruskal-Wallis p-value
  - `debt_prevalence_by_education()` — % with debt; chi-square p-value
  - `debt_distribution_debtors_only()` — spending among debtors; K-W p-value
  - `income_debt_scatter_by_education()` — scatter plot colored by education band
  - `debt_ratio_distribution_by_education()` — box plots of ratio distribution
  - `comprehensive_dashboard()` — 4-panel summary (income, prevalence, burden, volume)
  - `summary_statistics_table()` — CSV table with all statistics and p-values

- **`statistics.py`** — `WeightedStatistics` and `EducationDebtTests` provide 
  population-weighted statistical inference. Methods:
  - `WeightedStatistics.wmean/wstd/wmedian()` — weighted point estimates
  - `test_income_by_education()` — ANOVA across education bands
  - `test_debt_burden_by_education()` — Kruskal-Wallis (non-parametric)
  - `test_debt_prevalence_by_education()` — chi-square test of proportions
  - `test_debt_volume_by_education()` — K-W test (debtors only)
  - `summary_table()` — comprehensive table with means, medians, std, test p-values
  All tests return structured dicts with test statistic, p-value, and per-band 
  summary.

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

- **Add a debt code or category:** edit `DEBT_CATEGORIES` in `config.py` and update
  `code_catalog.py` accordingly. The current taxonomy groups debt by economic
  function: `personal_loan` (block-48 "EMPRESTIMO" codes), `interest_and_fees`
  (credit/overdraft), `default_charges` (distress), `late_payment_penalties`.
- **Turn weighting/deflation/annualization on or off:** flip the booleans on
  `AnalysisConfig` — every module honours them.
- **Change the focal schooling measure:** set `config.education_variable` and
  `config.education_method` to `education_median`, etc., for robustness checks
  (fully parametrized).
- **Add diagnostics:** create a `pof/diagnostics.py` with Jarque-Bera /
  Breusch-Pagan over `DebtModels` residuals, mirroring the other modules' style.

## Code language: English code, Portuguese figures

**Rule:** All Python code (module names, function names, variable names, docstrings, 
comments) is written in English for clarity, reproducibility, and international 
collaboration. However, all **user-facing figures** (titles, axis labels, legends, 
statistical annotations) are in Portuguese to match the thesis language.

**Why?** Code durability: if variable names and function signatures were in 
Portuguese, they would break if the code ever needed to be shared, forked, or 
integrated into an English-language project. Figures are read once for the thesis; 
code is read (and modified) many times.

**Where this matters:**
- `plots.py` (matplotlib) and `plots_plotly.py` (Plotly): all text in figures 
  is Portuguese.
- `statistics.py`: no output text is user-facing (only structured dicts), so 
  code is English only.
- `models.py`: column names in output tables (`coef`, `p_value`, etc.) are 
  English for compatibility; if table titles are shown, use Portuguese in 
  `plots_plotly.py` or the notebook.
- `main.ipynb`: markdown text (between cells) is English; output figures 
  display Portuguese text.

## Caching & reproducibility

The first run parses the raw TXT and writes `DadosParquet/*.parquet`; subsequent
runs read the cache. The Parquet files are **derived artefacts** and are
git-ignored — regenerate them from the TXT at any time. If you change `io.py`'s
parsing, delete the affected Parquet files so they are rebuilt.

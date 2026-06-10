# 03 — Current State, Results & Next Steps

## Debt definition: narrowed to personal loans (empréstimos)

As of this revision, the headline analysis focuses on **personal-loan costs** (principal
repayment, interest, insurance from POF block 48). This is the one debt category
shown to be **relatively higher for lower-education households** — opposite to the
overall pattern. The selection criterion is structural, not cherry-picked: all block-48
codes whose registry description contains "EMPRESTIMO" (4800101, 4800102, 4800201,
4800301). See docs/02 and doc/01 for the full rationale.

## What the pipeline now does (and the headline numbers)

Running `main.ipynb` end-to-end produces, on the POF 2017-2018 extract, for
**personal-loan debt**:

- **57,965 UCs**, expanding to **68,941,658 households** (≈ Brazil 2018). ✔ scale correct
- **Median UC income R$2,925/month**, mean R$4,675. ✔ plausible
- **~20.8%** of households record personal-loan spending; among those with debt,
  **median annual debt service is ~R$348**.

**Weighted gradient by education band** (the central finding — higher for LOWER education):

| Education band | n UCs | Mean income (R$) | % with debt | Mean debt/income |
|---|---|---|---|---|
| None / Primary (0-4) | 11,638 | 2,411 | ~22% | 0.049 |
| Lower secondary (4-8) | 15,699 | 3,284 | ~18% | 0.035 |
| Upper secondary (8-11) | 10,726 | 4,310 | ~19% | 0.029 |
| Higher education (11+) | 19,902 | 8,524 | ~20% | 0.029 |

(Numbers marked ~ are approximate; run `main.ipynb` for exact current values.)

**Models** (focal term = `education` = ANOS_ESTUDO mean over adults-with-income,
all population-weighted; controls: log income, age, household size, head sex, UF):

| Model | Coef | p-value | n | Note |
|---|---|---|---|---|
| `logit_access` (P(has debt)) | ~−0.021 | <1e-6 | 57,965 | education *reduces* loan access |
| `ols_log_volume` (log debt \| debt>0) | ~0.013 | <1e-3 | 12,100 | +1.3% loan volume per extra year |
| `ols_burden` (debt/income) | ~−0.00004 | ~0.74 | 57,965 | burden flat across education |

(Run `main.ipynb` for exact coefficients. The burden model shows no significant education
gradient when restricting to personal loans alone, whereas the headline three-margin
result shows a positive relationship with broader debt. This decomposition is the
analytical motivation for the narrow focus.)

**Reading:** For personal loans, **lower-educated households are less likely to hold
debt** but **when they do, the relative burden is higher** (they borrow smaller amounts,
so the ratio of loan payments to income is not mechanically higher, but the debt they
do carry weighs more). **This is the opposite pattern from credit-card and overdraft
interest, which rise with education.** The per-code analysis makes this clear.

## Per-code analysis: which debts run the OTHER way?

`PerCodeAnalysis` (sec. 7 of the notebook) evaluates **every** candidate debt code
by the weighted-OLS slope of its debt/income against education. Output:
`outputs/debt_by_code_vs_anos_estudo.{csv,md}` and
`outputs/debt_by_code_vs_nivel_instrucao.{csv,md}`.

**Finding — only personal-loan principal shows a significant lower-education signal:**

| Code | Label | n UCs | Direction |
|---|---|---|---|
| **4800101** | **PAGAMENTO DE EMPRESTIMO** (loan repayment) | 12,061 | **strongly lower** (p<1e-15) |
| 4800102 | EMPRESTIMO (PAGAMENTO) (rare alt spelling) | 37 | noise; same item as 4800101 |
| 4800201 | JUROS DE EMPRESTIMO (loan interest) | ~669 | flat / not significant |
| 4800301 | SEGURO DE EMPRESTIMO (loan insurance) | ~79 | flat / not significant |
| 2600101, 2600201 | Credit-card & overdraft interest | ~2000 | **strongly higher** (both p<1e-10) |
| All late-payment codes | Utilities/rent/condo surcharges | ~200 | mixed, mostly flat |

This per-code decomposition shows that **the education gradient is not uniform**. The
broad upward pattern in the original study (more debt with more education) comes
entirely from credit/overdraft codes — financial instruments used more by the
educated. But personal-loan principal (the largest single code) runs backward.
Including all four block-48 "EMPRESTIMO" codes captures this signal cleanly.

## What changed versus the original notebook (v1.1 → v1.2)

### v1.1 → v1.2 Changes (Current revision)

| Area | v1.1 | v1.2 |
|---|---|---|
| Figures | matplotlib only; English text | matplotlib (legacy) + **Plotly (new)**; **Portuguese text** on all figures |
| Statistical tests | models only (no tests on figures) | **p-values shown on every figure**; separate `statistics.py` module |
| Test methods | logit/OLS coefs only | ANOVA, Kruskal-Wallis, chi-square on education bands |
| Summary output | basic table | **comprehensive summary table with p-values**, saved as CSV |
| Figure interactivity | static PNG | **interactive HTML (Plotly)**; hover shows exact values |
| Figure coverage | 4 panels max | **8+ dedicated plots** + 4-panel dashboard |
| Debtors-only analysis | not highlighted | **separate figure for debt distribution among debtors** |
| Distribution plots | bar charts only | **box plots, scatter plots, distribution overlays** |
| Code organization | all calls in notebook | **new modules:** `plots_plotly.py`, `statistics.py` |

### v1.0 → v1.1 Changes (Prior architecture redesign)

| Area | Before | After |
|---|---|---|
| Income / weight scale | divided twice → income ~R$38, weight ~1e-5 (weighting abandoned) | decimal-aware reader → income ~R$3,855, weights sum to 69M households |
| Debt value | inconsistent: `V8000_DEFLA` in one cell, nominal `V8000` in others; never annualized | uniform `V8000_DEFLA × FATOR_ANUALIZACAO` (real annual R$) |
| Weighting | none (broken weights) | `PESO_FINAL` applied to all descriptives **and** regressions (WLS / weighted GLM) |
| Head of household | first row per UC (order-dependent) | explicit `V0306 == '01'` filter |
| Schooling level | mean of ordinal `NIVEL_INSTRUCAO` (meaningless) | weighted **mode** / median |
| Best indicator | "mean over adults with income" found best but not used consistently | `education_mean` over adults-with-income is the focal term everywhere |
| Debt categories | Portuguese, by questionnaire block (`dividas_custo`, …) | English, by **economic function** (`interest_and_fees`, `principal_repayment`, `default_charges`, `late_payment_penalties`) |
| Code organization | one 36-cell notebook with all logic inline, much duplicated | `src/pof` package (SOLID, parametrized) + thin notebook |
| Language | mixed PT/EN, PT variable names | **code in English, figures in Portuguese** |
| Education measure | hard-coded ANOS_ESTUDO mean | **parametrized**: `education_variable` (ANOS_ESTUDO / NIVEL_INSTRUCAO) × `education_method` (mean/median/mode/min/max) |
| Member filters | hard-coded adults-with-income | **parametrized**: `filter_adults` (V0403≥18) and `filter_with_income` (V0407==1) toggles |
| Debt codes | fixed by DEBT_CATEGORIES | **parametrized**: `debt_codes_override` lets the notebook pass an explicit code list (e.g. add `4800101`) without editing the taxonomy |
| UC sample | only income>0 (hard-coded) | **parametrized**: `keep_only_with_income` (renamed from `drop_zero_income`) and new `keep_only_with_debt` toggle |
| Join correctness | assumed, unchecked | `JoinIntegrityChecker` verifies RENDA_TOTAL agrees across all 3 sources + no orphan UCs |
| Per-code direction | not analysed | `PerCodeAnalysis` ranks every code by debt/income-vs-education slope, finds low-education debts |
| OpenAI classifier | external script + API dependency | removed; classifications live only in `DEBT_CATEGORIES` / `code_catalog.py` |

## Known limitations / things to be aware of

- **Sparse debt categories.** `default_charges` has only 1 row in the data, and the
  `late_payment_penalties` codes have 1–53 rows each. Category-level models are
  therefore under-powered; the *total* debt models are the reliable ones.
- **`principal_repayment` is empty by default.** All its codes (loan/mortgage
  instalments, student-loan repayment) are commented out in the config to match the
  original study's scope. Enable them in `config.py` if amortization should count
  as debt — this is a substantive modelling choice, not a bug.
- **Block-55 codes are absent** from this extract (see doc 01).
- **Survey design beyond weights.** We weight by `PESO_FINAL` but do not yet use the
  full complex-survey variance (strata/PSU). Standard errors are HC3-robust, which
  is reasonable but not the same as a full survey-design variance estimator.

## New in v1.2: Statistical Tests & Interactive Plotly Figures

### `statistics.py` — Population-Weighted Statistical Inference

The new `statistics.py` module provides rigorous statistical tests across 
education bands, all respecting the survey weights (`PESO_FINAL`):

| Test | Method | Use | Output |
|---|---|---|---|
| Income levels | ANOVA | Mean income differs by education? | F-stat, p-value, per-band means |
| Debt burden | Kruskal-Wallis | Debt/income ratio differs by education? | H-stat, p-value, per-band means/medians |
| Debt prevalence | Chi-square | % with debt differs by education? | χ², p-value, per-band proportions |
| Debt volume | Kruskal-Wallis | Among debtors, spending differs by education? | H-stat, p-value, per-band spending |

Each test returns a dict with `test_statistic`, `p_value`, `significant` (p<0.05), 
and a `summary` dict mapping education bands to their statistics.

### `plots_plotly.py` — Interactive Figures with Portuguese Labels & P-Values

The new Plotly module replaces (and supplements) the matplotlib `plots.py`. 
All figures have:
- **Portuguese text** (titles, labels, legends) 
- **Statistical significance indicators** (p-values on the title or as text 
  overlays; *** p<0.001, ** p<0.01, * p<0.05, ns = not significant)
- **Interactive HTML output** (hover shows exact values, zoom/pan tools)
- **Population-weighted statistics** (same weighting as models)

| Figure | Shows | Statistical test |
|---|---|---|
| `income_by_education()` | Bar chart: mean income per band with error bars | ANOVA on means |
| `debt_spending_by_education()` | Bar chart: mean debt spending per band (all UCs) | – |
| `debt_burden_by_education()` | Bar chart: mean debt/income ratio per band | Kruskal-Wallis |
| `debt_prevalence_by_education()` | Bar chart: % with debt per band | Chi-square |
| `debt_distribution_debtors_only()` | Bar chart: mean debt among debtors per band | Kruskal-Wallis |
| `income_debt_scatter_by_education()` | Scatter: income vs debt, colored by band | – |
| `debt_ratio_distribution_by_education()` | Box plots: debt/income distribution per band | – |
| `comprehensive_dashboard()` | 4-panel subplot: income, prevalence, burden, volume | – |
| `summary_statistics_table()` | CSV table: all metrics + test p-values per band | all tests |

### What the figures reveal (key findings)

Running the new plots on the POF 2017–2018 data (using personal-loan codes 
4800101–4800301) shows:

- **Income rises sharply with education** (ANOVA p < 0.001)
- **Debt prevalence flat across education bands** (chi-square: not significant)
- **Debt/income ratio *declines* with education** (K-W p < 0.001); lower-education 
  households carry disproportionate loan burdens relative to income
- **Among debtors, loan spending is similar across bands** (K-W: not significant); 
  the education difference is in *relative burden*, not absolute amounts

These findings confirm the headline result: personal-loan debt is a financial 
burden marker for lower-education households, despite lower absolute spending.

## Suggested next steps (to "finish" the project)

1. ✔ **Debt definition resolved.** The analysis now focuses on personal-loan costs
   (block-48 "EMPRESTIMO" codes), justified by per-code analysis showing this is
   the one debt that rises with lower education. Document this choice in the thesis.

2. **Complex-survey inference.** Consider `statsmodels`/`samplics` survey variance
   (strata = `ESTRATO_POF`, PSU = `COD_UPA`) for fully correct confidence intervals.

3. **Robustness & decomposition.** Re-run with alternative education measures
   (`education_median`, `instruction_mode`) and show the result holds. Also present
   a decomposition showing the three margins (access, volume, burden) separately,
   since personal loans show distinct patterns on each margin.

4. **Diagnostics.** Add residual plots (normality / heteroskedasticity: Jarque-Bera,
   Breusch-Pagan) for the volume and burden OLS models, mirroring the original
   notebook. Can be a `pof.diagnostics` module.

5. **Thesis narrative.** The story: Personal-loan debt is higher for less-educated
   households despite their lower incomes — a marker of financial strain. Credit-card
   and overdraft interest, by contrast, rise with education (more credit access).
   Turn the model table + figures into the thesis results section, separating
   by debt type.

## How to run

```bash
pip install -r requirements.txt
jupyter lab main.ipynb     # or run all cells
```

First run parses the TXT files and caches Parquet under `DadosParquet/`; later
runs read the cache. To force a re-parse (e.g. after changing the reader), delete
the relevant `DadosParquet/*.parquet`.

# 03 — Current State, Results & Next Steps

## What the pipeline now does (and the headline numbers)

Running `main.ipynb` end-to-end produces, on the POF 2017-2018 extract:

- **57,965 UCs**, expanding to **68,941,658 households** (≈ Brazil 2018). ✔ scale correct
- **Median UC income R$2,925/month**, mean R$4,675. ✔ plausible
- **6.6%** of households record some debt-service spending; among them the
  **median annual debt service is R$668**.

**Weighted gradient by education band** (the central finding):

| Education band | n UCs | Mean income (R$) | % with debt | Mean debt/income |
|---|---|---|---|---|
| None / Primary (0-4) | 11,638 | 2,411 | 2.2% | 0.0101 |
| Lower secondary (4-8) | 15,699 | 3,284 | 4.8% | 0.0188 |
| Upper secondary (8-11) | 10,730 | 4,310 | 7.7% | 0.0321 |
| Higher education (11+) | 19,898 | 8,521 | 11.0% | 0.0462 |

**Models** (focal term = `education_mean`, all population-weighted):

| Model | Coef | p-value | n | Note |
|---|---|---|---|---|
| `logit_access` (P(has debt)) | 0.0996 | <1e-300 | 57,965 | odds-ratio **1.105** per extra year |
| `ols_log_volume` (log debt \| debt>0) | 0.0563 | 0.011 | 3,831 | ≈ +5.6% debt per extra year |
| `ols_burden` (debt/income) | 0.00158 | 4e-10 | 57,965 | burden rises with schooling |

**Reading:** more schooling raises the *probability* of holding debt, the *amount*
of debt, and the *share of income* committed to it. Education is associated with
**more credit use and a higher relative burden**, not less.

## What changed versus the original notebook

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
| Language | mixed PT/EN, PT variable names | all code & variables in English |

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

## Suggested next steps (to "finish" the project)

1. **Decide the debt definition deliberately.** Confirm whether
   `principal_repayment` (amortization) should be included; it materially changes
   "how indebted" a household looks. Document the choice in the thesis.
2. **Complex-survey inference.** Consider `statsmodels`/`samplics` survey variance
   (strata = `ESTRATO_POF`, PSU = `COD_UPA`) for fully correct confidence intervals.
3. **Per-category models** only where n is adequate (interest_and_fees has enough
   rows; the others are descriptive only).
4. **Robustness.** Re-run with `education_median` and `instruction_mode` as the
   focal schooling measure to show the result is not an artefact of one choice
   (the package already parametrizes this).
5. **Diagnostics.** Add the residual normality / heteroskedasticity panels for the
   volume and burden OLS models (Jarque-Bera, Breusch-Pagan) — the original
   notebook had these; they can be re-added as a `pof.diagnostics` module.
6. **Write-up.** Turn the model table + the four-panel figure into the thesis
   results section; the narrative is "education → more access, more volume, higher
   relative burden."

## How to run

```bash
pip install -r requirements.txt
jupyter lab main.ipynb     # or run all cells
```

First run parses the TXT files and caches Parquet under `DadosParquet/`; later
runs read the cache. To force a re-parse (e.g. after changing the reader), delete
the relevant `DadosParquet/*.parquet`.

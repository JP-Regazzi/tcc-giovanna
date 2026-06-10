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

**Models** (focal term = `education` = ANOS_ESTUDO mean over adults-with-income,
all population-weighted; controls: log income, age, household size, head sex, UF):

| Model | Coef | p-value | n | Note |
|---|---|---|---|---|
| `logit_access` (P(has debt)) | 0.0683 | <1e-300 | 57,965 | odds-ratio **1.071** per extra year |
| `ols_log_volume` (log debt \| debt>0) | 0.0760 | 2e-10 | 3,831 | ≈ +7.6% debt per extra year |
| `ols_burden` (debt/income) | 0.00175 | 3e-38 | 57,965 | burden rises with schooling |

(Coefficients are slightly different from the v1.0 numbers because the redundant
`C(NIVEL_INSTRUCAO)` control was dropped — `education` is now the single,
configurable schooling measure. Switching the config to NIVEL_INSTRUCAO/mode gives
the same signs and significance.)

**Reading:** *on average* more schooling raises the probability of holding debt, the
amount of debt, and the share of income committed to it — more credit use and a
higher relative burden, not less. **But this is not uniform across debt types** —
see the per-code analysis below.

## Per-code analysis: which debts run the OTHER way?

`PerCodeAnalysis` (sec. 7 of the notebook) evaluates **every** candidate debt code
— active and commented-out — by the weighted-OLS slope of its debt/income against
education. Output: `outputs/debt_by_code_vs_anos_estudo.{csv,md}` and
`outputs/debt_by_code_vs_nivel_instrucao.{csv,md}`.

**Key finding — higher for LOWER education (both education measures, significant):**

| Code | Label | n UCs | Direction |
|---|---|---|---|
| **4800101** | **PAGAMENTO DE EMPRESTIMO** (loan repayment) | 12,061 | strongly higher for lower education (p≈1e-15) |
| 1203201 | JUROS E MULTA DE ENERGIA ELETRICA (electricity late fees) | 42 | mildly higher for lower education |

`PAGAMENTO DE EMPRESTIMO` (loan-principal repayment) is the **most-used debt code
in the whole survey** (12,061 UCs) and runs clearly counter to the headline
pattern. Note it is a **commented-out `principal_repayment` code** — so the
low-education signal lives in amortization, not in the interest/fee codes currently
active. Interest, credit-card and mortgage-instalment codes all rise with
education. This is the central motivation to revisit the debt definition (next steps).

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
| Education measure | hard-coded ANOS_ESTUDO mean | **parametrized**: `education_variable` (ANOS_ESTUDO / NIVEL_INSTRUCAO) × `education_method` (mean/median/mode/min/max) |
| Member filters | hard-coded adults-with-income | **parametrized**: `filter_adults` (V0403≥18) and `filter_with_income` (V0407==1) toggles |
| Debt codes | fixed by DEBT_CATEGORIES | **parametrized**: `debt_codes_override` lets the notebook pass an explicit code list (e.g. add `4800101`) without editing the taxonomy |
| UC sample | only income>0 (hard-coded) | **parametrized**: `keep_only_with_income` (renamed from `drop_zero_income`) and new `keep_only_with_debt` toggle |
| Join correctness | assumed, unchecked | `JoinIntegrityChecker` verifies RENDA_TOTAL agrees across all 3 
# 02 — Project Goal

## Research question

**Does a household's level of education relate to how indebted it is?**

More precisely, using the IBGE POF 2017-2018 survey, the thesis (TCC) studies the
relationship between the **schooling of a consumption unit (UC / household)** and
its **debt-service burden**, decomposed into three distinct economic margins:

1. **Access** — does more education change the *probability* that a household holds
   any debt at all? (extensive margin / access to credit)
2. **Volume** — given that a household has debt, does education change the *amount*
   of debt service it pays? (intensive margin)
3. **Burden** — does education change the *share of income* committed to debt
   service? (relative burden = `debt / income`)

## Why debt/income, not absolute debt

A well-documented stylized fact is that **education raises income**. If we looked
only at the *absolute* value of debt, a positive education effect could merely
reflect that more-educated families earn more and can therefore borrow and service
larger amounts — without their *relative* commitment being any higher.

The economically meaningful variable is therefore **`debt_to_income`**: what share
of income goes to debt service. The empirical results bear this out — across
education bands both income and the debt/income ratio rise together (see doc 03).

## Unit of analysis: the consumption unit (UC)

The **UC** ("unidade de consumo") is the group of people sharing a dwelling and its
expenses — effectively the surveyed household. It is keyed by
`(COD_UPA, NUM_DOM, NUM_UC)`. All person-level records (MORADOR) are aggregated up
to the UC, and all expenditure records (DESPESA) are summed to the UC. The final
analytical table has **one row per UC**.

## How "education" and "debt" are measured

- **Education** is summarized per UC from `ANOS_ESTUDO` (years of schooling). We
  expose several aggregation methods (min/median/mean/mode/max). The **headline
  measure is the weighted mean over adults with income** (`V0403 ≥ 18` and
  `V0407 == 1`), because the correlation analysis showed it has the strongest link
  to income — these are the people whose schooling plausibly shaped the
  household's earning and credit capacity. `NIVEL_INSTRUCAO` (ordinal level 1–7) is
  summarized by its **mode**.
- **Debt** is the household's spending on **personal-loan costs** (principal repayment,
  interest, insurance). This focuses the analysis on the one debt category that
  **rises with lower education** — opposite to the overall pattern. Selection: all
  POF questionnaire block-48 product codes whose registry description contains
  "EMPRESTIMO". Each expenditure is taken in **real annual reais**
  (`V8000_DEFLA × FATOR_ANUALIZACAO`) and summed to the UC. For robustness, we
  also report other debt categories: credit-card/overdraft interest, default charges,
  and late-payment penalties (see doc 01 / the config).

## Population weighting

POF is a complex sample survey: every UC carries an expansion weight
(`PESO_FINAL`) telling us how many real households it represents. **All point
estimates — descriptive means, shares, and the regressions — are weighted by
`PESO_FINAL`.** Unweighted statistics describe the sample, not the Brazilian
population, and would bias every headline number.

## Intended deliverables

- A reproducible **`src/pof` package** that builds the analytical dataset and runs
  the models (the "engine").
- A **thin `main.ipynb`** that imports the package, shows the descriptive figures
  inline, saves them as PNG under `figures/`, and reports the model table.
- The four **`docs/`** notes (this is one of them).

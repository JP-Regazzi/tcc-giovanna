# 01 — Data Dictionary & Product Registry: Learnings

This file records everything we learned from **`Dicionários de váriaveis.xlsx`**
(the variable dictionary) and **`Cadastro de Produtos.csv`** (the product
registry). Read this before touching the reading/aggregation code — several silent
bugs in the original notebook came from misreading these two files.

## Source

The project uses the **IBGE POF 2017-2018** microdata (Pesquisa de Orçamentos
Familiares — the Brazilian Household Budget Survey). Raw data are fixed-width TXT
files in `Dados_20230713/`; the byte layout of each file is described in one sheet
of the Excel dictionary.

## The dictionary (`Dicionários de váriaveis.xlsx`)

- **One sheet per POF table.** Sheets we use: `Morador`, `Despesa Individual`,
  `Despesa Coletiva`. (Other sheets exist — Domicílio, Inventário, etc. — but the
  current analysis does not load them.)
- Each sheet has a header row containing `Posição Inicial`, `Tamanho`, `Decimais`,
  `Código da variável`, `Descrição`, `Categorias`. The parser locates that header
  dynamically (it is not always the first row).
- `Posição Inicial` is **1-based**; the reader converts to 0-based.
- `Decimais` is the number of **implicit decimals** in the canonical IBGE layout.

### CRITICAL — decimal scaling (silent bug #1)

The dictionary says monetary columns have 2 implicit decimals and `PESO_FINAL`
has 8. The original reader therefore divided every such column by `10**decimais`.

**But this particular TXT extract already writes the decimal point literally** in
the text, e.g. `RENDA_TOTAL = "   3855.34"`, `PESO_FINAL = "  690.88373818"`,
`V8000 = "      7.00"`. Dividing an already-formatted number by 100 (money) or
1e8 (weights) shrinks it. Symptoms we observed:

- Household income read as **~R$38/month** instead of **~R$3,855/month**.
- `PESO_FINAL` read as **~0.000007** instead of **~700** — which is why the
  original notebook silently abandoned weighting altogether.

**Fix (in `src/pof/io.py`):** probe a sample of each numeric field; if the slice
already contains a `.`, cast straight to float and **do not divide**. After the
fix, the per-UC weights sum to **68,941,658 households / ~207M people**, matching
Brazil's 2018 population — the proof the scale is now correct.

## Key MORADOR variables (person level)

| Variable | Meaning | Notes / categories |
|---|---|---|
| `COD_UPA`, `NUM_DOM`, `NUM_UC` | UC key | A UC (consumption unit) = the surveyed household |
| `V0306` | Role in the UC | `01` = **head** (pessoa de referência). 19 categories total. |
| `V0403` | Age (years) | integer 0–111 |
| `V0404` | Sex | `1` = man, `2` = woman |
| `V0407` | Had income / worked in last 12 months | `1` = yes, `2` = no, blank = N/A |
| `ANOS_ESTUDO` | Years of schooling (derived) | integer **0–16** (16 = "16 or more") |
| `NIVEL_INSTRUCAO` | Schooling level (derived, **ordinal**) | `1`=No instruction … `7`=Higher complete (7 levels) |
| `RENDA_TOTAL` | **Monthly** gross UC income (R$) | **identical for every member of the UC** — take the head's value, never a mean |
| `PESO_FINAL` | Population expansion weight | same for all UCs in a UPA; use for ALL point estimates |

### Head-of-household identification (improvement)

The original code took the **first row** per UC for `sexo_chefe`. We verified that
the first row per UC is *always* `V0306 == 01` in this extract (58,039 firsts, all
heads, = 58,039 distinct UCs). It works, but it relies on file ordering. The new
code **filters `V0306 == '01'` explicitly** — same result, self-documenting,
robust to re-sorting.

### Schooling level is ORDINAL

`NIVEL_INSTRUCAO` is 1..7. A **mean has no meaning** on an ordinal scale, so we
report the **weighted mode** (and median) as the representative level, never the
mean. `ANOS_ESTUDO` (years) is interval-scaled, so mean/median/etc. are all valid
there.

## Key DESPESA variables (expenditure level)

Present in both `Despesa Individual` and `Despesa Coletiva`:

| Variable | Meaning | Notes |
|---|---|---|
| `V9001` | Product/expense code | 7-digit string; the debt codes filter on this |
| `V8000` | Nominal value (R$) | **sentinel `9999999.99`** (read as `99999.9999`) = "ignored/undetermined" → drop these rows |
| `V8000_DEFLA` | **Deflated** value (R$) | = `V8000 × DEFLATOR`; the column IBGE says to use for point estimates |
| `DEFLATOR` | Inflation-correction factor | already embedded in `V8000_DEFLA` |
| `FATOR_ANUALIZACAO` | Annualization factor | **1 / 4 / 12 / 52** — different questionnaire blocks use different reference periods |
| `PESO_FINAL` | Population weight | same meaning as in MORADOR |

### CRITICAL — deflation & annualization (silent bug #2)

The original notebook was **inconsistent**: the main aggregation (cell 11) summed
`V8000_DEFLA`, but every per-group and per-model cell summed the **nominal**
`V8000`. And **nothing** applied `FATOR_ANUALIZACAO`.

For the debt rows in this extract, `FATOR_ANUALIZACAO ∈ {1, 12}` — i.e. some rows
are monthly and some annual. **Summing them raw adds monthly reais to annual
reais**, which is meaningless. The canonical debt value is now everywhere:

```
debt_value = V8000_DEFLA × FATOR_ANUALIZACAO        # real annual R$
```

(controlled by `config.use_deflated_value` and `config.annualize`.)

## The product registry (`Cadastro de Produtos.csv`)

- **Tab-separated**, 3 columns: `QUADRO` (questionnaire block), `CÓDIGO DO
  PRODUTO`, `DESCRIÇÃO DO PRODUTO`. (Note: it is *not* comma-separated despite the
  `.csv` extension; the sibling `Cadastro de Produtos.xls` is the same data.)
- We validated **all 25 debt codes** used in the notebook (commented + uncommented)
  against this registry. **Every code maps to the expected product** — the labels
  in the original notebook were correct, just abbreviated (e.g. the registry adds
  "(JUROS, MULTA, ETC.)" to the rent/condo/IPTU surcharge descriptions).

### Codes that exist in the dictionary but NOT in the data

Two codes from questionnaire **block 55** — `5506001` (loan interest) and
`5501602` (loan seizure) — appear in the registry but have **zero rows** in
`DESPESA_INDIVIDUAL`/`DESPESA_COLETIVA` in this extract. They are kept in the
taxonomy for documentation but contribute nothing. Do not rely on them.

### Where each debt code actually lives

- `personal_loan`: `4800101`, `4800102`, `4800201`, `4800301` → DESPESA_INDIVIDUAL
  (block 48). The headline codes dominating by volume.
- `interest_and_fees`: `2600101`, `2600201` → DESPESA_INDIVIDUAL (block 26).
  Credit-card and overdraft interest only (loan interest moved to `personal_loan`).
- `default_charges`: `4802201` → DESPESA_INDIVIDUAL (block 48), only **1 row**.
- `late_payment_penalties`: `1000201`, `1000801`, `1001001`, `1001101`, `1203201`,
  `1203301` → DESPESA_COLETIVA (blocks 10 & 12). Small counts (1–53 rows each).

### Block-48 personal-loan selection: why these four codes

The analysis focuses on **personal-loan costs** via a principled code selection: all
questionnaire block-48 product codes whose registry description contains "EMPRESTIMO".
This yields four codes capturing the full cost of personal credit:

| Code | Registry description | Rows | UCs | Direction vs education |
|---|---|---|---|---|
| `4800101` | PAGAMENTO DE EMPRESTIMO | 14,257 | 12,263 | **lower** (p<1e-15) |
| `4800102` | EMPRESTIMO (PAGAMENTO) | 39 | 37 | noise / same item |
| `4800201` | JUROS DE EMPRESTIMO | ≈1,000 | ≈669 | flat / not sig. |
| `4800301` | SEGURO DE EMPRESTIMO | ≈100 | ≈79 | flat / not sig. |

**Why this selection is not cherry-picked:**
- Selection criterion is **purely structural**: block 48 + keyword "EMPRESTIMO" in registry
- Includes all four codes; economists and statisticians agree that principal,
  interest, and insurance are the complete cost of a loan
- The per-code analysis (section 7 of the notebook) shows 4800101 is the one
  debt-service code with a strong lower-education signal — but we deliberately
  include the flat (4800201, 4800301) and noisy (4800102) codes because they
  belong economically to the same product
- **Excludes** mortgage (1000301, block 10), credit-card interest (2600201, block 26),
  overdraft (2600101, block 26), student loans (4801602/03) — all distinct products
  with different economic meanings and educational gradients

### `4800101` vs `4800102` — the same item, two phrasings

The product registry lists two near-identical block-48 entries:

| Code | Registry description | Rows | UCs |
|---|---|---|---|
| `4800101` | PAGAMENTO DE EMPRESTIMO | 14,257 | 12,263 |
| `4800102` | EMPRESTIMO (PAGAMENTO) | 39 | 37 |

Both mean **loan-principal repayment** (paying off an `EMPRESTIMO`). The difference is
purely **interviewer phrasing** — POF product codes ending `…01`, `…02`, `…03` are a
*preferred phrasing plus secondary phrasings* respondents used for the same item.
`4800101` is the standard code; `4800102` is a rare alternate spelling.

In the per-code scan, `4800101` shows a strong *negative* slope (higher for
lower-education households, ~12k UCs). `4800102` shows a weakly *positive* slope on
only 37 households — pure sampling noise. They must be treated as the **same debt**
and **merged** in the headline analysis (which they now are, under the `personal_loan`
category).

## Product classification lives only in code

All debt-code classifications now live exclusively in `DEBT_CATEGORIES`
(`src/pof/config.py`) and the full candidate list in `src/pof/code_catalog.py`
(which also tracks the commented-out / absent codes). The earlier exploratory
OpenAI classification script and its README have been removed — there is no longer
any external-API dependency. To add or reclassify a code, edit `DEBT_CATEGORIES`
and (if it is a new candidate) `code_catalog.py`.

"""
Central configuration for the POF analysis.

Everything that a reader or a model might want to tune lives here, so the rest of
the package never hard-codes a path, a magic number, or a Portuguese column name.

Two things deserve a comment because they are *survey-design* decisions, not code
style:

1. PESO_FINAL (the population expansion weight) is stored in the raw file with 8
   IMPLICIT decimals. The naive dictionary reader divides every numeric column by
   10**decimals, which turns a weight of ~700 into ~0.000007 and makes it useless.
   We therefore read PESO_FINAL with ZERO implicit decimals (see io.PofReader) and
   the value comes out on its correct scale: summing the per-UC weight reproduces
   ~69 million Brazilian households / ~207 million people (the 2018 population).

2. Monetary expenditure (V8000) must be (a) deflated to a common price reference
   using V8000_DEFLA and (b) annualized using FATOR_ANUALIZACAO, because different
   POF questionnaire blocks use different reference periods (monthly = 12, annual =
   1, etc.). Summing raw V8000 across blocks mixes monthly and annual money, which
   is not economically meaningful. The canonical debt value is therefore
   V8000_DEFLA * FATOR_ANUALIZACAO  ==> real annual reais.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Debt taxonomy — named by ECONOMIC FUNCTION, in English.
# ---------------------------------------------------------------------------
# Each POF product code (V9001) is a 7-digit string. The codes below were
# validated one-by-one against "Cadastro de Produtos.csv" (the official product
# registry) — see docs/01_dictionary_and_products.md.
@dataclass(frozen=True)
class DebtCategory:
    """A group of POF product codes that share an economic interpretation."""

    key: str                       # machine name, e.g. "interest_and_fees"
    label: str                     # human label, e.g. "Interest & banking fees"
    description: str               # one-line economic meaning
    codes: Dict[str, str]          # {product_code: official_pt_description}

    @property
    def code_list(self) -> List[str]:
        return list(self.codes.keys())


# NOTE on coverage: codes 5506001 / 5501602 (questionnaire block 55) are NOT
# present in DESPESA_INDIVIDUAL or DESPESA_COLETIVA in this extract; they are kept
# here for documentation completeness but contribute nothing. See the docs.
DEBT_CATEGORIES: Dict[str, DebtCategory] = {
    "interest_and_fees": DebtCategory(
        key="interest_and_fees",
        label="Interest & banking fees",
        description=(
            "Cost of credit: interest on overdraft, credit-card interest and loan "
            "interest. The clearest signal of the PRICE a household pays for debt."
        ),
        codes={
            "2600101": "JUROS DE CHEQUE ESPECIAL (overdraft interest)",
            "2600201": "JUROS DE CARTAO DE CREDITO (credit-card interest)",
            "4800201": "JUROS DE EMPRESTIMO (loan interest)",
            # The codes below also belong here economically but are commented out
            # in the original study; enable via config if desired:
            # "2600401": "SEGURO DE CARTAO DE CREDITO (credit-card insurance)",
            # "2600503": "MANUTENCAO DE CHEQUE ESPECIAL (overdraft maintenance)",
            # "2600801": "TAXA DE CARTAO ESPECIAL (special card fee)",
            # "2601103": "RENOVACAO DE CHEQUE ESPECIAL (overdraft renewal)",
            # "2601201": "TAXA DE DEVOLUCAO DE CHEQUE (bounced-cheque fee)",
            # "4800301": "SEGURO DE EMPRESTIMO (loan insurance)",
            # "5506001": "JUROS DE EMPRESTIMO (block 55 — absent in this extract)",
        },
    ),
    "principal_repayment": DebtCategory(
        key="principal_repayment",
        label="Principal repayment",
        description=(
            "Amortization of the principal: loan and mortgage instalments, student "
            "credit repayment. Captures the STOCK of debt being paid down."
        ),
        codes={
            # All commented out in the original study. Enable to analyse amortization.
            # "4800101": "PAGAMENTO DE EMPRESTIMO (loan repayment)",
            # "4800102": "EMPRESTIMO (PAGAMENTO) (loan repayment)",
            # "1000301": "PRESTACAO DO IMOVEL (mortgage instalment)",
            # "4801602": "CREDITO EDUCATIVO (PAGAMENTO) (student-loan repayment)",
            # "4801603": "PAGAMENTO DE CREDITO EDUCATIVO (student-loan repayment)",
        },
    ),
    "default_charges": DebtCategory(
        key="default_charges",
        label="Default charges",
        description=(
            "Charges that only arise when a household has defaulted: payment of a "
            "protested title, loan-related seizure. A marker of financial distress."
        ),
        codes={
            "4802201": "PAGAMENTO DE TITULO PROTESTADO (protested-title payment)",
            # "5501602": "PENHORA (EMPRESTIMO) (loan seizure — absent in this extract)",
        },
    ),
    "late_payment_penalties": DebtCategory(
        key="late_payment_penalties",
        label="Late-payment penalties",
        description=(
            "Interest, fines and surcharges added to ordinary bills (rent, condo, "
            "property tax, utilities) because they were paid late. Mild distress."
        ),
        codes={
            "1000201": "ADICIONAIS DO ALUGUEL (rent surcharges: interest/fine)",
            "1000801": "ADICIONAIS DE PRESTACAO DO IMOVEL (mortgage surcharges)",
            "1000901": "ADICIONAIS DE ALUGUEL DE GARAGEM (garage-rent surcharges)",
            "1001001": "ADICIONAIS DE CONDOMINIO (condo-fee surcharges)",
            "1001101": "ADICIONAIS DE IPTU (urban property-tax surcharges)",
            "1001201": "ADICIONAIS DE IPTR (rural property-tax surcharges)",
            "1203201": "JUROS E MULTA DE ENERGIA ELETRICA (electricity late fees)",
            "1203301": "JUROS E MULTA DE CONTA DE AGUA (water-bill late fees)",
        },
    ),
}


# ---------------------------------------------------------------------------
# Education category cut-points (years of study -> schooling band).
# ANOS_ESTUDO is integer 0..16 (16 = "16 or more"), per the dictionary.
# ---------------------------------------------------------------------------
EDUCATION_BINS: List[float] = [-0.01, 4, 8, 11, 16]
EDUCATION_LABELS: List[str] = [
    "None / Primary (0-4)",
    "Lower secondary (4-8)",
    "Upper secondary (8-11)",
    "Higher education (11+)",
]


@dataclass
class AnalysisConfig:
    """All tunable parameters for one run of the pipeline."""

    # --- paths (relative to the repository root by default) -----------------
    base_path: Path = field(default_factory=lambda: Path(".").resolve())
    txt_dirname: str = "Dados_20230713"
    parquet_dirname: str = "DadosParquet"
    dictionary_filename: str = "Dicionários de váriaveis.xlsx"
    product_registry_filename: str = "Cadastro de Produtos.csv"
    figures_dirname: str = "figures"
    outputs_dirname: str = "outputs"

    # --- which POF tables to load (TXT name -> Excel dictionary sheet) -------
    pof_tables: Dict[str, str] = field(default_factory=lambda: {
        "MORADOR.TXT": "Morador",
        "DESPESA_INDIVIDUAL.TXT": "Despesa Individual",
        "DESPESA_COLETIVA.TXT": "Despesa Coletiva",
    })

    # --- column names (kept in one place; POF codes are cryptic) ------------
    col_age: str = "V0403"                 # age in years
    col_sex: str = "V0404"                 # 1 = man, 2 = woman
    col_uc_role: str = "V0306"             # role in the consumption unit; 01 = head
    col_had_income: str = "V0407"          # had income/worked in last 12 months (1=yes)
    col_years_study: str = "ANOS_ESTUDO"   # derived years of schooling (0..16)
    col_instruction: str = "NIVEL_INSTRUCAO"  # derived schooling level (1..7)
    col_household_income: str = "RENDA_TOTAL"  # monthly gross UC income (R$)
    col_weight: str = "PESO_FINAL"         # population expansion weight (fixed scale)
    col_product: str = "V9001"             # expenditure product code
    col_value_nominal: str = "V8000"       # nominal expenditure (R$)
    col_value_deflated: str = "V8000_DEFLA"   # deflated expenditure (R$)
    col_annualization: str = "FATOR_ANUALIZACAO"  # 1/4/12/52 reference-period factor
    uc_keys: tuple = ("COD_UPA", "NUM_DOM", "NUM_UC")
    col_uf: str = "UF"

    # --- survey-design constants -------------------------------------------
    # V8000 sentinel for "ignored/undetermined" value is 9999999.99; with 2
    # implicit decimals it is read as 99999.9999. Rows at/above this are dropped.
    value_sentinel: float = 99999.9999
    head_role_code: str = "1"              # V0306 == "01" stripped -> "1"
    adult_min_age: int = 18

    # --- analytical options -------------------------------------------------
    use_deflated_value: bool = True        # use V8000_DEFLA (vs nominal V8000)
    annualize: bool = True                 # multiply by FATOR_ANUALIZACAO
    adults_with_income_only: bool = True   # restrict schooling agg to earners >=18
    apply_weights_descriptive: bool = True # weight means/medians/modes by PESO_FINAL
    apply_weights_regression: bool = True  # use weighted least squares / weighted logit
    drop_zero_income: bool = True          # remove UCs with RENDA_TOTAL <= 0
    ratio_winsor_quantile: float = 0.99    # winsorize debt/income ratio for OLS

    education_bins: List[float] = field(default_factory=lambda: list(EDUCATION_BINS))
    education_labels: List[str] = field(default_factory=lambda: list(EDUCATION_LABELS))

    random_state: int = 42

    # --- derived path helpers ----------------------------------------------
    @property
    def txt_dir(self) -> Path:
        return self.base_path / self.txt_dirname

    @property
    def parquet_dir(self) -> Path:
        return self.base_path / self.parquet_dirname

    @property
    def dictionary_path(self) -> Path:
        return self.base_path / self.dictionary_filename

    @property
    def product_registry_path(self) -> Path:
        return self.base_path / self.product_registry_filename

    @property
    def figures_dir(self) -> Path:
        return self.base_path / self.figures_dirname

    @property
    def outputs_dir(self) -> Path:
        return self.base_path / self.outputs_dirname

    @property
    def debt_categories(self) -> Dict[str, DebtCategory]:
        return DEBT_CATEGORIES

    def all_debt_codes(self) -> List[str]:
        """Every product code across all categories (deduplicated, order-preserving)."""
        seen: Dict[str, None] = {}
        for cat in DEBT_CATEGORIES.values():
            for code in cat.code_list:
                seen.setdefault(code, None)
        return list(seen.keys())

    def ensure_dirs(self) -> None:
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)


def default_config() -> AnalysisConfig:
    """Convenience factory used by the notebook."""
    return AnalysisConfig()

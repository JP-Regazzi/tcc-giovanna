"""
Full catalog of debt-related product codes -- including the ones commented out in
DEBT_CATEGORIES.

The per-code analysis (code_analysis.py) is asked to evaluate EVERY candidate debt
code, active or not, to discover which kinds of debt are relatively higher for
LOWER-education households. So we keep the complete list here, each tagged with the
category it belongs to and whether it is "active" (currently uncommented in
DEBT_CATEGORIES) or "candidate" (commented out / known absent).

Codes were validated against "Cadastro de Produtos.csv"; see docs/01.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .config import DEBT_CATEGORIES


@dataclass(frozen=True)
class CodeInfo:
    code: str
    label: str
    category: str
    active: bool  # True if currently uncommented in DEBT_CATEGORIES


# The full set, including commented-out candidates. `active` is reconciled with
# DEBT_CATEGORIES at import time so it never drifts out of sync.
_RAW: List[Dict] = [
    # interest_and_fees
    {"code": "2600101", "label": "JUROS DE CHEQUE ESPECIAL (overdraft interest)", "category": "interest_and_fees"},
    {"code": "2600201", "label": "JUROS DE CARTAO DE CREDITO (credit-card interest)", "category": "interest_and_fees"},
    {"code": "4800201", "label": "JUROS DE EMPRESTIMO (loan interest)", "category": "interest_and_fees"},
    {"code": "2600401", "label": "SEGURO DE CARTAO DE CREDITO (credit-card insurance)", "category": "interest_and_fees"},
    {"code": "2600503", "label": "MANUTENCAO DE CHEQUE ESPECIAL (overdraft maintenance)", "category": "interest_and_fees"},
    {"code": "2600801", "label": "TAXA DE CARTAO ESPECIAL (special card fee)", "category": "interest_and_fees"},
    {"code": "2601103", "label": "RENOVACAO DE CHEQUE ESPECIAL (overdraft renewal)", "category": "interest_and_fees"},
    {"code": "2601201", "label": "TAXA DE DEVOLUCAO DE CHEQUE (bounced-cheque fee)", "category": "interest_and_fees"},
    {"code": "4800301", "label": "SEGURO DE EMPRESTIMO (loan insurance)", "category": "interest_and_fees"},
    {"code": "5506001", "label": "JUROS DE EMPRESTIMO (block 55 - absent in extract)", "category": "interest_and_fees"},
    # principal_repayment
    {"code": "4800101", "label": "PAGAMENTO DE EMPRESTIMO (loan repayment)", "category": "principal_repayment"},
    {"code": "4800102", "label": "EMPRESTIMO (PAGAMENTO) (loan repayment)", "category": "principal_repayment"},
    {"code": "1000301", "label": "PRESTACAO DO IMOVEL (mortgage instalment)", "category": "principal_repayment"},
    {"code": "4801602", "label": "CREDITO EDUCATIVO (PAGAMENTO) (student-loan repayment)", "category": "principal_repayment"},
    {"code": "4801603", "label": "PAGAMENTO DE CREDITO EDUCATIVO (student-loan repayment)", "category": "principal_repayment"},
    # default_charges
    {"code": "4802201", "label": "PAGAMENTO DE TITULO PROTESTADO (protested-title payment)", "category": "default_charges"},
    {"code": "5501602", "label": "PENHORA (EMPRESTIMO) (loan seizure - absent in extract)", "category": "default_charges"},
    # late_payment_penalties
    {"code": "1000201", "label": "ADICIONAIS DO ALUGUEL (rent surcharges)", "category": "late_payment_penalties"},
    {"code": "1000801", "label": "ADICIONAIS DE PRESTACAO DO IMOVEL (mortgage surcharges)", "category": "late_payment_penalties"},
    {"code": "1000901", "label": "ADICIONAIS DE ALUGUEL DE GARAGEM (garage-rent surcharges)", "category": "late_payment_penalties"},
    {"code": "1001001", "label": "ADICIONAIS DE CONDOMINIO (condo-fee surcharges)", "category": "late_payment_penalties"},
    {"code": "1001101", "label": "ADICIONAIS DE IPTU (urban property-tax surcharges)", "category": "late_payment_penalties"},
    {"code": "1001201", "label": "ADICIONAIS DE IPTR (rural property-tax surcharges)", "category": "late_payment_penalties"},
    {"code": "1203201", "label": "JUROS E MULTA DE ENERGIA ELETRICA (electricity late fees)", "category": "late_payment_penalties"},
    {"code": "1203301", "label": "JUROS E MULTA DE CONTA DE AGUA (water-bill late fees)", "category": "late_payment_penalties"},
]


def _active_codes() -> set:
    active = set()
    for cat in DEBT_CATEGORIES.values():
        active.update(cat.code_list)
    return active


def full_catalog() -> List[CodeInfo]:
    """All candidate debt codes, tagged active/candidate from DEBT_CATEGORIES."""
    active = _active_codes()
    return [
        CodeInfo(code=r["code"], label=r["label"], category=r["category"],
                 active=r["code"] in active)
        for r in _RAW
    ]

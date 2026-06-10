"""
Econometric models linking household schooling to debt.

The dependent variables are highly skewed (most UCs have zero debt; those with
debt are very dispersed), which violates plain-OLS assumptions. We therefore use
a TWO-PART (hurdle) approach plus a relative-burden regression:

  Part 1 -- Weighted logistic regression on `has_debt` (0/1):
            does schooling change the PROBABILITY of carrying any debt? (access)

  Part 2 -- Weighted OLS on `log_debt` for UCs with debt > 0:
            given access, does schooling change the VOLUME of debt? (intensive margin)

  Part 3 -- Weighted OLS on `debt_to_income` (winsorized) for all UCs:
            does schooling change the SHARE of income committed to debt service?

The focal regressor is `education` -- the per-UC schooling summary produced by the
configured education_variable + education_method (see config / aggregation). All
models are population-weighted by PESO_FINAL when config.apply_weights_regression
is True, and use HC3-robust standard errors for the OLS parts. Controls: log
income, age, household size proxy, head's sex, and UF fixed effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from .config import AnalysisConfig


@dataclass
class ModelResult:
    """A compact, serializable summary of one fitted model."""

    name: str
    focal_term: str
    coef: float
    std_err: float
    p_value: float
    nobs: int
    extra: Dict[str, float]

    def as_row(self) -> Dict[str, float]:
        row = {
            "model": self.name,
            "focal_term": self.focal_term,
            "coef": self.coef,
            "std_err": self.std_err,
            "p_value": self.p_value,
            "nobs": self.nobs,
        }
        row.update(self.extra)
        return row


class DebtModels:
    """Fits the two-part + ratio models on the analytical dataset."""

    FOCAL = "education"
    _CONTROLS = "log_income + age_mean + n_members_aggregated + head_is_woman + C(UF)"
    _CONTROLS_NO_INCOME = "age_mean + n_members_aggregated + head_is_woman + C(UF)"

    def __init__(self, config: AnalysisConfig):
        self.config = config

    # -- public API ---------------------------------------------------------
    def fit_all(self, df: pd.DataFrame) -> List[ModelResult]:
        data = self._prepare(df)
        results = [self.fit_access(data), self.fit_volume(data), self.fit_burden(data)]
        return [r for r in results if r is not None]

    def fit_access(self, data: pd.DataFrame) -> Optional[ModelResult]:
        """Part 1 -- weighted logit on has_debt."""
        formula = f"has_debt ~ {self.FOCAL} + {self._CONTROLS}"
        try:
            kw = {"freq_weights": data["weight"]} if self._weighted else {}
            model = smf.glm(formula, data=data, family=sm.families.Binomial(), **kw).fit()
            return self._summarize(
                "logit_access", model,
                extra={"odds_ratio": float(np.exp(model.params[self.FOCAL]))},
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[models] access model failed: {exc}")
            return None

    def fit_volume(self, data: pd.DataFrame) -> Optional[ModelResult]:
        """Part 2 -- weighted OLS on log_debt | debt>0, HC3 errors."""
        sub = data.dropna(subset=["log_debt"]).copy()
        formula = f"log_debt ~ {self.FOCAL} + {self._CONTROLS}"
        return self._fit_ols("ols_log_volume", formula, sub, extra_keys=["rsquared"])

    def fit_burden(self, data: pd.DataFrame) -> Optional[ModelResult]:
        """Part 3 -- weighted OLS on winsorized debt_to_income, HC3 errors."""
        sub = data.copy()
        q = self.config.ratio_winsor_quantile
        cap = sub["debt_to_income"].quantile(q)
        sub["debt_to_income_w"] = sub["debt_to_income"].clip(upper=cap)
        # income is the denominator here, so it is NOT a control
        formula = f"debt_to_income_w ~ {self.FOCAL} + {self._CONTROLS_NO_INCOME}"
        return self._fit_ols("ols_burden", formula, sub, extra_keys=["rsquared"])

    # -- internals ----------------------------------------------------------
    @property
    def _weighted(self) -> bool:
        return self.config.apply_weights_regression

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        for col in [self.FOCAL, "log_income", "age_mean", "n_members_aggregated",
                    "head_is_woman", "debt_to_income", "log_debt", "has_debt", "weight"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")
        data["UF"] = data["UF"].astype(str)
        return data

    def _fit_ols(self, name: str, formula: str, data: pd.DataFrame,
                 extra_keys: List[str]) -> Optional[ModelResult]:
        try:
            if self._weighted:
                model = smf.wls(formula, data=data, weights=data["weight"]).fit(cov_type="HC3")
            else:
                model = smf.ols(formula, data=data).fit(cov_type="HC3")
            extra = {k: float(getattr(model, k)) for k in extra_keys if hasattr(model, k)}
            return self._summarize(name, model, extra=extra)
        except Exception as exc:  # noqa: BLE001
            print(f"[models] {name} failed: {exc}")
            return None

    def _summarize(self, name: str, model, extra: Dict[str, float]) -> ModelResult:
        return ModelResult(
            name=name,
            focal_term=self.FOCAL,
            coef=float(model.params[self.FOCAL]),
            std_err=float(model.bse[self.FOCAL]),
            p_value=float(model.pvalues[self.FOCAL]),
            nobs=int(model.nobs),
            extra=extra,
        )

    @staticmethod
    def to_frame(results: List[ModelResult]) -> pd.DataFrame:
        return pd.DataFrame([r.as_row() for r in results])

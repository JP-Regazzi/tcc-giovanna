"""
Reading layer: turn the raw IBGE POF files into tidy Polars DataFrames.

The POF microdata ships as fixed-width TXT files. The byte layout of each file
lives in the Excel dictionary, one sheet per table, listing for every variable its
start position, width and number of implicit decimals.

Two scaling subtleties (both were silent bugs in the original notebook):

1. Decimal point already present in the text. The dictionary declares "implicit
   decimals" for the canonical IBGE layout, but THIS extract already writes the
   decimal point literally (e.g. "3855.34", "690.88373818", "7.00"). Dividing such
   a value by 10**decimals shrinks it by 100x (money) or 1e8x (weights) -- exactly
   why household income used to read as ~R$38 and PESO_FINAL as ~1e-5. We probe
   each numeric field once and skip the division when it is already decimal.

2. PESO_FINAL is also pinned via an override so the population weight is never
   over-divided. With the fix the per-UC weights sum to ~69M households / ~207M
   people (Brazil, 2018).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import polars as pl

from .config import AnalysisConfig


# Columns whose stored value is already on the analytical scale (never divide).
_DECIMAL_OVERRIDE: Dict[str, int] = {
    "PESO_FINAL": 0,
    "PESO": 0,
}


@dataclass(frozen=True)
class FieldSpec:
    """One fixed-width field: name, 0-based start, width, decimal divisor."""

    name: str
    start: int
    width: int
    divisor: int


class DictionaryParser:
    """Reads the byte layout for a table from the Excel dictionary."""

    def __init__(self, dictionary_path: Path):
        self.dictionary_path = Path(dictionary_path)

    def layout(self, sheet: str) -> List[FieldSpec]:
        df = pd.read_excel(self.dictionary_path, sheet_name=sheet, dtype=str)

        header_idx = self._find_header_row(df)
        if header_idx is None:
            raise ValueError(f"Could not locate the layout header in sheet '{sheet}'.")

        df.columns = df.iloc[header_idx]
        df = df.iloc[header_idx + 1:].copy()
        df = df.dropna(subset=["Posição Inicial", "Código da variável"])
        df = df[df["Posição Inicial"].astype(str).str.isnumeric()]

        specs: List[FieldSpec] = []
        for _, row in df.iterrows():
            name = str(row["Código da variável"]).strip()
            start = int(row["Posição Inicial"]) - 1
            width = int(row["Tamanho"])
            divisor = self._divisor_for(name, row.get("Decimais", None))
            specs.append(FieldSpec(name=name, start=start, width=width, divisor=divisor))
        return specs

    @staticmethod
    def _find_header_row(df: pd.DataFrame) -> Optional[int]:
        for i, row in df.iterrows():
            if row.astype(str).str.contains("Posição Inicial", na=False).any():
                return df.index.get_loc(i)
        return None

    @staticmethod
    def _divisor_for(name: str, decimals_cell) -> int:
        if name in _DECIMAL_OVERRIDE:
            return 10 ** _DECIMAL_OVERRIDE[name]
        if pd.notna(decimals_cell) and str(decimals_cell).strip().isnumeric():
            return 10 ** int(float(str(decimals_cell).strip()))
        return 1


class PofReader:
    """Loads POF tables as Polars DataFrames, with a Parquet cache."""

    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.parser = DictionaryParser(config.dictionary_path)

    def load_all(self, verbose: bool = True) -> Dict[str, pl.DataFrame]:
        self.config.parquet_dir.mkdir(parents=True, exist_ok=True)
        tables: Dict[str, pl.DataFrame] = {}
        for txt_name, sheet in self.config.pof_tables.items():
            key = txt_name.split(".")[0]
            tables[key] = self.load_table(txt_name, sheet, verbose=verbose)
        return tables

    def load_table(self, txt_name: str, sheet: str, verbose: bool = True) -> pl.DataFrame:
        key = txt_name.split(".")[0]
        parquet_path = self.config.parquet_dir / f"{key}.parquet"

        if parquet_path.exists():
            df = pl.read_parquet(parquet_path)
            if verbose:
                print(f"[{key}] read from parquet cache -> {df.shape}")
            return df

        txt_path = self.config.txt_dir / txt_name
        if not txt_path.exists():
            raise FileNotFoundError(
                f"Neither parquet cache nor raw TXT found for '{key}'. "
                f"Looked for: {parquet_path} and {txt_path}"
            )

        specs = self.parser.layout(sheet)
        df = self._read_fixed_width(txt_path, specs)
        df.write_parquet(parquet_path)
        if verbose:
            print(f"[{key}] parsed from TXT -> {df.shape} (cached to parquet)")
        return df

    @staticmethod
    def _read_fixed_width(txt_path: Path, specs: List[FieldSpec]) -> pl.DataFrame:
        raw = pl.read_csv(
            txt_path,
            has_header=False,
            new_columns=["raw"],
            truncate_ragged_lines=True,
            quote_char=None,
        )

        def slice_expr(spec: FieldSpec) -> pl.Expr:
            s = pl.col("raw").str.slice(spec.start, spec.width).str.strip_chars()
            return pl.when(s == "").then(None).otherwise(s)

        sample = raw.head(2000)
        already_decimal: Dict[str, bool] = {}
        for spec in specs:
            if spec.divisor > 1:
                vals = sample.select(slice_expr(spec).alias("x")).drop_nulls()["x"]
                has_dot = vals.str.contains(r"\.").any() if vals.len() else False
                already_decimal[spec.name] = bool(has_dot)

        exprs: List[pl.Expr] = []
        for spec in specs:
            sliced = slice_expr(spec)
            if spec.divisor > 1 and not already_decimal.get(spec.name, False):
                col = (sliced.cast(pl.Float64, strict=False) / spec.divisor).alias(spec.name)
            elif spec.divisor > 1:
                col = sliced.cast(pl.Float64, strict=False).alias(spec.name)
            else:
                col = sliced.alias(spec.name)
            exprs.append(col)

        return raw.select(exprs)

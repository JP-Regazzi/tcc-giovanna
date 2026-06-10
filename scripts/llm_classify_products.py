#!/usr/bin/env python3
"""
Batch-classify products from `Cadastro de Produtos.csv` using OpenAI.

Writes incremental output to `candidatos_divida_llm.csv` with columns:
QUADRO, CODIGO, DESCRICAO, LABEL, JUSTIFICATIVA, PROMPT_SNIPPET

Usage:
  - Export `OPENAI_API_KEY` in your environment.
  - Optionally set `OPENAI_MODEL` (default: "gpt-4").
  - Run: python scripts/llm_classify_products.py --batch-size 100

Includes `--dry-run` to test parsing and batching without calling the API.
"""
import os
import argparse
import json
import time
import csv
from typing import List

import pandas as pd
from tqdm import tqdm

try:
    import openai
except Exception:
    openai = None

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4")
INPUT_PATH = "Cadastro de Produtos.csv"
OUTPUT_PATH = "candidatos_divida_llm.csv"


PROMPT_TEMPLATE = (
    "You are an expert data annotator for survey product codes.\n"
    "For each product below, decide whether it should be considered a household debt/payment (label as 'Yes', 'Maybe', or 'No').\n"
    "Return a JSON array with one object per product, strictly valid JSON, with the following keys:"
    " 'quadro', 'codigo', 'descricao', 'label', 'justification'.\n"
    "Justification must be 1-2 short sentences that explain why the label was chosen.\n"
    "Do NOT include any additional text outside the JSON array.\n\n"
    "Products:\n"
)


def read_products(path: str) -> pd.DataFrame:
    # file appears to be tab-separated with three columns: QUADRO, CODIGO, DESCRICAO
    df = pd.read_csv(path, sep="\t", header=None, names=["QUADRO", "CODIGO", "DESCRICAO"], dtype=str, engine="python")
    df = df.fillna("")
    return df


def chunk_rows(rows: List[dict], batch_size: int):
    for i in range(0, len(rows), batch_size):
        yield rows[i : i + batch_size]


def build_prompt(batch: List[dict]) -> str:
    items_text = []
    for r in batch:
        items_text.append(f"- QUADRO: {r['QUADRO']} | CODIGO: {r['CODIGO']} | DESCRICAO: {r['DESCRICAO']}")
    prompt = PROMPT_TEMPLATE + "\n".join(items_text)
    return prompt


def call_openai_chat(prompt: str, model: str = DEFAULT_MODEL, max_retries: int = 5) -> str:
    if openai is None:
        raise RuntimeError("openai package not installed")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in environment")
    openai.api_key = api_key

    for attempt in range(max_retries):
        try:
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1500,
            )
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            wait = 2 ** attempt
            print(f"OpenAI call failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("OpenAI request failed after retries")


def parse_model_json(output: str):
    # Expect output to be a JSON array; try to load directly.
    output = output.strip()
    try:
        data = json.loads(output)
        return data
    except Exception:
        # Attempt to locate first/last bracketed JSON array
        start = output.find("[")
        end = output.rfind("]")
        if start != -1 and end != -1:
            try:
                data = json.loads(output[start : end + 1])
                return data
            except Exception:
                pass
    raise ValueError("Could not parse JSON from model output")


def write_rows(rows: List[dict], output_path: str, write_header: bool = False):
    fieldnames = ["QUADRO", "CODIGO", "DESCRICAO", "LABEL", "JUSTIFICATIVA", "PROMPT_SNIPPET"]
    mode = "a" if os.path.exists(output_path) else "w"
    with open(output_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def dry_label(item: dict):
    text = item["DESCRICAO"].lower()
    if "juros" in text or "emprestimo" in text or "parcela" in text or "consorci" in text or "financi" in text:
        return "Yes", "Description explicitly mentions loan/interest/parcel/consortium/financing."
    if "multa" in text or "juros" in text:
        return "Maybe", "May be related to penalties or interest linked to payments."
    return "No", "Not related to debt payments based on description."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-index", type=int, default=0, help="Row index to start from (0-based)")
    args = parser.parse_args()

    df = read_products(INPUT_PATH)
    all_rows = df.to_dict(orient="records")

    rows_to_process = all_rows[args.start_index :]
    print(f"Loaded {len(all_rows)} products; processing {len(rows_to_process)} starting at index {args.start_index}.")

    batches = list(chunk_rows(rows_to_process, args.batch_size))

    for batch_idx, batch in enumerate(tqdm(batches, desc="Batches")):
        prompt = build_prompt(batch)
        prompt_snippet = prompt[:1000]

        if args.dry_run:
            # simulate labels
            labeled = []
            for item in batch:
                label, just = dry_label(item)
                labeled.append({
                    "QUADRO": item["QUADRO"],
                    "CODIGO": item["CODIGO"],
                    "DESCRICAO": item["DESCRICAO"],
                    "LABEL": label,
                    "JUSTIFICATIVA": just,
                    "PROMPT_SNIPPET": prompt_snippet,
                })
            write_rows(labeled, OUTPUT_PATH)
            continue

        model_output = call_openai_chat(prompt, model=DEFAULT_MODEL)
        try:
            parsed = parse_model_json(model_output)
        except Exception as e:
            print(f"Failed to parse model output for batch {batch_idx}: {e}")
            print("Saving no-op rows for this batch to allow re-run from this point.")
            # write placeholder No answers to avoid losing progress
            placeholder = []
            for item in batch:
                placeholder.append({
                    "QUADRO": item["QUADRO"],
                    "CODIGO": item["CODIGO"],
                    "DESCRICAO": item["DESCRICAO"],
                    "LABEL": "Maybe",
                    "JUSTIFICATIVA": "Parsing error - needs human review.",
                    "PROMPT_SNIPPET": prompt_snippet,
                })
            write_rows(placeholder, OUTPUT_PATH)
            continue

        # parsed expected to be list of dicts
        out_rows = []
        for obj in parsed:
            out_rows.append({
                "QUADRO": obj.get("quadro") or obj.get("QUADRO") or "",
                "CODIGO": obj.get("codigo") or obj.get("CODIGO") or "",
                "DESCRICAO": obj.get("descricao") or obj.get("DESCRICAO") or "",
                "LABEL": obj.get("label") or obj.get("LABEL") or "",
                "JUSTIFICATIVA": obj.get("justification") or obj.get("JUSTIFICATION") or obj.get("justificativa") or obj.get("JUSTIFICATIVA") or "",
                "PROMPT_SNIPPET": prompt_snippet,
            })

        write_rows(out_rows, OUTPUT_PATH)


if __name__ == "__main__":
    main()

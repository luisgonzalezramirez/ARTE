from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def is_missing(x) -> bool:
    return pd.isna(x) or str(x).strip() == ""


def format_value(value, fmt: str) -> str:
    if is_missing(value):
        width = int(fmt[1:].split(".")[0]) if "." in fmt else int(fmt[1:])
        return " " * width

    kind = fmt[0].upper()

    if kind == "A":
        width = int(fmt[1:])
        return str(value)[:width].ljust(width)

    if kind == "I":
        width = int(fmt[1:])
        return f"{int(float(value)):>{width}d}"

    if kind == "F":
        width, dec = fmt[1:].split(".")
        width = int(width)
        dec = int(dec)
        return f"{float(value):>{width}.{dec}f}"

    raise ValueError(f"Unsupported CDS format: {fmt}")


def format_row(row: pd.Series, columns: list[dict]) -> str:
    fields = []

    for col in columns:
        csv_col = col["column"]
        fmt = col["format"]
        fields.append(format_value(row[csv_col], fmt))

    return " ".join(fields)


def required_columns(config: dict) -> list[str]:
    return sorted({c["column"] for c in config["columns"]})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a CDS fixed-width .dat file from a CSV file and YAML configuration."
    )
    parser.add_argument("csv", help="Input CSV file.")
    parser.add_argument("yaml", help="CDS YAML configuration file.")
    parser.add_argument("-o", "--output", required=True, help="Output .dat file.")
    parser.add_argument("--nrows", type=int, default=None, help="Use only the first N rows.")

    args = parser.parse_args()

    with open(args.yaml, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    df = pd.read_csv(args.csv)

    if args.nrows is not None:
        df = df.head(args.nrows)

    missing = [c for c in required_columns(config) if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    lines = [format_row(row, config["columns"]) for _, row in df.iterrows()]

    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Generated: {args.output}")
    print(f"Records: {len(lines)}")
    print(f"LRECL: {max(len(line) for line in lines) if lines else 0}")


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pn
import yaml


def is_missing(x) -> bool:
    return pn.isna(x) or str(x).strip() == ""


def count_decimals(x) -> int:
    if is_missing(x):
        return 0

    s = str(x).strip()

    if "e" in s.lower():
        return 5

    if "." not in s:
        return 0

    return len(s.split(".")[1].rstrip("0"))


def infer_string_format(series: pn.Series) -> str:
    vals = series.dropna().astype(str)
    width = max((len(v) for v in vals), default=1)
    return f"A{width}"


def infer_integer_format(series: pn.Series) -> str:
    vals = pn.to_numeric(series, errors="coerce")
    vals = vals[np.isfinite(vals)]

    if len(vals) == 0:
        return "I1"

    width = max(len(str(int(abs(v)))) for v in vals)

    if (vals < 0).any():
        width += 1

    return f"I{width}"


def infer_float_format(series: pn.Series, scientific_threshold: float = 1e6) -> str:
    vals = pn.to_numeric(series, errors="coerce")
    vals = vals[np.isfinite(vals)]

    if len(vals) == 0:
        return "F1.0"

    max_abs = float(np.nanmax(np.abs(vals)))

    if max_abs >= scientific_threshold or (0 < max_abs < 1e-4):
        return "E12.5"

    decimals = max(count_decimals(v) for v in series)

    formatted = [f"{float(v):.{decimals}f}" for v in vals]
    width = max(len(v) for v in formatted)

    return f"F{width}.{decimals}"


def infer_cds_format(series: pn.Series) -> str:
    vals = series.dropna()

    if len(vals) == 0:
        return "A1"

    numeric = pn.to_numeric(vals, errors="coerce")

    if numeric.notna().all():
        if np.all(np.isclose(numeric, np.round(numeric))):
            return infer_integer_format(vals)

        return infer_float_format(vals)

    return infer_string_format(vals)


def cds_format_width(fmt: str) -> int:
    kind = fmt[0].upper()

    if kind in {"A", "I"}:
        return int(fmt[1:])

    if kind in {"F", "E"}:
        return int(fmt[1:].split(".")[0])

    raise ValueError(f"Unsupported CDS format: {fmt}")


def format_value(value, fmt: str) -> str:
    width = cds_format_width(fmt)

    if is_missing(value):
        return " " * width

    kind = fmt[0].upper()

    if kind == "A":
        return str(value)[:width].ljust(width)

    if kind == "I":
        return f"{int(float(value)):>{width}d}"

    if kind == "F":
        width, dec = fmt[1:].split(".")
        return f"{float(value):>{int(width)}.{int(dec)}f}"

    if kind == "E":
        width, dec = fmt[1:].split(".")
        return f"{float(value):>{int(width)}.{int(dec)}E}"

    raise ValueError(f"Unsupported CDS format: {fmt}")


def infer_formats(df: pn.DataFrame, config: dict) -> None:
    for col in config["columns"]:
        if "format" not in col or col["format"] in {None, "auto"}:
            col["format"] = infer_cds_format(df[col["column"]])


def format_row(row: pn.Series, columns: list[dict]) -> str:
    fields = []

    for col in columns:
        csv_col = col["column"]
        fmt = col["format"]
        fields.append(format_value(row[csv_col], fmt))

    return " ".join(fields)


def required_coordinate_columns(config: dict) -> list[str]:
    coord = config.get("coordinates", {})

    if not coord:
        raise ValueError(
            "Missing required 'coordinates' block in YAML. "
            "CDS tables should define RA/Dec columns."
        )

    missing_keys = [k for k in ["ra_column", "dec_column"] if k not in coord]

    if missing_keys:
        raise ValueError(f"Missing keys in coordinates block: {missing_keys}")

    return [coord["ra_column"], coord["dec_column"]]

def required_columns(config: dict) -> list[str]:
    cols = {c["column"] for c in config["columns"]}

    for c in required_coordinate_columns(config):
        cols.add(c)

    return sorted(cols)


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

    df_raw = pn.read_csv(args.csv, dtype=str)
    df = df_raw.copy()

    if args.nrows is not None:
        df = df.head(args.nrows)

    missing = [c for c in required_columns(config) if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    infer_formats(df, config)

    lines = [format_row(row, config["columns"]) for _, row in df.iterrows()]

    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Generated: {args.output}")
    print(f"Records: {len(lines)}")
    print(f"LRECL: {max(len(line) for line in lines) if lines else 0}")
    print("Inferred formats:")
    for col in config["columns"]:
        print(f"  {col['label']:<12s} {col['format']}")


if __name__ == "__main__":
    main()
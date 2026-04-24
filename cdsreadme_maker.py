from __future__ import annotations

import argparse
from pathlib import Path
import textwrap

import numpy as np
import pandas as pn

import yaml


def cds_format_width(fmt: str) -> int:
    kind = fmt[0].upper()

    if kind in {"A", "I"}:
        return int(fmt[1:])

    if kind in {"F", "E"}:
        return int(fmt[1:].split(".")[0])

    raise ValueError(f"Unsupported CDS format: {fmt}")

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


def infer_formats(df: pn.DataFrame, config: dict) -> None:
    for col in config["columns"]:
        if "format" not in col or col["format"] in {None, "auto"}:
            col["format"] = infer_cds_format(df[col["column"]])

def compute_byte_ranges(columns: list[dict]) -> list[dict]:
    out = []
    pos = 1

    for col in columns:
        width = cds_format_width(col["format"])
        start = pos
        end = pos + width - 1

        new = dict(col)
        new["byte_start"] = start
        new["byte_end"] = end
        out.append(new)

        pos = end + 2  # one separator space

    return out


def count_records(dat_file: Path) -> int:
    if not dat_file.exists():
        return 0

    with open(dat_file, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.rstrip("\n"))


def get_lrecl(dat_file: Path) -> int:
    if not dat_file.exists():
        return 0

    with open(dat_file, "r", encoding="utf-8") as f:
        return max((len(line.rstrip("\n")) for line in f), default=0)


def wrap_block(text: str, width: int = 80, indent: str = "  ") -> str:
    paragraphs = str(text).split("\n")
    lines = []

    for p in paragraphs:
        if p.strip() == "":
            lines.append("")
        else:
            lines.extend(
                textwrap.wrap(
                    p.strip(),
                    width=width,
                    initial_indent=indent,
                    subsequent_indent=indent,
                )
            )

    return "\n".join(lines)


def make_file_summary(config: dict, dat_file: Path) -> str:
    readme_lrecl = 80
    dat_lrecl = get_lrecl(dat_file)
    dat_records = count_records(dat_file)

    dat_name = dat_file.name
    explanation = config["file"].get("explanation", "Data table")

    return f"""File Summary:
--------------------------------------------------------------------------------
 FileName         Lrecl  Records  Explanations
--------------------------------------------------------------------------------
 ReadMe              {readme_lrecl:<5d}   .   This file
 {dat_name:<14s} {dat_lrecl:>5d} {dat_records:>7d}   {explanation}
--------------------------------------------------------------------------------
"""


def make_byte_by_byte(config: dict, dat_file: Path) -> str:
    cols = compute_byte_ranges(config["columns"])

    lines = []
    lines.append(f"Byte-by-byte Description of file: {dat_file.name}")
    lines.append("--------------------------------------------------------------------------------")
    lines.append("    Bytes   Format  Units  Label                     Explanations")
    lines.append("--------------------------------------------------------------------------------")

    for c in cols:
        b = f"{c['byte_start']:>4d}-{c['byte_end']:>4d}"
        fmt = c["format"]
        unit = c.get("unit", "---")
        label = c["label"]
        explanation = c.get("description", "")

        first = f"{b}   {fmt:<7s} {unit:<6s} {label:<25s} {explanation}"
        wrapped = textwrap.wrap(
            first,
            width=80,
            subsequent_indent=" " * 51,
            break_long_words=False,
        )
        lines.extend(wrapped)

    lines.append("--------------------------------------------------------------------------------")

    return "\n".join(lines)


def make_notes(config: dict) -> str:
    notes = config.get("notes", [])

    if not notes:
        return ""

    blocks = []

    for note in notes:
        title = note["title"]
        text = note.get("text", "")
        blocks.append(f"{title}:\n{wrap_block(text)}")

        codes = note.get("codes", [])
        if codes:
            code_lines = ["", "  The following codes are used:", ""]
            for c in codes:
                code_lines.append(f"  {c['code']:<8s} = {c['description']}")
            blocks.append("\n".join(code_lines))

    return "\n\n".join(blocks)


def make_references(config: dict) -> str:
    refs = config.get("references", [])

    if not refs:
        return ""

    lines = []
    lines.append("References:")
    lines.append("=" * 80)

    for r in refs:
        bibcode = r.get("bibcode", "")
        text = r.get("text", "")
        lines.append(f"{bibcode:<19s} {text}")

    return "\n".join(lines)

def validate_coordinates_block(config: dict) -> None:
    if "coordinates" not in config:
        raise ValueError(
            "Missing required 'coordinates' block in YAML. "
            "CDS catalogues should define RA and Dec columns."
        )

    coord = config["coordinates"]

    required_keys = ["ra_column", "dec_column"]
    missing_keys = [k for k in required_keys if k not in coord]

    if missing_keys:
        raise ValueError(f"Missing keys in coordinates block: {missing_keys}")

    column_names = {c["column"] for c in config["columns"]}

    missing_columns = [
        coord["ra_column"],
        coord["dec_column"],
    ]

    missing_columns = [c for c in missing_columns if c not in column_names]

    if missing_columns:
        raise ValueError(
            "Coordinate columns are defined in 'coordinates' but are missing "
            f"from the byte-by-byte columns list: {missing_columns}"
        )

def build_readme(config: dict, dat_file: Path) -> str:
    validate_coordinates_block(config)

    title = config["catalog"]["title"]
    authors = config["catalog"]["authors"]
    keywords = config["catalog"].get("keywords", [])
    objects = config.get("objects", [])

    lines = []

    lines.append(config["catalog"].get("header", "").rstrip())
    lines.append("=" * 80)
    lines.append(title)
    lines.append(f"    {authors}")
    lines.append("=" * 80)

    if keywords:
        lines.append("Keywords:")
        for k in keywords:
            lines.append(f"  {k}")
        lines.append("")

    if objects:
        lines.append("Objects:")
        lines.append("    -----------------------------------------")
        lines.append("       RA   (2000)   DE    Designation(s)")
        lines.append("    -----------------------------------------")
        for obj in objects:
            lines.append(
                f"      {obj['ra']:>7}       {obj['dec']:>7}   {obj['name']}"
            )
        lines.append("")

    lines.append("Abstract:")
    lines.append(wrap_block(config["catalog"].get("abstract", "")))
    lines.append("")

    lines.append("Description:")
    lines.append(wrap_block(config["catalog"].get("description", "")))
    lines.append("")

    lines.append(make_file_summary(config, dat_file))
    lines.append(make_byte_by_byte(config, dat_file))
    lines.append("")

    notes = make_notes(config)
    if notes:
        lines.append(notes)
        lines.append("")

    refs = make_references(config)
    if refs:
        lines.append(refs)
        lines.append("")

    lines.append("=" * 80)
    lines.append(config["catalog"].get("prepared_by", "     (prepared by author / ARTE)"))

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a CDS-style ReadMe from a YAML configuration and .dat file."
    )
    parser.add_argument("csv", help="Input CSV file used to infer CDS formats.")
    parser.add_argument("yaml", help="CDS YAML configuration file.")
    parser.add_argument("dat", help="Input .dat file.")
    parser.add_argument("-o", "--output", default="ReadMe", help="Output ReadMe file.")

    args = parser.parse_args()

    with open(args.yaml, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    df = pn.read_csv(args.csv, dtype=str)

    missing = [c["column"] for c in config["columns"] if c["column"] not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    infer_formats(df, config)

    dat_file = Path(args.dat)
    text = build_readme(config, dat_file)

    Path(args.output).write_text(text, encoding="utf-8")

    print(f"Generated: {args.output}")
    print(f"DAT file: {dat_file}")
    print(f"LRECL: {get_lrecl(dat_file)}")
    print(f"Records: {count_records(dat_file)}")


if __name__ == "__main__":
    main()
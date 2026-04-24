from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pn
import yaml


# ============================================================
# GENERIC UTILITIES
# ============================================================
def is_missing(x) -> bool:
    return pn.isna(x) or str(x).strip() == ""


def latex_escape(s: str) -> str:
    if is_missing(s):
        return ""

    s = str(s)
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }

    for k, v in repl.items():
        s = s.replace(k, v)

    return s


# ============================================================
# NUMERIC AND ERROR UTILITIES
# ============================================================
def first_nonzero_decimal_position(x: float) -> int:
    if x is None or not np.isfinite(x) or x <= 0:
        return 0

    s = f"{float(x):.12f}".split(".")[1]

    for i, ch in enumerate(s, start=1):
        if ch != "0":
            return i

    return 0


def decimals_from_error(err: float) -> int:
    if err is None or not np.isfinite(err) or err <= 0:
        return 0

    s = f"{err:.12f}".rstrip("0").rstrip(".")

    return len(s.split(".")[1]) if "." in s else 0


def integer_digits(x: float) -> int:
    if x is None or not np.isfinite(x):
        return 0

    x = abs(float(x))

    if x < 1:
        return 1

    return len(str(int(x)))


def get_positive_scaled_values(
    df: pn.DataFrame,
    columns: list[str],
    scale: float = 1.0,
) -> pn.Series:
    vals = []

    for col in columns:
        s = pn.to_numeric(df[col], errors="coerce")
        vals.append(s)

    out = pn.concat(vals, ignore_index=True)
    out = out[np.isfinite(out) & (out > 0)] * scale

    return out


def get_global_decimals_from_error_columns(
    df: pn.DataFrame,
    error_columns: list[str],
    scale: float = 1.0,
) -> int:
    vals = get_positive_scaled_values(df, error_columns, scale=scale)

    if len(vals) == 0:
        return 0

    return first_nonzero_decimal_position(float(vals.min()))


def get_max_error_integer_digits(
    df: pn.DataFrame,
    error_columns: list[str],
    scale: float = 1.0,
) -> int:
    vals = get_positive_scaled_values(df, error_columns, scale=scale)

    if len(vals) == 0:
        return 0

    return max(integer_digits(float(v)) for v in vals)


def make_phantom_for_error(err: float, max_digits: int) -> str:
    d = integer_digits(err)
    nphantom = max(0, max_digits - d)

    if nphantom <= 0:
        return ""

    return r"\hphantom{" + "0" * nphantom + "}"


# ============================================================
# SCALE AND SCIENTIFIC-FACTOR UTILITIES
# ============================================================
def strip_outer_math_dollars(s: str) -> str:
    s = str(s).strip()

    if s.startswith("$") and s.endswith("$") and len(s) >= 2:
        return s[1:-1]

    return s


def scale_to_power_of_ten(scale: float) -> int | None:
    if scale is None or scale <= 0:
        return None

    exponent = -np.log10(scale)

    if np.isclose(exponent, round(exponent)):
        return int(round(exponent))

    return None


def apply_scale_factor_to_unit(unit: str, scale: float) -> str:
    exponent = scale_to_power_of_ten(scale)

    if exponent is None or exponent == 0:
        return unit

    unit = "" if unit is None else str(unit).strip()

    if "$" in unit:
        raise ValueError(
            f"Unit '{unit}' should not contain '$'. "
            "ARTE handles math mode automatically."
        )

    # Remove outer $ if present
    if unit.startswith("$") and unit.endswith("$"):
        unit = unit[1:-1]

    if unit.startswith("(") and unit.endswith(")"):
        inside = unit[1:-1]
    else:
        inside = unit

    if unit == "":
        return rf"($10^{{{exponent}}}$)"

    if unit.startswith("(") and unit.endswith(")"):
        inside = strip_outer_math_dollars(unit[1:-1])
        return rf"($10^{{{exponent}}}\,{inside}$)"

    inside = strip_outer_math_dollars(unit)
    return rf"$10^{{{exponent}}}\,{inside}$"


def apply_scientific_factor_to_unit(unit: str, exponent: int) -> str:
    unit = "" if unit is None else str(unit).strip()

    if unit == "":
        return rf"($10^{{{exponent}}}$)"

    if unit.startswith("(") and unit.endswith(")"):
        inside = strip_outer_math_dollars(unit[1:-1])
        return rf"($10^{{{exponent}}}\,{inside}$)"

    inside = strip_outer_math_dollars(unit)
    return rf"$10^{{{exponent}}}\,{inside}$"


def common_scientific_exponent_from_columns(
    df: pn.DataFrame,
    columns: list[str],
) -> int:
    vals = []

    for col in columns:
        s = pn.to_numeric(df[col], errors="coerce")
        vals.append(s)

    vals = pn.concat(vals, ignore_index=True)
    vals = vals[np.isfinite(vals) & (vals != 0)]

    if len(vals) == 0:
        return 0

    median_abs = float(np.nanmedian(np.abs(vals)))

    if median_abs <= 0 or not np.isfinite(median_abs):
        return 0

    return int(np.floor(np.log10(median_abs)))


def apply_scientific_factor_to_unit(unit: str, exponent: int) -> str:
    if unit is None:
        unit = ""

    unit = str(unit)

    if unit.strip() == "":
        return rf"($10^{{{exponent}}}$)"

    unit_clean = unit.strip()

    if unit_clean.startswith("(") and unit_clean.endswith(")"):
        inside = unit_clean[1:-1]
        return rf"($10^{{{exponent}}}$ {inside})"

    return rf"$10^{{{exponent}}}$ {unit_clean}"


# ============================================================
# DECIMAL FORMAT HELPERS
# ============================================================
def get_decimals_for_symmetric_error(
    r: pn.Series,
    cfg: dict,
    column_props: dict,
) -> int:
    err = r[cfg["error_column"]]
    base_scale = float(cfg.get("scale", 1.0))
    scientific_scale = column_props.get(cfg["id"], {}).get("scientific_scale", 1.0)
    scale = base_scale * scientific_scale

    mode = cfg.get("decimals", 0)

    if mode == "from_error":
        return decimals_from_error(float(err) * scale) if not is_missing(err) else 0

    if mode == "global_from_error":
        return column_props[cfg["id"]]["decimals"]

    return int(mode)


def get_decimals_for_asymmetric_error(
    r: pn.Series,
    cfg: dict,
    column_props: dict,
) -> int:
    err_up = r[cfg["error_up_column"]]
    err_down = r[cfg["error_down_column"]]
    base_scale = float(cfg.get("scale", 1.0))
    scientific_scale = column_props.get(cfg["id"], {}).get("scientific_scale", 1.0)
    scale = base_scale * scientific_scale

    mode = cfg.get("decimals", 0)

    if mode == "from_error":
        vals = []

        if not is_missing(err_up):
            vals.append(float(err_up) * scale)

        if not is_missing(err_down):
            vals.append(float(err_down) * scale)

        vals = [v for v in vals if np.isfinite(v) and v > 0]

        return decimals_from_error(min(vals)) if vals else 0

    if mode == "global_from_error":
        return column_props[cfg["id"]]["decimals"]

    return int(mode)


# ============================================================
# CELL FORMATTERS
# ============================================================
def format_string(r: pn.Series, cfg: dict) -> str:
    return latex_escape(r[cfg["column"]])


def format_float(r: pn.Series, cfg: dict) -> str:
    x = r[cfg["column"]]

    if is_missing(x):
        return ""

    scale = float(cfg.get("scale", 1.0))
    nd = cfg.get("decimals", None)
    math_mode = bool(cfg.get("math_mode", False))

    x = float(x) * scale

    if nd is None:
        out = f"{x:g}"
    else:
        out = f"{x:.{int(nd)}f}"

    return rf"${out}$" if math_mode else out


def format_limit_value(val: float, cfg: dict, nd: int) -> str:
    limit_symbol = cfg.get("limit_symbol", "<")
    return rf"${limit_symbol}{val:.{nd}f}$"


def format_value_error(
    r: pn.Series,
    cfg: dict,
    column_props: dict,
) -> str:
    val = r[cfg["value_column"]]
    err = r[cfg["error_column"]]

    if is_missing(val):
        return ""

    base_scale = float(cfg.get("scale", 1.0))
    scientific_scale = column_props.get(cfg["id"], {}).get("scientific_scale", 1.0)
    scale = base_scale * scientific_scale
    val = float(val) * scale

    nd = get_decimals_for_symmetric_error(r, cfg, column_props)

    if bool(cfg.get("round_to_integer", False)):
        nd = 0

    if "limit_column" in cfg and not is_missing(r[cfg["limit_column"]]):
        return format_limit_value(val, cfg, nd)

    if is_missing(err) or float(err) <= 0:
        return rf"${val:.{nd}f}$"

    err = float(err) * scale

    phantom = ""
    if cfg.get("align_uncertainty", False):
        max_digits = column_props[cfg["id"]]["max_error_integer_digits"]
        phantom = make_phantom_for_error(err, max_digits)

    return rf"${val:.{nd}f} \pm{phantom}{err:.{nd}f}$"


def format_value_error_asymmetric(
    r: pn.Series,
    cfg: dict,
    column_props: dict,
) -> str:
    val = r[cfg["value_column"]]
    err_up = r[cfg["error_up_column"]]
    err_down = r[cfg["error_down_column"]]

    if is_missing(val):
        return ""

    base_scale = float(cfg.get("scale", 1.0))
    scientific_scale = column_props.get(cfg["id"], {}).get("scientific_scale", 1.0)
    scale = base_scale * scientific_scale
    val = float(val) * scale

    nd = get_decimals_for_asymmetric_error(r, cfg, column_props)

    if bool(cfg.get("round_to_integer", False)):
        nd = 0

    if "limit_column" in cfg and not is_missing(r[cfg["limit_column"]]):
        return format_limit_value(val, cfg, nd)

    if (
        is_missing(err_up)
        or is_missing(err_down)
        or float(err_up) <= 0
        or float(err_down) <= 0
    ):
        return rf"${val:.{nd}f}$"

    err_up = float(err_up) * scale
    err_down = float(err_down) * scale

    phantom_up = ""
    phantom_down = ""

    if cfg.get("align_uncertainty", False):
        max_digits = column_props[cfg["id"]]["max_error_integer_digits"]
        phantom_up = make_phantom_for_error(err_up, max_digits)
        phantom_down = make_phantom_for_error(err_down, max_digits)

    return (
        rf"${val:.{nd}f}"
        rf"^{{+{phantom_up}{err_up:.{nd}f}}}"
        rf"_{{-{phantom_down}{err_down:.{nd}f}}}$"
    )


def format_cell(
    r: pn.Series,
    cfg: dict,
    column_props: dict,
) -> str:
    kind = cfg["type"]

    if kind == "string":
        return format_string(r, cfg)

    if kind == "float":
        return format_float(r, cfg)

    if kind == "value_error":
        return format_value_error(r, cfg, column_props)

    if kind == "value_error_asymmetric":
        return format_value_error_asymmetric(r, cfg, column_props)

    raise ValueError(f"Unknown column type: {kind}")


# ============================================================
# CONFIGURATION HELPERS
# ============================================================
def required_columns(config: dict) -> list[str]:
    cols = []

    for c in config["columns"]:
        t = c["type"]

        if t in {"string", "float"}:
            cols.append(c["column"])

        elif t == "value_error":
            cols.extend([c["value_column"], c["error_column"]])

            if "limit_column" in c:
                cols.append(c["limit_column"])

        elif t == "value_error_asymmetric":
            cols.extend(
                [
                    c["value_column"],
                    c["error_up_column"],
                    c["error_down_column"],
                ]
            )

            if "limit_column" in c:
                cols.append(c["limit_column"])

        else:
            raise ValueError(f"Unknown column type: {t}")

    return sorted(set(cols))


def compute_global_column_properties(
    df: pn.DataFrame,
    config: dict,
) -> dict:
    out = {}

    for c in config["columns"]:
        t = c["type"]

        if t not in {"value_error", "value_error_asymmetric"}:
            continue

        props = {}
        scale = float(c.get("scale", 1.0))

        if t == "value_error":
            error_columns = [c["error_column"]]
        else:
            error_columns = [
                c["error_up_column"],
                c["error_down_column"],
            ]

        if c.get("scientific_factor", False):
            sci_columns = [c["value_column"]] + error_columns

            exponent = common_scientific_exponent_from_columns(
                df=df,
                columns=sci_columns,
            )

            props["scientific_exponent"] = exponent
            props["scientific_scale"] = 10.0 ** (-exponent)

        else:
            props["scientific_exponent"] = None
            props["scientific_scale"] = 1.0

        total_scale = scale * props["scientific_scale"]

        if c.get("decimals") == "global_from_error":
            props["decimals"] = get_global_decimals_from_error_columns(
                df=df,
                error_columns=error_columns,
                scale=total_scale,
            )

        if c.get("align_uncertainty", False):
            props["max_error_integer_digits"] = get_max_error_integer_digits(
                df=df,
                error_columns=error_columns,
                scale=total_scale,
            )

        out[c["id"]] = props

    return out


def infer_alignment(config: dict) -> str:
    align = []

    for c in config["columns"]:
        if "align" in c:
            align.append(c["align"])
            continue

        if c["type"] == "string":
            align.append("l")

        elif c["type"] in {"float", "value_error", "value_error_asymmetric"}:
            align.append("r")

        else:
            align.append("l")

    return "".join(align)


# ============================================================
# TABLE BUILDING
# ============================================================
def build_header(config: dict) -> str:
    table = config["table"]

    alignment = table.get("alignment", infer_alignment(config))
    caption = table["caption"]
    label = table["label"]

    names = [c["header"] for c in config["columns"]]

    units = []

    for c in config["columns"]:
        unit = c.get("unit", "")

        if "scale" in c and c.get("show_scale_in_unit", True):
            unit = apply_scale_factor_to_unit(unit, float(c["scale"]))

        units.append(unit)

    ncols = len(names)

    header_line = " & ".join(names) + r" \\"
    unit_line = " & ".join(units) + r" \\"

    return rf"""
\begin{{center}}
\{table.get("font_size", "footnotesize")}
\begin{{longtable}}{{{alignment}}}
\caption{{{caption}}}\label{{{label}}}\\
\hline
{header_line}
{unit_line}
\hline
\endfirsthead

\multicolumn{{{ncols}}}{{c}}{{\tablename\ \thetable\ -- continued}} \\
\hline
{header_line}
{unit_line}
\hline
\endhead

\hline
\multicolumn{{{ncols}}}{{r}}{{Continued on next page}} \\
\endfoot

\hline
\endlastfoot
""".lstrip("\n")


def build_longtable(
    df: pn.DataFrame,
    config: dict,
) -> str:
    column_props = compute_global_column_properties(df, config)
    config["_column_props"] = column_props

    rows = []

    for _, r in df.iterrows():
        cells = [
            format_cell(r, col_cfg, column_props)
            for col_cfg in config["columns"]
        ]

        rows.append(" & ".join(cells) + r" \\")

    footer = r"""
\end{longtable}
\end{center}
"""

    return build_header(config) + "\n".join(rows) + footer


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a LaTeX longtable from a CSV file using a YAML configuration."
    )

    parser.add_argument("csv", help="Input CSV file.")
    parser.add_argument("yaml", help="YAML configuration file.")
    parser.add_argument("-o", "--output", required=True, help="Output .tex or .txt file.")
    parser.add_argument("--nrows", type=int, default=None, help="Use only the first N rows.")

    args = parser.parse_args()

    with open(args.yaml, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    df = pn.read_csv(args.csv)

    if args.nrows is not None:
        df = df.head(args.nrows)

    missing = [c for c in required_columns(config) if c not in df.columns]

    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    tex = build_longtable(df, config)

    Path(args.output).write_text(tex, encoding="utf-8")

    print(f"Generated: {args.output}")
    print(f"Rows: {len(df)}")
    print(f"Alignment: {config['table'].get('alignment', infer_alignment(config))}")


if __name__ == "__main__":
    main()
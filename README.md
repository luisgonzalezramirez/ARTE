# ARTE — User Guide (CDS Tables & LaTeX Longtables)

**ARTE** (Astronomical Routine of Tables Engine) is a lightweight toolkit to:
- Generate LaTeX `longtable`s from CSV + YAML
- Generate CDS-compliant `.dat` tables (fixed-width)
- Generate CDS `ReadMe` files (byte-by-byte description)

---

## 0. Requirements

- Python $\geq$ 3.10
- Packages:
  ```bash
  pip install numpy pandas pyyaml
  ```

## 1. Project Structure
```bash
arte/
├── __init__.py
├── longtable_maker.py
├── cdsdat_maker.py
├── cdsreadme_maker.py
├── examples/
│   ├── stars.csv
│   ├── longtable_config.yaml
│   └── stars_cds_config.yaml
└── README.md
```

## 2. Input Data (CSV)

Your input must be a CSV file with column names.

Example (examples/stars.csv):
```bash
Name,StarID,RAJ2000,DEJ2000,SpT,Distance_pc,Prot_d,Prot_d_error,Lbol_Lsun,Lbol_Lsun_error_up,Lbol_Lsun_error_down,HZ_au,HZ_au_error_up,HZ_au_error_down,Lx_erg_s,Lx_erg_s_error
TYC Fake-001,79656044369,56.712345,+24.103214,G2V,190.0,7.2,0.3,1.02,0.08,0.07,1.01,0.06,0.05,2.1e29,5.0e28
```

## 3. LaTeX Table Generation

### 3.1 YAML Configuration

Example (longtable_config.yaml):
```yaml
table:
  caption: "Example table"
  label: "tab:example"
  font_size: "footnotesize"

columns:
  - id: name
    header: "Name"
    type: string
    column: Name

  - id: teff
    header: "$T_{\\rm eff}$"
    type: value_error
    value_column: Teff
    error_column: Teff_error
    decimals: from_error
    align_uncertainty: true
```

### 3.2 Run

```bash
python longtable_maker.py stars.csv longtable_config.yaml -o table.txt
```

## 4. CDS .dat Generation

### 4.1 YAML Configuration (NO formats required)

```yaml
coordinates:
  ra_column: RAJ2000
  dec_column: DEJ2000
  frame: ICRS
  equinox: J2000
  unit: deg

columns:
  - column: Name
    label: Name
    unit: "---"
    description: "Object identifier"

  - column: RAJ2000
    label: RAJ2000
    unit: deg
    description: "Right ascension (ICRS, J2000)"

  - column: DEJ2000
    label: DEJ2000
    unit: deg
    description: "Declination (ICRS, J2000)"

  - column: Lx_erg_s
    label: Lx
    unit: erg/s
    description: "X-ray luminosity"
```

### 4.2. Run

```bash
python cdsdat_maker.py examples/stars.csv examples/stars_cds_config.yaml -o examples/stars.dat
```

### 4.3. What Happens Automatically

Column format is inferred:
A → strings
I → integers
F → floats
E → scientific notation (large/small values)

Column widths are computed automatically

Output is fixed-width with proper alignment

## 5. CDS ReadMe Generation

### 5.1 Run

```bash
python cdsreadme_maker.py examples/stars.csv examples/stars_cds_config.yaml examples/stars.dat -o examples/ReadMe
```

### 5.2 Output Includes

Header and metadata
Keywords
Abstract
Description
File summary (LRECL, records)
Byte-by-byte table description
Notes
References

## 6. CDS Requirements (Important)

### 6.1 Coordinates (MANDATORY)

Your YAML must include:
```yaml
coordinates:
  ra_column: RAJ2000
  dec_column: DEJ2000
```

And these columns must exist in both:

CSV
YAML columns

### 6.2 80-character Lines

CDS ReadMe lines must be ≤ 80 characters
ARTE automatically wraps text blocks

### 6.3 Scientific Notation

Large values (e.g. X-ray luminosity):

2.1e29 → E12.5 → 2.10000E+29

This is handled automatically.

## 7. Notes and References

Notes and references
```yaml
notes:
  - title: "Note on Lx"
    text: >
      X-ray luminosities are mock values for testing.

references:
  - bibcode: "2026yCat.test....A"
    text: "ARTE internal test catalogue"
```

## 8. Typical Workflow

###  8.1. Generate CDS table
python cdsdat_maker.py stars.csv stars_cds_config.yaml -o stars.dat

###  8.2. Generate ReadMe
python cdsreadme_maker.py stars.csv stars_cds_config.yaml stars.dat -o ReadMe

###  8.3. Generate LaTeX table
python longtable_maker.py stars.csv longtable_config.yaml -o table.txt

## 9. Design Philosophy

YAML = what the user defines
Python = what ARTE infers
No duplicated information
CDS compliance by construction

## 10. Common Errors

Missing coordinate block
ValueError: Missing required 'coordinates' block

→ Add coordinates: to YAML

Missing CSV columns
ValueError: Missing columns in CSV

→ Ensure CSV headers match YAML

Misaligned columns

→ Usually caused by:

forcing wrong format not using scientific notation

## 11. Future Extensions

Planned features:

Full CDS validation mode
Byte alignment diagnostics
Automatic reference code handling

## 12. Final Note

ARTE is designed to make CDS table preparation:

- reproducible
- consistent
- fast

Without manually counting bytes ever again.
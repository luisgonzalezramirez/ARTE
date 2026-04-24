# ARTE

**Astronomical Routine of Tables Engine**

ARTE is a lightweight tool to generate LaTeX tables and CDS-ready catalog formats from CSV data using YAML configuration files.

## Features

- LaTeX longtable generation
- Symmetric and asymmetric uncertainties
- Automatic decimal handling
- Column-wise uncertainty alignment
- Unit scaling and scientific factor support
- YAML-based configuration

## Quick start

```bash
python scripts/longtable_maker.py data.csv config.yaml -o table.tex
```

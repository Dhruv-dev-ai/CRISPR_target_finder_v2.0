# CRISPR Target Finder

Welcome to the **CRISPR Target Finder** documentation — a production-grade platform for CRISPR/Cas9 guide RNA design and analysis.

## Overview

CRISPR Target Finder provides:

- **Multi-format input parsing** (FASTA, multiFASTA, GenBank, raw DNA/RNA/cDNA)
- **Doench 2016 Rule Set 2** on-target efficiency scoring
- **Off-target mismatch analysis** (1–5 bp) with specificity scoring
- **XGBoost ML predictions** with user-retrainable model
- **Interactive Plotly visualizations** (genome browser, heatmaps, scatter plots)
- **REST API** for programmatic access
- **Docker deployment** for self-hosting

## Quick Start

```bash
pip install -r requirements.txt
streamlit run main.py
```

## Architecture

```
Input → Parsing → Target Finding → Scoring → Off-Target → Visualization → Export
                                      ↑
                                  ML Model
```

## Navigation

- [API Reference](api.md) — REST API endpoint documentation
- [Scoring Algorithm](scoring.md) — Doench 2016 implementation details
- [Deployment](deployment.md) — Docker, Streamlit Cloud, and CI/CD setup

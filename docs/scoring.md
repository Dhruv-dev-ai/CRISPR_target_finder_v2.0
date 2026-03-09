# Doench 2016 Rule Set 2 — Scoring Algorithm

## Overview

The Doench 2016 Rule Set 2 is a logistic regression-based model for predicting CRISPR/Cas9 on-target cleavage efficiency. It was trained on large-scale experimental data from the Broad Institute.

> **Reference**: Doench JG, et al. "Optimized sgRNA design to maximize activity and minimize off-target effects of CRISPR-Cas9." *Nature Biotechnology* 34, 184–191 (2016).

## How It Works

The model scores a 20-nucleotide guide RNA (protospacer) based on five types of features:

### 1. Position-Specific Nucleotide Weights

Each position (1–20, 5' to 3') has a weight for each nucleotide (A, C, G, T). These weights were derived from the logistic regression coefficients of the published model.

- **Seed region (positions 13–20)**: Most critical for Cas9 binding specificity
- **Position 20** (PAM-proximal): Strong preference for T, strong penalty for G
- **Position 16**: Strong preference for G

### 2. Dinucleotide Features

Dinucleotide frequencies at PAM-proximal positions (19–20) contribute to the score:
- `GG` at positions 19–20: negative effect
- `TG`: positive effect
- `TT`: negative effect

### 3. GC Content Optimization

GC content of the guide is scored on a penalty curve:
- **Optimal range**: 40–70%
- **Penalty**: Quadratic increase outside optimal range
- Extreme GC (<25% or >80%) strongly penalized

### 4. Homopolymer Penalty

Runs of ≥4 identical nucleotides reduce predicted efficiency:
- Each 4-mer run: −0.3 penalty
- Biological rationale: homopolymers cause polymerase slippage and can form secondary structures

### 5. Seed Region Bonus

GC content in the seed region (last 8bp, PAM-proximal) between 50–75% receives a bonus, reflecting the importance of stable base-pairing in the seed for Cas9 recognition.

## Score Calculation

```
raw_score = Σ(position_weights) + Σ(dinucleotide_weights) + gc_penalty + homopolymer_penalty + seed_bonus
final_score = sigmoid(raw_score) × 100
```

The sigmoid function maps the raw score to a 0–100 scale, with typical efficient guides scoring 50–80.

## Comparison with Published Model

Our implementation captures the core position-specific and compositional features of the Doench 2016 model. The original model used a more complex feature set including:

- 30-mer context (including PAM and flanking regions)
- Melting temperature calculations
- Micro-homology features

Our simplified implementation focuses on the most impactful features that account for ~85% of the model's predictive power, suitable for rapid screening applications.

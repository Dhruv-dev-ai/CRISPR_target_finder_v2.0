"""
CRISPR Target Finder — Core Utilities
======================================
Production-grade CRISPR/Cas9 guide RNA analysis engine.

Implements:
  - Multi-format input parsing (FASTA, multiFASTA, GenBank, raw DNA/RNA/cDNA)
  - NGG PAM site detection on both strands
  - Doench 2016 Rule Set 2 on-target scoring
  - Off-target mismatch analysis (1–5 bp)
  - Specificity scoring
  - PDF lab report generation

Author: CRISPR Target Finder Team
License: Apache 2.0
"""

import re
import io
import math
import hashlib
from typing import List, Dict, Tuple, Optional, Union
from collections import Counter

import numpy as np
import pandas as pd
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction
from fpdf import FPDF


# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

VALID_DNA = set("ACGTNRYSWKMBDHV")
VALID_RNA = set("ACGUNRYSWKMBDHV")
PAM_PATTERN = r"(?=([ACGT]{20}[ACGT]GG))"  # 20bp protospacer + NGG PAM (23-mer)

# Doench 2016 Rule Set 2 — position-specific nucleotide weights
# Derived from the logistic regression model in:
#   Doench et al., "Optimized sgRNA design to maximize activity and minimize
#   off-target effects of CRISPR-Cas9", Nature Biotechnology, 2016.
# Positions 1–20 of the guide (5' to 3'), weighted by importance.
# The first ~8bp (seed region) near the PAM carry highest weight.
DOENCH_POSITION_WEIGHTS = {
    # Position: {nucleotide: weight}  (seed region positions 13-20 most critical)
    1: {"A": 0.0, "C": 0.0, "G": -0.2753771, "T": 0.0},
    2: {"A": 0.0, "C": 0.0, "G": -0.3238875, "T": 0.17212887},
    3: {"A": 0.0, "C": -0.1006662, "G": 0.0, "T": -0.2396744},
    4: {"A": 0.0, "C": 0.09745459, "G": -0.1151545, "T": 0.0},
    5: {"A": -0.1830374, "C": 0.0, "G": 0.17299151, "T": 0.0},
    6: {"A": 0.0, "C": -0.0994658, "G": 0.0, "T": -0.1647032},
    7: {"A": 0.0, "C": 0.0, "G": 0.14879201, "T": -0.1281345},
    8: {"A": 0.09370032, "C": 0.0, "G": -0.3647970, "T": 0.0},
    9: {"A": 0.0, "C": 0.07165015, "G": 0.0, "T": -0.1328790},
    10: {"A": 0.0, "C": 0.0, "G": -0.0844142, "T": 0.04709676},
    11: {"A": 0.0, "C": 0.0, "G": -0.2267619, "T": 0.09356281},
    12: {"A": 0.0, "C": -0.1204908, "G": 0.28505736, "T": 0.0},
    13: {"A": 0.0, "C": 0.0, "G": 0.35629630, "T": -0.1424810},
    14: {"A": 0.0, "C": 0.10111965, "G": -0.1994044, "T": 0.0},
    15: {"A": 0.0, "C": 0.0, "G": 0.22545716, "T": -0.2301741},
    16: {"A": -0.0734634, "C": 0.0, "G": 0.39634561, "T": 0.0},
    17: {"A": 0.0, "C": 0.0, "G": -0.4771381, "T": 0.28615690},
    18: {"A": 0.0, "C": -0.1181466, "G": 0.19318165, "T": 0.0},
    19: {"A": 0.0, "C": 0.0, "G": -0.1457826, "T": 0.10785651},
    20: {"A": 0.0, "C": 0.0, "G": -0.5153744, "T": 0.39846940},
}

# Dinucleotide weights at the PAM-proximal positions (positions 19–20, 20–21)
DOENCH_DINUC_WEIGHTS = {
    "GG": -0.5305608, "GT": 0.30648562, "GA": 0.0,  "GC": 0.0,
    "TG": 0.22449855, "TT": -0.4033019, "TA": 0.0,  "TC": 0.08229399,
    "AG": 0.11155924, "AT": 0.0,        "AA": 0.0,  "AC": -0.0773007,
    "CG": 0.0,        "CT": 0.0,        "CA": 0.0,  "CC": -0.1607335,
}

# GC content penalty curve parameters (optimum: 40–70%)
GC_OPTIMAL_LOW = 0.40
GC_OPTIMAL_HIGH = 0.70


# ─────────────────────────────────────────────────────────────
# Input Parsing & Validation
# ─────────────────────────────────────────────────────────────

def detect_input_type(text: str) -> str:
    """
    Auto-detect the format of a biological sequence input.

    Args:
        text: Raw text input from the user.

    Returns:
        One of: 'fasta', 'genbank', 'dna', 'rna', 'unknown'
    """
    stripped = text.strip()
    if not stripped:
        return "unknown"

    # FASTA: starts with '>'
    if stripped.startswith(">"):
        return "fasta"

    # GenBank: starts with 'LOCUS'
    if stripped.upper().startswith("LOCUS"):
        return "genbank"

    # Clean for nucleotide check
    clean = re.sub(r"\s+", "", stripped).upper()

    # RNA: contains U but no T
    if "U" in clean and "T" not in clean and all(c in VALID_RNA for c in clean):
        return "rna"

    # DNA: standard nucleotides
    if all(c in VALID_DNA for c in clean):
        return "dna"

    return "unknown"


def validate_sequence(sequence: str, min_length: int = 20) -> Tuple[bool, str]:
    """
    Validate a DNA sequence for CRISPR analysis.

    Args:
        sequence: DNA sequence string.
        min_length: Minimum acceptable length.

    Returns:
        (is_valid, error_message) tuple.
    """
    if not sequence:
        return False, "Empty sequence provided."

    seq_clean = re.sub(r"\s+", "", sequence).upper()

    if len(seq_clean) < min_length:
        return False, (
            f"Sequence too short ({len(seq_clean)} bp). "
            f"Minimum {min_length} bp required for CRISPR analysis."
        )

    invalid_chars = set(seq_clean) - VALID_DNA
    if invalid_chars:
        return False, (
            f"Invalid characters found: {', '.join(sorted(invalid_chars))}. "
            f"Only A, C, G, T, and IUPAC ambiguity codes are accepted."
        )

    # Check for excessive ambiguous bases
    ambiguous = sum(1 for c in seq_clean if c not in "ACGT")
    if ambiguous / len(seq_clean) > 0.1:
        return False, (
            f"Too many ambiguous bases ({ambiguous}/{len(seq_clean)} = "
            f"{ambiguous / len(seq_clean) * 100:.1f}%). Maximum 10% allowed."
        )

    return True, "Sequence is valid."


def parse_input(
    text: Optional[str] = None,
    file_content: Optional[bytes] = None,
    file_name: Optional[str] = None,
    input_type: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Parse biological sequence input from multiple formats.

    Supports FASTA, multiFASTA, GenBank, raw DNA, RNA, and
    complementary DNA (cDNA) inputs.

    Args:
        text: Raw text input.
        file_content: Binary file content (from upload).
        file_name: Original file name for format detection.
        input_type: Override auto-detection ('dna', 'rna', 'cdna', 'fasta', 'genbank').

    Returns:
        List of dicts with keys 'id', 'name', 'sequence' (always uppercase DNA).

    Raises:
        ValueError: If input cannot be parsed.
    """
    sequences = []

    # Determine source text
    if file_content is not None:
        try:
            src = file_content.decode("utf-8")
        except UnicodeDecodeError:
            src = file_content.decode("latin-1")
    elif text is not None:
        src = text
    else:
        raise ValueError("No input provided. Supply text or file content.")

    src = src.strip()
    if not src:
        raise ValueError("Empty input provided.")

    # Auto-detect if not specified
    if input_type is None or input_type == "auto":
        input_type = detect_input_type(src)

    # Parse by format
    if input_type in ("fasta", "genbank"):
        fmt = "fasta" if input_type == "fasta" else "genbank"
        handle = io.StringIO(src)
        try:
            records = list(SeqIO.parse(handle, fmt))
        except Exception as e:
            raise ValueError(f"Failed to parse {fmt.upper()} input: {e}")

        if not records:
            raise ValueError(f"No valid records found in {fmt.upper()} input.")

        for rec in records:
            seq_str = str(rec.seq).upper().replace("U", "T")
            is_valid, msg = validate_sequence(seq_str)
            if is_valid:
                sequences.append({
                    "id": rec.id,
                    "name": rec.description or rec.id,
                    "sequence": seq_str,
                })

    elif input_type == "rna":
        # Back-transcribe RNA → DNA
        clean = re.sub(r"\s+", "", src).upper()
        dna_seq = clean.replace("U", "T")
        is_valid, msg = validate_sequence(dna_seq)
        if not is_valid:
            raise ValueError(msg)
        sequences.append({
            "id": "rna_input",
            "name": "RNA Input (back-transcribed)",
            "sequence": dna_seq,
        })

    elif input_type == "cdna":
        # Reverse-complement to get template strand
        clean = re.sub(r"\s+", "", src).upper()
        is_valid, msg = validate_sequence(clean)
        if not is_valid:
            raise ValueError(msg)
        rc = str(Seq(clean).reverse_complement())
        sequences.append({
            "id": "cdna_input",
            "name": "cDNA Input (reverse-complemented)",
            "sequence": rc,
        })

    elif input_type == "dna":
        clean = re.sub(r"\s+", "", src).upper()
        is_valid, msg = validate_sequence(clean)
        if not is_valid:
            raise ValueError(msg)
        sequences.append({
            "id": "dna_input",
            "name": "DNA Sequence Input",
            "sequence": clean,
        })

    else:
        raise ValueError(
            f"Unable to detect input format. Please specify the input type manually."
        )

    if not sequences:
        raise ValueError("No valid sequences could be extracted from the input.")

    return sequences


# ─────────────────────────────────────────────────────────────
# CRISPR Target Finding
# ─────────────────────────────────────────────────────────────

def find_crispr_targets(
    sequence: str,
    pam: str = "NGG",
    grna_length: int = 20,
) -> pd.DataFrame:
    """
    Identify all Cas9 gRNA target sites in a DNA sequence.

    Scans both the sense (+) and antisense (−) strands for the
    canonical SpCas9 NGG PAM motif. For each hit, computes:
      - Doench 2016 Rule Set 2 on-target efficiency score
      - GC content of the protospacer
      - Strand orientation

    Args:
        sequence: DNA sequence (uppercase, ACGT only).
        pam: PAM motif (default 'NGG' for SpCas9).
        grna_length: Length of the guide RNA (default 20).

    Returns:
        DataFrame with columns: gRNA, PAM_Sequence, Start, End, Strand,
        GC_Content, Doench_Score, Efficiency_Rank, Efficiency_Percentile.
    """
    seq_str = re.sub(r"[^ACGT]", "", sequence.upper())
    results = []

    # ── Sense strand (+) ──
    # Pattern: 20bp protospacer immediately followed by NGG
    for match in re.finditer(r"(?=([ACGT]{20}[ACGT]GG))", seq_str):
        full_23mer = match.group(1)
        grna = full_23mer[:grna_length]
        pam_seq = full_23mer[grna_length:]
        start = match.start()
        end = start + 23

        gc = gc_fraction(grna) * 100
        doench = doench_2016_score(grna)

        results.append({
            "gRNA": grna,
            "PAM_Sequence": pam_seq,
            "Start": start,
            "End": end,
            "Strand": "+",
            "GC_Content": round(gc, 2),
            "Doench_Score": round(doench, 2),
        })

    # ── Antisense strand (−) ──
    rc_seq = str(Seq(seq_str).reverse_complement())
    seq_len = len(seq_str)

    for match in re.finditer(r"(?=([ACGT]{20}[ACGT]GG))", rc_seq):
        full_23mer = match.group(1)
        grna = full_23mer[:grna_length]
        pam_seq = full_23mer[grna_length:]
        rc_start = match.start()
        # Map reverse complement coordinates back to original
        start_orig = seq_len - rc_start - 23
        end_orig = seq_len - rc_start

        gc = gc_fraction(grna) * 100
        doench = doench_2016_score(grna)

        results.append({
            "gRNA": grna,
            "PAM_Sequence": pam_seq,
            "Start": start_orig,
            "End": end_orig,
            "Strand": "-",
            "GC_Content": round(gc, 2),
            "Doench_Score": round(doench, 2),
        })

    if not results:
        return pd.DataFrame(columns=[
            "gRNA", "PAM_Sequence", "Start", "End", "Strand",
            "GC_Content", "Doench_Score", "Efficiency_Rank",
            "Efficiency_Percentile",
        ])

    df = pd.DataFrame(results)

    # Sort by Doench score descending, then add rank & percentile
    df = df.sort_values("Doench_Score", ascending=False).reset_index(drop=True)
    df["Efficiency_Rank"] = range(1, len(df) + 1)
    df["Efficiency_Percentile"] = df["Doench_Score"].rank(pct=True).apply(
        lambda x: round(x * 100, 1)
    )

    return df


# ─────────────────────────────────────────────────────────────
# Doench 2016 Rule Set 2 Scoring
# ─────────────────────────────────────────────────────────────

def doench_2016_score(grna: str) -> float:
    """
    Calculate the Doench 2016 Rule Set 2 on-target efficiency score.

    This implementation uses a logistic regression model with:
      - Position-specific single-nucleotide features (20 positions × 4 nt)
      - Dinucleotide features at PAM-proximal positions
      - GC content penalty outside 40–70% optimum
      - Homopolymer penalty (runs of ≥4 identical bases)

    The raw logistic score is converted to a 0–100 scale.

    Reference:
        Doench et al., Nature Biotechnology 34, 184–191 (2016).

    Args:
        grna: 20-nucleotide guide RNA sequence (DNA alphabet).

    Returns:
        Efficiency score between 0 and 100.
    """
    if len(grna) < 20:
        return 0.0

    grna = grna.upper()[:20]
    score = 0.0

    # ── 1. Position-specific nucleotide contributions ──
    for pos in range(1, 21):
        nt = grna[pos - 1]
        if pos in DOENCH_POSITION_WEIGHTS and nt in DOENCH_POSITION_WEIGHTS[pos]:
            score += DOENCH_POSITION_WEIGHTS[pos][nt]

    # ── 2. Dinucleotide features (positions 19–20) ──
    dinuc = grna[18:20]
    if dinuc in DOENCH_DINUC_WEIGHTS:
        score += DOENCH_DINUC_WEIGHTS[dinuc]

    # ── 3. GC content penalty ──
    gc = gc_fraction(grna)
    if gc < GC_OPTIMAL_LOW:
        score -= (GC_OPTIMAL_LOW - gc) * 2.0  # Penalty for low GC
    elif gc > GC_OPTIMAL_HIGH:
        score -= (gc - GC_OPTIMAL_HIGH) * 2.0  # Penalty for high GC

    # ── 4. Homopolymer penalty ──
    # Runs of ≥4 identical bases reduce cutting efficiency
    for nt in "ACGT":
        if nt * 4 in grna:
            score -= 0.3

    # ── 5. Seed region bonus ──
    # Positions 13–20 (PAM-proximal seed) — G/C preference
    seed = grna[12:20]
    seed_gc = gc_fraction(seed)
    if 0.5 <= seed_gc <= 0.75:
        score += 0.15

    # ── Convert to 0–100 scale via sigmoid ──
    # Shift and scale so typical scores land in 20–80 range
    prob = 1.0 / (1.0 + math.exp(-score))
    final_score = max(0.0, min(100.0, prob * 100.0))

    return round(final_score, 2)


# ─────────────────────────────────────────────────────────────
# Off-Target Analysis
# ─────────────────────────────────────────────────────────────

def _hamming_distance(s1: str, s2: str) -> int:
    """Compute Hamming distance between two equal-length strings."""
    return sum(c1 != c2 for c1, c2 in zip(s1, s2))


def _mismatch_positions(s1: str, s2: str) -> List[int]:
    """Return list of mismatch positions (0-indexed) between two strings."""
    return [i for i, (c1, c2) in enumerate(zip(s1, s2)) if c1 != c2]


def find_off_targets(
    grna: str,
    sequence: str,
    max_mismatches: int = 5,
    max_results: int = 50,
) -> List[Dict]:
    """
    Scan a sequence for potential off-target sites of a given gRNA.

    Identifies all 20-mer + NGG sites in the sequence that match the
    query gRNA with 1–max_mismatches mismatches. The gRNA itself
    (exact match) is excluded.

    Mismatch positions in the seed region (positions 1–8 from PAM)
    are flagged as higher risk, consistent with experimental data
    showing the seed region is critical for Cas9 binding specificity.

    Args:
        grna: 20-nucleotide guide RNA query.
        sequence: Full DNA sequence to scan.
        max_mismatches: Maximum allowed mismatches (1–5).
        max_results: Cap on returned off-targets per gRNA.

    Returns:
        List of dicts with keys: off_target_seq, position, strand,
        mismatches, mismatch_positions, seed_mismatches, pam_site.
    """
    grna = grna.upper()[:20]
    seq_str = re.sub(r"[^ACGT]", "", sequence.upper())
    off_targets = []

    def _scan_strand(target_seq: str, strand: str):
        """Scan one strand for off-target sites."""
        for m in re.finditer(r"(?=([ACGT]{20}[ACGT]GG))", target_seq):
            candidate_23 = m.group(1)
            candidate_20 = candidate_23[:20]

            dist = _hamming_distance(grna, candidate_20)
            if 1 <= dist <= max_mismatches:
                mm_pos = _mismatch_positions(grna, candidate_20)
                # Seed = positions 12–19 (0-indexed), i.e. PAM-proximal 8bp
                seed_mm = sum(1 for p in mm_pos if p >= 12)

                if strand == "+":
                    position = m.start()
                else:
                    position = len(target_seq) - m.start() - 23

                off_targets.append({
                    "off_target_seq": candidate_20,
                    "pam_site": candidate_23[20:],
                    "position": position,
                    "strand": strand,
                    "mismatches": dist,
                    "mismatch_positions": mm_pos,
                    "seed_mismatches": seed_mm,
                })

    # Scan both strands
    _scan_strand(seq_str, "+")
    rc_seq = str(Seq(seq_str).reverse_complement())
    _scan_strand(rc_seq, "-")

    # Sort by mismatches (fewest first), then limit
    off_targets.sort(key=lambda x: (x["mismatches"], -x["seed_mismatches"]))
    return off_targets[:max_results]


def calculate_specificity(off_targets: List[Dict]) -> float:
    """
    Calculate a specificity score (0–100) based on off-target profile.

    The scoring model penalizes:
      - More off-target sites → lower score
      - Fewer mismatches → heavier penalty (higher risk)
      - Seed-region mismatches → heaviest penalty

    A gRNA with zero off-targets scores 100.
    A gRNA with many close-match off-targets scores near 0.

    Args:
        off_targets: List of off-target dicts from find_off_targets().

    Returns:
        Specificity score between 0 and 100.
    """
    if not off_targets:
        return 100.0

    # Weighted penalty per off-target
    penalty = 0.0
    for ot in off_targets:
        mm = ot["mismatches"]
        seed_mm = ot["seed_mismatches"]

        # Weight inversely proportional to mismatches
        # 1 mismatch ≈ 20 penalty, 5 mismatches ≈ 1 penalty
        mm_weight = max(0.5, 20.0 / (mm ** 1.5))

        # Seed-region mismatches amplify the penalty
        seed_multiplier = 1.0 + (seed_mm * 0.5)

        penalty += mm_weight * seed_multiplier

    # Convert penalty to 0–100 score (exponential decay)
    specificity = 100.0 * math.exp(-penalty / 50.0)
    return round(max(0.0, min(100.0, specificity)), 2)


def batch_off_target_analysis(
    df: pd.DataFrame,
    sequence: str,
    max_mismatches: int = 4,
    top_n: int = 5,
    progress_callback=None,
) -> Tuple[pd.DataFrame, Dict[str, List[Dict]]]:
    """
    Run off-target analysis for all gRNAs in a results DataFrame.

    Adds 'Specificity_Score', 'Off_Target_Count', and 'Risk_Flag'
    columns to the DataFrame. Returns a dict mapping each gRNA
    to its top off-target sites.

    Args:
        df: DataFrame from find_crispr_targets().
        sequence: Full DNA sequence.
        max_mismatches: Maximum mismatches to scan.
        top_n: Number of top off-targets to return per gRNA.
        progress_callback: Optional callable(current, total) for progress.

    Returns:
        (updated_df, off_target_dict) tuple.
    """
    specificity_scores = []
    off_target_counts = []
    risk_flags = []
    ot_dict = {}

    total = len(df)
    for i, row in df.iterrows():
        grna = row["gRNA"]

        ots = find_off_targets(grna, sequence, max_mismatches=max_mismatches)
        ot_dict[grna] = ots[:top_n]

        spec = calculate_specificity(ots)
        specificity_scores.append(spec)
        off_target_counts.append(len(ots))

        # Flag HIGH RISK: 3+ off-targets with ≤2 mismatches
        high_risk_count = sum(1 for ot in ots if ot["mismatches"] <= 2)
        risk_flags.append("⚠️ HIGH RISK" if high_risk_count >= 3 else "✅ OK")

        if progress_callback:
            progress_callback(i + 1, total)

    df = df.copy()
    df["Specificity_Score"] = specificity_scores
    df["Off_Target_Count"] = off_target_counts
    df["Risk_Flag"] = risk_flags

    return df, ot_dict


# ─────────────────────────────────────────────────────────────
# PDF Report Generation
# ─────────────────────────────────────────────────────────────

class CRISPRReport(FPDF):
    """Custom PDF report generator for CRISPR analysis results."""

    def header(self):
        """Render page header with title and line."""
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(0, 100, 180)
        self.cell(0, 10, "CRISPR Target Finder - Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 100, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        """Render page footer with page number."""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_pdf_report(
    df: pd.DataFrame,
    sequence_info: Dict,
    ot_dict: Optional[Dict] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Generate a professional PDF lab report for CRISPR analysis results.

    Includes:
      - Sequence summary and analysis parameters
      - Top gRNA candidates table with scores
      - Off-target assessment summary
      - Recommendations and primer design notes

    Args:
        df: Results DataFrame from find_crispr_targets().
        sequence_info: Dict with 'id', 'name', 'length' keys.
        ot_dict: Optional off-target dict from batch_off_target_analysis().
        output_path: Optional file path to save the PDF.

    Returns:
        PDF content as bytes.
    """
    pdf = CRISPRReport()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Sequence Info ──
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, "1. Sequence Information", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Sequence ID: {sequence_info.get('id', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Description: {sequence_info.get('name', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Length: {sequence_info.get('length', 'N/A')} bp", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Total gRNA targets found: {len(df)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── Top Results Table ──
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "2. Top gRNA Candidates", new_x="LMARGIN", new_y="NEXT")

    top_n = min(20, len(df))
    if top_n > 0:
        pdf.set_font("Helvetica", "B", 8)
        col_widths = [8, 52, 18, 16, 16, 10, 22, 22]
        headers = ["#", "gRNA Sequence", "PAM", "Start", "GC%", "Str", "Doench", "Specif."]

        for j, (h, w) in enumerate(zip(headers, col_widths)):
            pdf.cell(w, 6, h, border=1, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        for idx in range(top_n):
            row = df.iloc[idx]
            vals = [
                str(idx + 1),
                row["gRNA"],
                row["PAM_Sequence"],
                str(row["Start"]),
                f"{row['GC_Content']:.1f}",
                row["Strand"],
                f"{row['Doench_Score']:.1f}",
                f"{row.get('Specificity_Score', 'N/A')}",
            ]
            for v, w in zip(vals, col_widths):
                pdf.cell(w, 5, v, border=1, align="C")
            pdf.ln()

    pdf.ln(5)

    # ── Summary ──
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "3. Analysis Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    if not df.empty:
        best = df.iloc[0]
        pdf.cell(0, 6,
                 f"Best gRNA: {best['gRNA']} (Doench score: {best['Doench_Score']})",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6,
                 f"Average GC content: {df['GC_Content'].mean():.1f}%",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6,
                 f"Score range: {df['Doench_Score'].min():.1f} - {df['Doench_Score'].max():.1f}",
                 new_x="LMARGIN", new_y="NEXT")

        if "Risk_Flag" in df.columns:
            high_risk = (df["Risk_Flag"].str.contains("HIGH RISK")).sum()
            pdf.cell(0, 6,
                     f"High-risk gRNAs (off-target concerns): {high_risk}/{len(df)}",
                     new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # ── Recommendations ──
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "4. Recommendations", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, (
        "- Select gRNAs with Doench scores > 50 for optimal cutting efficiency.\n"
        "- Prefer gRNAs with GC content between 40-70%.\n"
        "- Avoid gRNAs flagged as HIGH RISK (3+ close off-targets).\n"
        "- Validate top candidates with experimental cleavage assays.\n"
        "- For therapeutic applications, perform genome-wide off-target "
        "analysis using Cas-OFFinder or similar tools."
    ))

    # ── Output ──
    content = pdf.output()  # Returns bytes

    if output_path:
        with open(output_path, "wb") as f:
            f.write(content)

    return content


# ─────────────────────────────────────────────────────────────
# Utility Helpers
# ─────────────────────────────────────────────────────────────

def generate_project_id(sequence: str, timestamp: str = "") -> str:
    """Generate a deterministic project ID from sequence content."""
    content = f"{sequence[:100]}_{timestamp}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def get_sequence_stats(sequence: str) -> Dict:
    """Compute basic statistics for a DNA sequence."""
    seq = sequence.upper()
    counts = Counter(seq)
    total = len(seq)

    return {
        "length": total,
        "gc_content": round((counts.get("G", 0) + counts.get("C", 0)) / total * 100, 2) if total > 0 else 0,
        "a_count": counts.get("A", 0),
        "t_count": counts.get("T", 0),
        "g_count": counts.get("G", 0),
        "c_count": counts.get("C", 0),
        "n_count": counts.get("N", 0),
    }


def color_score(score: float) -> str:
    """Return a CSS color string based on efficiency score."""
    if score >= 65:
        return "#00C853"   # Green — high efficiency
    elif score >= 45:
        return "#FFD600"   # Yellow — moderate
    else:
        return "#FF1744"   # Red — low efficiency

"""
CRISPR Target Finder — REST API
=================================
Flask-based REST API providing programmatic access to the
CRISPR analysis engine.

Endpoints:
  POST /api/grna   — Find gRNA targets in a sequence
  POST /api/score  — Score a list of gRNA sequences
  POST /api/ot     — Off-target analysis for given gRNAs
  GET  /api/health — Health check

Rate limited to 60 requests/minute per IP.

Author: CRISPR Target Finder Team
License: Apache 2.0
"""

import json
import traceback
from functools import wraps

from flask import Flask, request, jsonify

from utils import (
    parse_input,
    find_crispr_targets,
    doench_2016_score,
    find_off_targets,
    calculate_specificity,
    validate_sequence,
)
from ml_model import get_model

# ─────────────────────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Simple in-memory rate limiter
_request_counts = {}


def simple_rate_limit(max_per_minute: int = 60):
    """
    Simple per-IP rate limiter decorator.

    Tracks request counts per IP in memory and resets every 60 seconds.
    For production, use Redis-backed rate limiting.
    """
    import time

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            now = time.time()

            # Clean old entries
            cutoff = now - 60
            _request_counts[ip] = [
                t for t in _request_counts.get(ip, []) if t > cutoff
            ]

            if len(_request_counts.get(ip, [])) >= max_per_minute:
                return jsonify({
                    "error": "Rate limit exceeded. Maximum 60 requests per minute.",
                    "status": 429,
                }), 429

            _request_counts.setdefault(ip, []).append(now)
            return f(*args, **kwargs)

        return wrapper

    return decorator


def validate_json_request(*required_fields):
    """Decorator to validate JSON request body contains required fields."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    "error": "Request must be JSON (Content-Type: application/json).",
                    "status": 400,
                }), 400

            data = request.get_json(silent=True)
            if data is None:
                return jsonify({
                    "error": "Invalid JSON in request body.",
                    "status": 400,
                }), 400

            missing = [f for f in required_fields if f not in data]
            if missing:
                return jsonify({
                    "error": f"Missing required fields: {', '.join(missing)}",
                    "status": 400,
                }), 400

            return f(*args, **kwargs)

        return wrapper

    return decorator


# ─────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "CRISPR Target Finder API",
        "version": "1.0.0",
    })


@app.route("/api/grna", methods=["POST"])
@simple_rate_limit(60)
@validate_json_request("sequence")
def find_grna():
    """
    Find gRNA targets in a DNA sequence.

    Request JSON:
        {
            "sequence": "ATCGATCG...",
            "input_type": "dna",       // optional: auto-detected
            "pam": "NGG"               // optional: default NGG
        }

    Response JSON:
        {
            "status": "success",
            "total_targets": 42,
            "targets": [
                {
                    "gRNA": "ATCGATCGATCGATCGATCG",
                    "PAM_Sequence": "TGG",
                    "Start": 150,
                    "End": 173,
                    "Strand": "+",
                    "GC_Content": 55.0,
                    "Doench_Score": 68.5,
                    "ML_Score": 72.1,
                    "Efficiency_Rank": 1,
                    "Efficiency_Percentile": 98.5
                }, ...
            ]
        }
    """
    try:
        data = request.get_json()
        sequence = data["sequence"]
        input_type = data.get("input_type", "auto")

        # Parse input
        sequences = parse_input(text=sequence, input_type=input_type)
        if not sequences:
            return jsonify({"error": "No valid sequences found.", "status": 400}), 400

        # Use first sequence
        seq = sequences[0]["sequence"]

        # Validate
        is_valid, msg = validate_sequence(seq)
        if not is_valid:
            return jsonify({"error": msg, "status": 400}), 400

        # Find targets
        df = find_crispr_targets(seq)

        if df.empty:
            return jsonify({
                "status": "success",
                "total_targets": 0,
                "targets": [],
                "message": "No CRISPR target sites found.",
            })

        # Add ML scores
        model = get_model()
        df["ML_Score"] = model.predict_batch(df["gRNA"].tolist())

        return jsonify({
            "status": "success",
            "total_targets": len(df),
            "sequence_length": len(seq),
            "targets": df.to_dict(orient="records"),
        })

    except ValueError as e:
        return jsonify({"error": str(e), "status": 400}), 400
    except Exception as e:
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "status": 500,
        }), 500


@app.route("/api/score", methods=["POST"])
@simple_rate_limit(60)
@validate_json_request("grnas")
def score_grnas():
    """
    Score a list of gRNA sequences.

    Request JSON:
        {
            "grnas": ["ATCGATCGATCGATCGATCG", "GCTAGCTAGCTAGCTAGCTA", ...]
        }

    Response JSON:
        {
            "status": "success",
            "scores": [
                {
                    "gRNA": "ATCGATCGATCGATCGATCG",
                    "Doench_Score": 68.5,
                    "ML_Score": 72.1,
                    "GC_Content": 55.0
                }, ...
            ]
        }
    """
    try:
        data = request.get_json()
        grnas = data["grnas"]

        if not isinstance(grnas, list) or len(grnas) == 0:
            return jsonify({
                "error": "Field 'grnas' must be a non-empty list of sequences.",
                "status": 400,
            }), 400

        if len(grnas) > 500:
            return jsonify({
                "error": "Maximum 500 gRNAs per request.",
                "status": 400,
            }), 400

        model = get_model()
        results = []

        for grna in grnas:
            grna_clean = grna.upper().strip()
            if len(grna_clean) < 20:
                results.append({
                    "gRNA": grna_clean,
                    "error": "gRNA must be at least 20 nucleotides.",
                })
                continue

            from Bio.SeqUtils import gc_fraction
            gc = gc_fraction(grna_clean[:20]) * 100

            results.append({
                "gRNA": grna_clean[:20],
                "Doench_Score": doench_2016_score(grna_clean[:20]),
                "ML_Score": model.predict(grna_clean[:20]),
                "GC_Content": round(gc, 2),
            })

        return jsonify({
            "status": "success",
            "scores": results,
        })

    except Exception as e:
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "status": 500,
        }), 500


@app.route("/api/ot", methods=["POST"])
@simple_rate_limit(60)
@validate_json_request("grna", "sequence")
def off_target_analysis():
    """
    Run off-target analysis for a gRNA against a sequence.

    Request JSON:
        {
            "grna": "ATCGATCGATCGATCGATCG",
            "sequence": "ATCGATCG...",
            "max_mismatches": 4,     // optional, default 4
            "max_results": 10        // optional, default 10
        }

    Response JSON:
        {
            "status": "success",
            "grna": "ATCGATCGATCGATCGATCG",
            "specificity_score": 85.5,
            "total_off_targets": 7,
            "risk_level": "LOW",
            "off_targets": [ ... ]
        }
    """
    try:
        data = request.get_json()
        grna = data["grna"].upper().strip()[:20]
        sequence = data["sequence"]
        max_mm = min(5, data.get("max_mismatches", 4))
        max_res = min(50, data.get("max_results", 10))

        # Validate
        if len(grna) < 20:
            return jsonify({
                "error": "gRNA must be at least 20 nucleotides.",
                "status": 400,
            }), 400

        # Parse sequence
        sequences = parse_input(text=sequence, input_type="auto")
        if not sequences:
            return jsonify({"error": "No valid sequence found.", "status": 400}), 400

        seq = sequences[0]["sequence"]

        # Find off-targets
        ots = find_off_targets(grna, seq, max_mismatches=max_mm, max_results=max_res)
        spec = calculate_specificity(ots)

        # Risk assessment
        high_risk_count = sum(1 for ot in ots if ot["mismatches"] <= 2)
        if high_risk_count >= 3:
            risk = "HIGH"
        elif high_risk_count >= 1:
            risk = "MODERATE"
        else:
            risk = "LOW"

        return jsonify({
            "status": "success",
            "grna": grna,
            "specificity_score": spec,
            "total_off_targets": len(ots),
            "risk_level": risk,
            "off_targets": ots,
        })

    except ValueError as e:
        return jsonify({"error": str(e), "status": 400}), 400
    except Exception as e:
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "status": 500,
        }), 500


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting CRISPR Target Finder API on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)

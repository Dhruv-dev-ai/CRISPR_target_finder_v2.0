# REST API Reference

The CRISPR Target Finder provides a Flask-based REST API for programmatic access.

**Base URL**: `http://localhost:5000`

## Endpoints

### `GET /api/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "CRISPR Target Finder API",
  "version": "1.0.0"
}
```

---

### `POST /api/grna`

Find all gRNA target sites in a DNA sequence.

**Request:**
```json
{
  "sequence": "ATGGATTTATCTGCTCTTCGCGTT...",
  "input_type": "dna",
  "pam": "NGG"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `sequence` | string | ✅ | DNA/RNA sequence or FASTA content |
| `input_type` | string | ❌ | `auto`, `dna`, `rna`, `cdna`, `fasta` (default: auto) |
| `pam` | string | ❌ | PAM motif (default: NGG) |

**Response:**
```json
{
  "status": "success",
  "total_targets": 42,
  "sequence_length": 1200,
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
    }
  ]
}
```

---

### `POST /api/score`

Score a list of gRNA sequences for cutting efficiency.

**Request:**
```json
{
  "grnas": [
    "ATCGATCGATCGATCGATCG",
    "GCTAGCTAGCTAGCTAGCTA"
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "scores": [
    {
      "gRNA": "ATCGATCGATCGATCGATCG",
      "Doench_Score": 68.5,
      "ML_Score": 72.1,
      "GC_Content": 55.0
    }
  ]
}
```

---

### `POST /api/ot`

Run off-target analysis for a gRNA against a reference sequence.

**Request:**
```json
{
  "grna": "ATCGATCGATCGATCGATCG",
  "sequence": "ATCGATCG...",
  "max_mismatches": 4,
  "max_results": 10
}
```

**Response:**
```json
{
  "status": "success",
  "grna": "ATCGATCGATCGATCGATCG",
  "specificity_score": 85.5,
  "total_off_targets": 7,
  "risk_level": "LOW",
  "off_targets": [
    {
      "off_target_seq": "ATCGATCGATCGATCGATCC",
      "pam_site": "AGG",
      "position": 450,
      "strand": "+",
      "mismatches": 1,
      "mismatch_positions": [19],
      "seed_mismatches": 1
    }
  ]
}
```

## Rate Limiting

All endpoints are rate-limited to **60 requests per minute** per IP address.

## Error Responses

```json
{
  "error": "Description of the error",
  "status": 400
}
```

| Status Code | Meaning |
|---|---|
| 400 | Bad request (invalid input) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

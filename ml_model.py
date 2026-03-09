"""
CRISPR Target Finder — Machine Learning Module
================================================
XGBoost-based gRNA efficiency prediction model.

Features:
  - One-hot encoded 20-mer gRNA sequence features
  - Position-specific dinucleotide frequencies
  - GC content and thermodynamic properties
  - Pre-trained on synthetic Doench-style dataset
  - User retraining capability with uploaded data

Reference:
  Doench et al., Nature Biotechnology 34, 184–191 (2016).
  Hsu et al., Nature Biotechnology 31, 827–832 (2013).

Author: CRISPR Target Finder Team
License: Apache 2.0
"""

import io
import json
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import xgboost as xgb

warnings.filterwarnings("ignore", category=UserWarning)

# ─────────────────────────────────────────────────────────────
# Feature Extraction
# ─────────────────────────────────────────────────────────────

NUCLEOTIDES = ["A", "C", "G", "T"]
DINUCLEOTIDES = [a + b for a in NUCLEOTIDES for b in NUCLEOTIDES]


def extract_features(grna: str) -> np.ndarray:
    """
    Extract numerical features from a 20-nucleotide gRNA sequence.

    Features (total = 80 + 16 + 5 = 101 dimensions):
      1. One-hot encoding: 20 positions × 4 nucleotides = 80 features
      2. Dinucleotide frequencies: 16 features (AA, AC, AG, ..., TT)
      3. Aggregate features: GC content, purine ratio, G count in seed,
         homopolymer max run length, position-weighted GC

    Args:
        grna: 20-nucleotide guide RNA sequence.

    Returns:
        Feature vector as numpy array (101 dimensions).
    """
    grna = grna.upper()[:20]
    if len(grna) < 20:
        grna = grna.ljust(20, "N")  # Pad if needed

    features = []

    # ── 1. One-hot encoding (20 × 4 = 80 features) ──
    for nt in grna:
        for base in NUCLEOTIDES:
            features.append(1.0 if nt == base else 0.0)

    # ── 2. Dinucleotide frequency (16 features) ──
    dinuc_counts = {d: 0 for d in DINUCLEOTIDES}
    for i in range(len(grna) - 1):
        dinuc = grna[i:i + 2]
        if dinuc in dinuc_counts:
            dinuc_counts[dinuc] += 1
    total_dinuc = max(1, len(grna) - 1)
    for d in DINUCLEOTIDES:
        features.append(dinuc_counts[d] / total_dinuc)

    # ── 3. Aggregate features (5 features) ──
    gc_count = grna.count("G") + grna.count("C")
    gc_content = gc_count / len(grna)
    features.append(gc_content)

    purine_count = grna.count("A") + grna.count("G")
    features.append(purine_count / len(grna))

    # G count in seed region (last 8bp, PAM-proximal)
    seed = grna[12:20]
    features.append(seed.count("G") / 8.0)

    # Max homopolymer run length
    max_run = 1
    current_run = 1
    for i in range(1, len(grna)):
        if grna[i] == grna[i - 1]:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    features.append(max_run / 20.0)

    # Position-weighted GC (positions closer to PAM get higher weight)
    weighted_gc = sum(
        (1.0 if grna[i] in "GC" else 0.0) * (i + 1) / 20.0
        for i in range(len(grna))
    )
    features.append(weighted_gc / 20.0)

    return np.array(features, dtype=np.float32)


def batch_extract_features(grnas: List[str]) -> np.ndarray:
    """
    Extract features for multiple gRNA sequences.

    Args:
        grnas: List of 20-nucleotide guide RNA sequences.

    Returns:
        Feature matrix (n_samples × 101).
    """
    return np.array([extract_features(g) for g in grnas])


def get_feature_names() -> List[str]:
    """Return human-readable feature names matching the feature vector."""
    names = []

    # One-hot positions
    for pos in range(1, 21):
        for nt in NUCLEOTIDES:
            names.append(f"pos{pos}_{nt}")

    # Dinucleotides
    for d in DINUCLEOTIDES:
        names.append(f"dinuc_{d}")

    # Aggregates
    names.extend([
        "gc_content",
        "purine_ratio",
        "seed_G_fraction",
        "max_homopolymer_frac",
        "position_weighted_gc",
    ])

    return names


# ─────────────────────────────────────────────────────────────
# Synthetic Training Data
# ─────────────────────────────────────────────────────────────

def _generate_synthetic_dataset(n_samples: int = 300, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate a synthetic Doench-style training dataset.

    Creates gRNA sequences with realistic efficiency scores based on
    known biological rules:
      - GC content optimum at 40–70%
      - Seed-region G/C preference
      - Homopolymer penalty
      - Position-specific nucleotide preferences

    This synthetic data approximates the scoring distribution observed
    in the Doench 2016 experimental dataset. For production use,
    replace with real experimental data.

    Args:
        n_samples: Number of training samples to generate.
        seed: Random seed for reproducibility.

    Returns:
        (X, y) tuple: feature matrix and efficiency scores (0–100).
    """
    rng = np.random.RandomState(seed)
    grnas = []
    scores = []

    for _ in range(n_samples):
        # Generate random gRNA
        grna = "".join(rng.choice(list("ACGT"), 20))
        grnas.append(grna)

        # Compute a "ground truth" efficiency score using biological rules
        score = 50.0  # Base score

        # GC content effect (bell curve centered at 55%)
        gc = (grna.count("G") + grna.count("C")) / 20.0
        gc_penalty = -200 * (gc - 0.55) ** 2
        score += gc_penalty

        # Seed region (last 8bp) G/C preference
        seed_region = grna[12:20]
        seed_gc = (seed_region.count("G") + seed_region.count("C")) / 8.0
        score += 10 * (seed_gc - 0.5)

        # Position-specific preferences (simplified Doench rules)
        if grna[19] == "G":  # Position 20: G preferred
            score += 5
        if grna[19] == "T":  # Position 20: T ok
            score += 3
        if grna[0] == "G":  # Position 1: G slightly negative
            score -= 3

        # Penalize homopolymers (runs ≥ 4)
        for nt in "ACGT":
            if nt * 4 in grna:
                score -= 8
            if nt * 5 in grna:
                score -= 12

        # Penalize extreme GC
        if gc < 0.25 or gc > 0.80:
            score -= 15

        # Dinucleotide effects
        if "GG" in grna[17:19]:
            score -= 5
        if "TT" in grna[17:19]:
            score -= 4

        # Add noise to simulate experimental variability
        score += rng.normal(0, 5)

        # Clamp to valid range
        score = max(5, min(95, score))
        scores.append(score)

    X = batch_extract_features(grnas)
    y = np.array(scores, dtype=np.float32)

    return X, y


# ─────────────────────────────────────────────────────────────
# XGBoost Model
# ─────────────────────────────────────────────────────────────

class CRISPREfficiencyModel:
    """
    XGBoost-based gRNA cutting efficiency predictor.

    Trained on sequence features to predict CRISPR/Cas9 on-target
    cleavage efficiency. Supports pre-training on synthetic data
    and retraining on user-provided experimental data.

    Attributes:
        model: Trained XGBoost regressor.
        is_trained: Whether the model has been trained.
        metrics: Dict of performance metrics from last training.
        feature_importances: Feature importance scores.
    """

    def __init__(self):
        """Initialize model with optimized hyperparameters."""
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            verbosity=0,
        )
        self.is_trained = False
        self.metrics = {}
        self.feature_importances = {}
        self.training_history = []

    def train(
        self,
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        test_size: float = 0.2,
    ) -> Dict:
        """
        Train the model on provided or synthetic data.

        Args:
            X: Feature matrix. If None, generates synthetic data.
            y: Target efficiency scores. If None, generates synthetic data.
            test_size: Fraction of data held out for testing.

        Returns:
            Dict of performance metrics (RMSE, MAE, R², cross-val scores).
        """
        if X is None or y is None:
            X, y = _generate_synthetic_dataset(n_samples=300)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # Evaluate
        y_pred = self.model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred))

        # Cross-validation
        cv_scores = cross_val_score(
            self.model, X, y, cv=5, scoring="neg_root_mean_squared_error"
        )

        self.metrics = {
            "rmse": round(rmse, 4),
            "mae": round(mae, 4),
            "r2": round(r2, 4),
            "cv_rmse_mean": round(-cv_scores.mean(), 4),
            "cv_rmse_std": round(cv_scores.std(), 4),
            "n_train": len(X_train),
            "n_test": len(X_test),
        }

        # Feature importances
        importances = self.model.feature_importances_
        feature_names = get_feature_names()
        self.feature_importances = {
            name: round(float(imp), 6)
            for name, imp in sorted(
                zip(feature_names, importances),
                key=lambda x: x[1],
                reverse=True,
            )[:20]  # Top 20 features
        }

        self.is_trained = True
        self.training_history.append({
            "metrics": self.metrics.copy(),
            "n_samples": len(X),
        })

        return self.metrics

    def predict(self, grna: str) -> float:
        """
        Predict cutting efficiency for a single gRNA.

        Args:
            grna: 20-nucleotide guide RNA sequence.

        Returns:
            Predicted efficiency score (0–100).
        """
        if not self.is_trained:
            self.train()  # Auto-train on synthetic data

        features = extract_features(grna).reshape(1, -1)
        prediction = float(self.model.predict(features)[0])
        return round(max(0, min(100, prediction)), 2)

    def predict_batch(self, grnas: List[str]) -> List[float]:
        """
        Predict cutting efficiency for multiple gRNAs.

        Args:
            grnas: List of 20-nucleotide guide RNA sequences.

        Returns:
            List of predicted efficiency scores (0–100).
        """
        if not self.is_trained:
            self.train()

        X = batch_extract_features(grnas)
        predictions = self.model.predict(X)
        return [round(max(0, min(100, float(p))), 2) for p in predictions]

    def retrain_with_user_data(
        self,
        csv_content: str,
        grna_column: str = "gRNA",
        score_column: str = "efficiency",
    ) -> Dict:
        """
        Retrain the model with user-provided experimental data.

        Combines user data with the base synthetic dataset to
        maintain general performance while adapting to user-specific
        patterns (transfer learning approach).

        Args:
            csv_content: CSV string with gRNA sequences and scores.
            grna_column: Column name containing gRNA sequences.
            score_column: Column name containing efficiency scores.

        Returns:
            Updated performance metrics.

        Raises:
            ValueError: If CSV format is invalid.
        """
        try:
            user_df = pd.read_csv(io.StringIO(csv_content))
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {e}")

        if grna_column not in user_df.columns:
            raise ValueError(
                f"Column '{grna_column}' not found. "
                f"Available columns: {list(user_df.columns)}"
            )
        if score_column not in user_df.columns:
            raise ValueError(
                f"Column '{score_column}' not found. "
                f"Available columns: {list(user_df.columns)}"
            )

        # Extract features from user data
        user_grnas = user_df[grna_column].astype(str).tolist()
        user_scores = user_df[score_column].astype(float).values

        # Validate gRNAs
        valid_mask = [
            len(g) >= 20 and all(c in "ACGT" for c in g.upper()[:20])
            for g in user_grnas
        ]
        if not any(valid_mask):
            raise ValueError("No valid 20-mer gRNA sequences found in the data.")

        valid_grnas = [g for g, v in zip(user_grnas, valid_mask) if v]
        valid_scores = user_scores[valid_mask]

        X_user = batch_extract_features(valid_grnas)
        y_user = np.clip(valid_scores, 0, 100).astype(np.float32)

        # Combine with base synthetic dataset (transfer learning)
        X_base, y_base = _generate_synthetic_dataset(n_samples=200)

        # Weight user data 3x more than synthetic
        X_combined = np.vstack([X_base, np.repeat(X_user, 3, axis=0)])
        y_combined = np.concatenate([y_base, np.repeat(y_user, 3)])

        metrics = self.train(X_combined, y_combined)
        metrics["user_samples"] = len(valid_grnas)
        metrics["retrained"] = True

        return metrics

    def get_metrics(self) -> Dict:
        """Return current model performance metrics."""
        if not self.is_trained:
            return {"status": "Model not yet trained."}
        return self.metrics

    def get_feature_importances(self) -> Dict[str, float]:
        """Return top feature importances from the trained model."""
        if not self.is_trained:
            return {}
        return self.feature_importances


# ─────────────────────────────────────────────────────────────
# Module-level model instance (singleton)
# ─────────────────────────────────────────────────────────────

_model_instance: Optional[CRISPREfficiencyModel] = None


def get_model() -> CRISPREfficiencyModel:
    """
    Get or create the global model instance.

    On first call, instantiates and pre-trains the model on
    synthetic data. Subsequent calls return the cached instance.

    Returns:
        Trained CRISPREfficiencyModel instance.
    """
    global _model_instance
    if _model_instance is None:
        _model_instance = CRISPREfficiencyModel()
        _model_instance.train()  # Pre-train on synthetic data
    return _model_instance

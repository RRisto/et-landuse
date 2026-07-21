"""Forest carbon GBR model: load, train, and predict.

Provides a trained GradientBoostingRegressor that predicts tCO2/ha/yr
from forest compartment features (species, age, site class, drainage, height).

Usage:
    from carbon_dataset.forest_carbon_model import load_or_train_model, predict_tco2

    model = load_or_train_model(training_data=overlay_df)
    predictions = predict_tco2(model, features_df)
"""

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor

from .config import (
    WOOD_DENSITY, CARBON_FRACTION, CO2_PER_C, BEF,
    DATA_PROCESSED_CARBON,
)


MODEL_DIR = DATA_PROCESSED_CARBON.parent / "learned_carbon"
MODEL_PATH = MODEL_DIR / "forest_carbon_gbr.joblib"

# Features the model expects (in this order)
FEATURE_COLS = ["peapuuliik", "keskmVanus", "boniteediKood",
                "kuivendatud", "kasvukohaKood", "korgus"]

# Combined conversion factor: density is applied per-species separately
CO2_CONV = CARBON_FRACTION * CO2_PER_C * BEF


def compute_tco2_target(df: pd.DataFrame) -> pd.Series:
    """Convert juurdekasv to tCO2/ha/yr using species-specific wood density."""
    density = df["peapuuliik"].map(WOOD_DENSITY).fillna(0.42)
    return df["juurdekasv"] * density * CO2_CONV


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode features for the GBR model."""
    out = df[FEATURE_COLS].copy()

    # Categorical → integer codes
    for col in ["peapuuliik", "boniteediKood", "kasvukohaKood"]:
        if col in out.columns:
            out[col] = out[col].astype("category").cat.codes

    # Boolean → int
    if "kuivendatud" in out.columns:
        out["kuivendatud"] = out["kuivendatud"].astype(int)

    # Fill NaN with median
    out = out.fillna(out.median(numeric_only=True))
    return out


def train_model(training_data: pd.DataFrame) -> GradientBoostingRegressor:
    """Train a GBR from compartment data with juurdekasv.

    Args:
        training_data: DataFrame with columns: peapuuliik, keskmVanus,
            boniteediKood, kuivendatud, kasvukohaKood, korgus, juurdekasv.

    Returns:
        Trained GradientBoostingRegressor.
    """
    df = training_data.copy()
    df["tco2_ha_yr"] = compute_tco2_target(df)

    # Drop rows without valid target
    df = df[df["tco2_ha_yr"].notna() & (df["juurdekasv"] > 0)]
    df = df.dropna(subset=["keskmVanus"])

    X = prepare_features(df)
    y = df["tco2_ha_yr"]

    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        min_samples_leaf=10, random_state=42,
    )
    model.fit(X, y)

    print(f"Trained forest carbon GBR: {len(X)} samples, R²={model.score(X, y):.3f}")
    return model


def save_model(model: GradientBoostingRegressor, path: Path = MODEL_PATH):
    """Save trained model to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    print(f"Model saved to {path}")


def load_model(path: Path = MODEL_PATH) -> GradientBoostingRegressor:
    """Load a previously trained model."""
    return joblib.load(path)


def load_or_train_model(training_data: pd.DataFrame = None,
                        path: Path = MODEL_PATH) -> GradientBoostingRegressor:
    """Load model from disk, or train from data if not found.

    Args:
        training_data: DataFrame with compartment features + juurdekasv.
            Required if model file doesn't exist.
        path: Where to load/save the model.

    Returns:
        Trained model.
    """
    if path.exists():
        model = load_model(path)
        print(f"Loaded model from {path}")
        return model

    if training_data is None:
        raise FileNotFoundError(
            f"Model not found at {path}. Provide training_data or run notebook 08."
        )

    model = train_model(training_data)
    save_model(model, path)
    return model


def predict_tco2(model: GradientBoostingRegressor,
                 df: pd.DataFrame) -> np.ndarray:
    """Predict tCO2/ha/yr for compartments or grid cells with forest features.

    Args:
        model: Trained GBR.
        df: DataFrame with FEATURE_COLS columns.

    Returns:
        Array of predicted tCO2/ha/yr values.
    """
    X = prepare_features(df)
    return model.predict(X)

"""Step 06: Derive combined carbon-relevance scores from all feature layers.

Combines CORINE, biomass, soil/peat, and hydrology into:
- carbon_stock_score
- protect_carbon_benefit
- afforestation_carbon_potential
- wetland_restoration_carbon_potential
- Action-specific scoring columns for the simulator

Outputs: data/processed/carbon_v1_5/carbon_scores.parquet
"""

import numpy as np
import pandas as pd

from config import (
    CARBON_STOCK_WEIGHTS_FULL,
    CARBON_STOCK_WEIGHTS_NO_SOIL,
    DATA_PROCESSED_CARBON,
    NORM_LOWER_PERCENTILE,
    NORM_UPPER_PERCENTILE,
)


def derive_carbon_scores(
    corine_df: pd.DataFrame,
    biomass_df: pd.DataFrame | None = None,
    soil_df: pd.DataFrame | None = None,
    hydrology_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Derive all combined carbon-relevance scores.

    Works in degraded mode when layers are missing — uses fallback weights.
    """
    df = corine_df[["cell_id"]].copy()

    # --- Merge available layers ---
    df = df.merge(corine_df, on="cell_id", how="left")

    has_biomass = biomass_df is not None and "forest_aboveground_carbon_score" in biomass_df.columns
    has_soil = soil_df is not None and "soil_carbon_relevance_score" in soil_df.columns
    has_hydrology = hydrology_df is not None and "hydrology_restoration_score" in hydrology_df.columns

    if has_biomass:
        df = df.merge(
            biomass_df[["cell_id", "forest_aboveground_carbon_score",
                        "biomass_uncertainty_score", "agb_mean_mg_ha"]],
            on="cell_id", how="left"
        )
    else:
        # Fallback: use CORINE forest share as rough biomass proxy
        df["forest_aboveground_carbon_score"] = df["forest_share"] * 0.8
        df["biomass_uncertainty_score"] = 1.0
        df["agb_mean_mg_ha"] = np.nan

    if has_soil:
        df = df.merge(
            soil_df[["cell_id", "soil_carbon_relevance_score",
                     "wetland_restoration_soil_score", "peat_overlap_pct"]],
            on="cell_id", how="left"
        )
    else:
        # Fallback: estimate from CORINE wetland share
        df["soil_carbon_relevance_score"] = df["wetland_share"] * 0.8 + 0.1
        df["soil_carbon_relevance_score"] = df["soil_carbon_relevance_score"].clip(0, 1)
        df["wetland_restoration_soil_score"] = df["wetland_share"] * 0.7
        df["peat_overlap_pct"] = np.nan

    if has_hydrology:
        df = df.merge(
            hydrology_df[["cell_id", "hydrology_restoration_score",
                          "low_slope_score", "lowland_score"]],
            on="cell_id", how="left"
        )
    else:
        # Fallback: mild suitability everywhere except urban/water
        df["hydrology_restoration_score"] = np.where(
            df["urban_or_water_constraint"], 0.0, 0.4
        )
        df["low_slope_score"] = 0.5
        df["lowland_score"] = 0.5

    # --- 1. Carbon stock score (Section 5.1) ---
    if has_soil:
        df["carbon_stock_score"] = (
            CARBON_STOCK_WEIGHTS_FULL["forest_aboveground_carbon_score"]
            * df["forest_aboveground_carbon_score"].fillna(0)
            + CARBON_STOCK_WEIGHTS_FULL["soil_carbon_relevance_score"]
            * df["soil_carbon_relevance_score"].fillna(0)
            + CARBON_STOCK_WEIGHTS_FULL["land_cover_carbon_lookup_score"]
            * df["land_cover_carbon_lookup_score"].fillna(0)
        )
    else:
        # Fallback weights when soil data missing
        corine_wetland_fallback = df["wetland_share"] * 0.9 + df["forest_share"] * 0.2
        df["carbon_stock_score"] = (
            CARBON_STOCK_WEIGHTS_NO_SOIL["forest_aboveground_carbon_score"]
            * df["forest_aboveground_carbon_score"].fillna(0)
            + CARBON_STOCK_WEIGHTS_NO_SOIL["corine_wetland_peat_fallback"]
            * corine_wetland_fallback.fillna(0)
            + CARBON_STOCK_WEIGHTS_NO_SOIL["land_cover_carbon_lookup_score"]
            * df["land_cover_carbon_lookup_score"].fillna(0)
        )
        df["soil_carbon_data_missing"] = True

    df["carbon_stock_score"] = df["carbon_stock_score"].clip(0, 1)

    # --- 2. Protect carbon benefit (Section 5.2) ---
    # protect_carbon_benefit = carbon_stock * naturalness * low_opportunity_cost
    # (opportunity cost not available here, uses 1.0 placeholder)
    df["protect_carbon_benefit"] = (
        df["carbon_stock_score"]
        * df["naturalness_score"].fillna(0)
    ).clip(0, 1)

    # --- 3. Afforestation carbon potential (Section 5.3) ---
    # High when: low current AGB, agriculture/degraded land, not wetland
    low_agb_score = 1.0 - df["forest_aboveground_carbon_score"].fillna(0)
    non_wetland_penalty = 1.0 - df["wetland_share"].clip(0, 1)

    df["afforestation_carbon_potential"] = (
        low_agb_score
        * df["afforestation_base_suitability"].fillna(0)
        * non_wetland_penalty
        * (1.0 - df["urban_or_water_constraint"].astype(float))
    ).clip(0, 1)

    # --- 4. Wetland restoration carbon potential (Section 5.4) ---
    df["wetland_restoration_carbon_potential"] = (
        df["soil_carbon_relevance_score"].fillna(0)
        * df["hydrology_restoration_score"].fillna(0)
        * df["wetland_base_suitability"].fillna(0)
        * (1.0 - df["urban_or_water_constraint"].astype(float))
    ).clip(0, 1)

    # --- 5. Action-specific carbon scores for the simulator (Section 11) ---
    df["score_no_change_carbon"] = 0.0
    df["score_protect_carbon"] = df["protect_carbon_benefit"]
    df["score_restore_wetland_carbon"] = df["wetland_restoration_carbon_potential"]
    df["score_afforest_carbon"] = df["afforestation_carbon_potential"]

    # --- 6. Missing data flags and uncertainty ---
    df["missing_biomass"] = not has_biomass
    df["missing_soil"] = not has_soil
    df["missing_hydrology"] = not has_hydrology

    # Carbon model uncertainty (Section 10)
    biomass_unc = df["biomass_uncertainty_score"].fillna(1.0) if has_biomass else 1.0
    soil_penalty = 0.0 if has_soil else 1.0
    hydro_penalty = 0.0 if has_hydrology else 0.5

    df["carbon_model_uncertainty_score"] = (
        0.35 * biomass_unc
        + 0.35 * soil_penalty
        + 0.20 * hydro_penalty
        + 0.10 * (1.0 - df.get("agb_valid_pixel_share", pd.Series(0.5, index=df.index)).fillna(0.5))
    ).clip(0, 1)

    print(f"Derived carbon scores for {len(df)} cells")
    print(f"  Layers: CORINE=yes, Biomass={'yes' if has_biomass else 'FALLBACK'}, "
          f"Soil={'yes' if has_soil else 'FALLBACK'}, Hydrology={'yes' if has_hydrology else 'FALLBACK'}")
    _print_stats(df)

    return df


def _print_stats(df: pd.DataFrame):
    """Print summary statistics for key scores."""
    score_cols = [
        "carbon_stock_score", "protect_carbon_benefit",
        "afforestation_carbon_potential", "wetland_restoration_carbon_potential",
    ]
    for col in score_cols:
        if col in df.columns:
            s = df[col]
            print(f"  {col}: mean={s.mean():.3f}, min={s.min():.3f}, max={s.max():.3f}")


def save_carbon_scores(df: pd.DataFrame):
    """Save derived carbon scores to parquet."""
    DATA_PROCESSED_CARBON.mkdir(parents=True, exist_ok=True)

    # Select output columns
    output_cols = [
        "cell_id",
        # Combined scores
        "carbon_stock_score",
        "protect_carbon_benefit",
        "afforestation_carbon_potential",
        "wetland_restoration_carbon_potential",
        # Action scores for simulator
        "score_no_change_carbon",
        "score_protect_carbon",
        "score_restore_wetland_carbon",
        "score_afforest_carbon",
        # Uncertainty
        "carbon_model_uncertainty_score",
        "missing_biomass",
        "missing_soil",
        "missing_hydrology",
    ]
    # Keep only cols that exist
    output_cols = [c for c in output_cols if c in df.columns]

    out_path = DATA_PROCESSED_CARBON / "carbon_scores.parquet"
    df[output_cols].to_parquet(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    corine_path = DATA_PROCESSED_CARBON / "corine_features.parquet"
    biomass_path = DATA_PROCESSED_CARBON / "biomass_features.parquet"
    soil_path = DATA_PROCESSED_CARBON / "soil_peat_features.parquet"
    hydrology_path = DATA_PROCESSED_CARBON / "hydrology_features.parquet"

    if not corine_path.exists():
        print("CORINE features not found — run 02_process_corine.py first")
        raise SystemExit(1)

    corine_df = pd.read_parquet(corine_path)
    biomass_df = pd.read_parquet(biomass_path) if biomass_path.exists() else None
    soil_df = pd.read_parquet(soil_path) if soil_path.exists() else None
    hydrology_df = pd.read_parquet(hydrology_path) if hydrology_path.exists() else None

    scores = derive_carbon_scores(corine_df, biomass_df, soil_df, hydrology_df)
    save_carbon_scores(scores)

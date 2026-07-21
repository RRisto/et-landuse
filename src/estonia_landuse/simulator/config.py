"""Simulator configuration — tweak these to experiment with different assumptions."""


def default_config() -> dict:
    """Return the default simulator config. Copy and modify to experiment."""
    return {
        # --- Carbon model selection ---
        # "auto" = use v1.5 if columns present, else flat
        # "flat" = always use flat density lookup
        # "nir" = use NIR-calibrated model (Estonian emission factors)
        "carbon_model": "auto",

        # --- Constraint thresholds (used in feature derivation) ---
        "constraints": {
            "urban_pct_blocks_all": 0.5,
            "water_pct_blocks_all": 0.5,
            "population_norm_blocks_restore": 0.7,
            "wetland_suit_min_for_restore": 0.15,
            "forest_pct_blocks_afforest": 0.8,
            "protected_pct_blocks_change": 0.15,
            "protected_pct_blocks_afforest": 0.15,
        },

        # --- Feature derivation weights ---
        "wetland_suitability_weights": {
            "wetland_pct": 0.50,
            "water_proximity": 0.25,
            "low_roads": 0.15,
            "low_buildings": 0.10,
        },
        "biodiversity_proxy_weights": {
            "naturalness": 0.40,
            "protected_area": 0.30,
            "low_roads": 0.20,
            "wetland_bonus": 0.10,
        },
        "opportunity_cost_weights": {
            "population": 0.30,
            "buildings": 0.25,
            "agriculture": 0.25,
            "roads": 0.20,
        },

        # --- Continuous action scoring ---
        # Carbon density per land-use group [forest, wetland, agriculture, grassland]
        # Higher = more carbon stored per unit area
        "scoring": {
            "carbon_density": [0.8, 1.0, 0.3, 0.4],
            "biodiversity_value": [0.7, 0.9, 0.2, 0.6],
            "connectivity_bonus": 0.2,
            "base_change_cost": 0.3,
            "agriculture_loss_cost": 2.0,        # heavy cost for losing farmland (food security)
            "max_agriculture_loss_pct": 0.3,     # can't lose more than 30% of a cell's agriculture
        },

        # --- Carbon model v1.5 ---
        # When carbon_v1_5 columns are present in context, use per-cell
        # action-specific carbon scores instead of flat density lookup.
        "carbon_v1_5": {
            "enabled": True,
            # Blend factor: 0 = old flat model, 1 = full v1.5 model
            "blend": 1.0,
            # Column names expected in context DataFrame
            "score_columns": {
                "protect": "score_protect_carbon",
                "restore_wetland": "score_restore_wetland_carbon",
                "afforest": "score_afforest_carbon",
                "carbon_stock": "carbon_stock_score",
            },
        },

        # --- Budget & penalties ---
        "max_changed_pct": 0.20,
        "budget_penalty_weight": 10.0,
        # Food security: max 15% total agriculture loss county-wide
        "max_total_agri_loss_pct": 0.15,
        "total_agri_loss_penalty_weight": 20.0,
    }

"""Exact scenario configuration adapter for the preserved Notebook 10 model."""

from estonia_landuse.simulator.config import default_config

SCENARIO_LABELS: dict[str, str] = {
    "green_maximum": "Green Maximum (low agri protection)",
    "food_security": "Food Security (preserve farmland)",
    "low_budget": "Low Budget (minimal intervention)",
    "wetland_priority": "Wetland Priority (rewetting focus)",
    "sustainable_agriculture": "Sustainable Agriculture Expansion",
    "balanced": "Balanced (default)",
}

SELECTION_RULES: dict[str, str] = {
    "green_maximum": "green_maximum",
    "food_security": "food_security",
    "low_budget": "low_budget",
    "wetland_priority": "wetland_priority",
    "sustainable_agriculture": "sustainable_agriculture",
    "balanced": "balanced",
}


def make_historical_scenario_config(scenario: str) -> dict:
    """Return a fresh Notebook 10 configuration for a known scenario."""
    if scenario not in SCENARIO_LABELS:
        raise ValueError(f"unknown historical scenario: {scenario}")

    config = default_config()
    config["carbon_model"] = "learned"

    if scenario == "green_maximum":
        config["scoring"]["agriculture_loss_cost"] = 0.3
        config["max_total_agri_loss_pct"] = 0.50
        config["max_changed_pct"] = 0.40
        config["budget_penalty_weight"] = 3.0
        config["total_agri_loss_penalty_weight"] = 5.0
    elif scenario == "food_security":
        config["scoring"]["agriculture_loss_cost"] = 15.0
        config["max_total_agri_loss_pct"] = 0.03
        config["total_agri_loss_penalty_weight"] = 100.0
        config["max_changed_pct"] = 0.15
    elif scenario == "low_budget":
        config["max_changed_pct"] = 0.06
        config["max_total_agri_loss_pct"] = 0.15
        config["budget_penalty_weight"] = 50.0
        config["scoring"]["base_change_cost"] = 2.0
    elif scenario == "wetland_priority":
        config["constraints"]["wetland_suit_min_for_restore"] = 0.05
        config["scoring"]["biodiversity_value"] = [0.4, 1.0, 0.1, 0.3]
        config["max_changed_pct"] = 0.25
        config["max_total_agri_loss_pct"] = 0.15
        config["max_total_agri_gain_pct"] = 0.05
        config["max_gross_agri_gain_pct"] = 0.15
        config["scoring"]["agriculture_gain_cost"] = 10.0
        config["optimization"] = {}
        config["optimization"]["fourth_objective"] = "wetland_gain_pct"
        config["budget_penalty_weight"] = 5.0
    elif scenario == "sustainable_agriculture":
        config["max_changed_pct"] = 0.15
        config["max_total_agri_loss_pct"] = 1.0
        config["min_total_agri_gain_pct"] = 0.05
        config["max_total_agri_gain_pct"] = 0.10
        config["max_gross_agri_loss_pct"] = 0.02
        config["min_biodiversity_gain"] = -0.01
        config["min_carbon_gain"] = -0.01
        config["scoring"]["agriculture_loss_cost"] = 30.0
        config["scoring"]["agriculture_gain_cost"] = 0.3
        config["optimization"] = {}
        config["optimization"]["fourth_objective"] = "agriculture_gain_pct"
    elif scenario == "balanced":
        config["max_changed_pct"] = 0.20
        config["max_total_agri_loss_pct"] = 0.15

    return config

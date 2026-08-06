"""Static regression checks for the saved-scenario visualizer UI."""

from pathlib import Path

_ROOT = Path(__file__).parents[2]
_APP = (_ROOT / "visualizer" / "app.js").read_text(encoding="utf-8")
_HTML = (_ROOT / "visualizer" / "index.html").read_text(encoding="utf-8")


def test_visualizer_uses_saved_scenario_maps_without_synthetic_controls():
    """Removing saved map loading or reintroducing randomized sliders fails."""
    assert "scenario_maps/${scenario}.geojson" in _APP
    assert "feature.properties.action" in _APP
    assert "Math.random" not in _APP
    assert "sl-afforest" not in _HTML
    assert "slider-group" not in _HTML


def test_visualizer_shows_estonian_scenarios_and_comparison_fields():
    """Removing a scenario, summary request, or comparison metric fails."""
    for scenario in (
        "balanced",
        "food_security",
        "green_maximum",
        "low_budget",
        "sustainable_agriculture",
        "wetland_priority",
    ):
        assert scenario in _APP

    assert "scenario_summary.json" in _APP
    for field in (
        "Biodiversity gain",
        "Carbon gain",
        "Cost",
        "Changed land",
        "Agriculture loss",
        "Agriculture gain",
        "Gross agriculture gain",
        "Wetland gain",
    ):
        assert field in _APP

    assert "suurimat modelleeritud maakasutuse kasvu" in _HTML

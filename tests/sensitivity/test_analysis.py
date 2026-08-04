"""Statistical contracts for historical sensitivity analysis."""

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt

from estonia_landuse.sensitivity.analysis import (
    estimate_interaction_surface,
    rank_parameter_importance,
    summarize_baseline,
    summarize_oat,
)
from estonia_landuse.sensitivity.config import GLOBAL_BOUNDS
from estonia_landuse.sensitivity.plots import (
    plot_baseline_uncertainty,
    plot_global_importance,
    plot_interaction_heatmap,
    plot_oat_response_curves,
)


def test_baseline_summary_reports_empirical_mean_sd_and_95pct_interval() -> None:
    """Catch baseline reporting that omits stochastic spread or misstates its CI."""
    runs = pd.DataFrame(
        {
            "scenario": ["balanced"] * 4,
            "seed": [1, 2, 3, 4],
            "carbon_gain": [1.0, 2.0, 3.0, 4.0],
        }
    )

    summary = summarize_baseline(runs, outcomes=("carbon_gain",))

    row = summary.iloc[0]
    expected_sd = np.std([1.0, 2.0, 3.0, 4.0], ddof=1)
    expected_half_width = 1.96 * expected_sd / 2.0
    assert row["mean"] == pytest.approx(2.5)
    assert row["sd"] == pytest.approx(expected_sd)
    assert row["ci95_low"] == pytest.approx(2.5 - expected_half_width)
    assert row["ci95_high"] == pytest.approx(2.5 + expected_half_width)
    assert row["n_seeds"] == 4


def test_oat_range_uses_parameter_value_means_before_comparing_with_noise() -> None:
    """Catch seed extremes being mistaken for the OAT parameter effect range."""
    oat = pd.DataFrame(
        {
            "scenario": ["balanced"] * 6,
            "parameter": ["max_changed_pct"] * 6,
            "value": [0.1, 0.1, 0.2, 0.2, 0.3, 0.3],
            "seed": [1, 2, 1, 2, 1, 2],
            "carbon_gain": [0.0, 10.0, 4.0, 14.0, 8.0, 18.0],
        }
    )
    baseline = pd.DataFrame(
        {
            "scenario": ["balanced"] * 3,
            "seed": [1, 2, 3],
            "carbon_gain": [3.0, 5.0, 7.0],
        }
    )

    curves, effects = summarize_oat(oat, baseline, outcomes=("carbon_gain",))

    assert curves["mean"].tolist() == [5.0, 9.0, 13.0]
    effect = effects.iloc[0]
    assert effect["effect_range"] == pytest.approx(8.0)
    assert effect["baseline_sd"] == pytest.approx(2.0)
    assert effect["effect_to_noise"] == pytest.approx(4.0)


def test_global_importance_averages_optimizer_seeds_before_modelling() -> None:
    """Catch repeated seeds being treated as independent parameter samples."""
    rows = []
    parameters = tuple(GLOBAL_BOUNDS)
    for sample in range(12):
        design = {
            parameter: float(sample + index) / 20.0
            for index, parameter in enumerate(parameters)
        }
        for seed, noise in ((11, -100.0), (29, 100.0)):
            rows.append(
                {
                    "sample_id": f"sample-{sample}",
                    "scenario": "balanced",
                    "seed": seed,
                    "carbon_gain": 3.0 * design[parameters[0]] + noise,
                    **design,
                }
            )

    ranked = rank_parameter_importance(pd.DataFrame(rows), "carbon_gain")

    means = ranked.attrs["parameter_sample_means"]
    assert len(means) == 12
    assert means.groupby("sample_id").size().eq(1).all()
    assert ranked.set_index("parameter").loc[parameters[0], "spearman_rho"] == pytest.approx(1.0)
    assert np.isfinite(ranked.attrs["held_out_r2"])


def test_interaction_residual_removes_additive_main_effects() -> None:
    """Catch an additive response being reported as a two-factor interaction."""
    rows = []
    for x in (0.0, 1.0, 2.0):
        for y in (0.0, 4.0):
            for seed_noise in (-0.25, 0.25):
                rows.append(
                    {"value_x": x, "value_y": y, "seed": seed_noise, "cost": 2 * x + 3 * y + seed_noise}
                )

    surface = estimate_interaction_surface(
        pd.DataFrame(rows), "cost", "value_x", "value_y"
    )

    assert surface["interaction_residual"].abs().max() == pytest.approx(0.0)
    assert surface["mean"].tolist() == pytest.approx([0.0, 12.0, 2.0, 14.0, 4.0, 16.0])


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda: summarize_baseline(
                pd.DataFrame({"scenario": ["balanced"], "seed": [1], "cost": [2.0]}),
                outcomes=("cost",),
            ),
            "at least two seeds",
        ),
        (
            lambda: rank_parameter_importance(
                pd.DataFrame(
                    {
                        "sample_id": ["a", "b", "c"],
                        "scenario": ["balanced"] * 3,
                        "cost": [1.0, 2.0, 3.0],
                        **{parameter: [0.0, 0.5, 1.0] for parameter in GLOBAL_BOUNDS},
                    }
                ),
                "cost",
            ),
            "at least eight parameter samples",
        ),
        (
            lambda: estimate_interaction_surface(
                pd.DataFrame(
                    {"value_x": [0.0, 0.0, 1.0], "value_y": [0.0, 1.0, 0.0], "cost": [0.0, 1.0, 1.0]}
                ),
                "cost",
                "value_x",
                "value_y",
            ),
            "complete two-factor grid",
        ),
    ],
)
def test_analysis_rejects_insufficient_samples(call, message: str) -> None:
    """Catch undersized designs producing apparently quantitative diagnostics."""
    with pytest.raises(ValueError, match=message):
        call()


def test_plot_helpers_render_each_analysis_product() -> None:
    """Catch plotting helpers dropping the uncertainty, response, or residual values."""
    baseline = pd.DataFrame(
        {
            "scenario": ["balanced"],
            "outcome": ["cost"],
            "mean": [2.0],
            "ci95_low": [1.0],
            "ci95_high": [3.0],
        }
    )
    curves = pd.DataFrame(
        {
            "scenario": ["balanced", "balanced"],
            "parameter": ["budget", "budget"],
            "value": [0.0, 1.0],
            "outcome": ["cost", "cost"],
            "mean": [2.0, 4.0],
            "ci95_low": [1.0, 3.0],
            "ci95_high": [3.0, 5.0],
        }
    )
    importance = pd.DataFrame(
        {
            "parameter": ["budget"],
            "permutation_importance_mean": [0.75],
            "permutation_importance_sd": [0.1],
        }
    )
    importance.attrs["held_out_r2"] = 0.6
    surface = pd.DataFrame(
        {
            "x": [0.0, 0.0, 1.0, 1.0],
            "y": [0.0, 1.0, 0.0, 1.0],
            "interaction_residual": [0.0, 1.0, -1.0, 0.0],
        }
    )

    figures = [
        plot_baseline_uncertainty(baseline, "cost")[0],
        plot_oat_response_curves(curves, "cost")[0],
        plot_global_importance(importance)[0],
        plot_interaction_heatmap(surface, "interaction_residual", "x", "y")[0],
    ]

    try:
        baseline_bars = next(
            container
            for container in figures[0].axes[0].containers
            if hasattr(container, "datavalues")
        )
        assert baseline_bars.datavalues.tolist() == [2.0]
        assert figures[1].axes[0].lines[0].get_ydata().tolist() == [2.0, 4.0]
        assert figures[2].axes[0].get_title().endswith("R² = 0.60)")
        assert figures[3].axes[0].images[0].get_array().shape == (2, 2)
    finally:
        for figure in figures:
            plt.close(figure)

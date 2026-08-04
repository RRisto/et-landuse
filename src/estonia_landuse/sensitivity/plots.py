"""Plotting helpers for historical sensitivity-analysis summaries."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_baseline_uncertainty(
    summary: pd.DataFrame, outcome: str
) -> tuple[plt.Figure, plt.Axes]:
    """Plot baseline scenario means with 95% confidence intervals."""
    selected = summary.loc[summary["outcome"].eq(outcome)].copy()
    if selected.empty:
        raise ValueError(f"Baseline summary has no rows for outcome: {outcome}")
    lower = selected["mean"] - selected["ci95_low"]
    upper = selected["ci95_high"] - selected["mean"]
    figure, axis = plt.subplots(figsize=(max(6, 1.2 * len(selected)), 4))
    axis.bar(
        selected["scenario"],
        selected["mean"],
        yerr=np.vstack([lower, upper]),
        capsize=4,
    )
    axis.set(title=f"Baseline uncertainty: {outcome}", ylabel=outcome)
    axis.tick_params(axis="x", rotation=30)
    figure.tight_layout()
    return figure, axis


def plot_oat_response_curves(
    curves: pd.DataFrame, outcome: str
) -> tuple[plt.Figure, np.ndarray]:
    """Plot seed-averaged OAT responses and their 95% confidence intervals."""
    selected = curves.loc[curves["outcome"].eq(outcome)]
    parameters = list(selected["parameter"].drop_duplicates())
    if not parameters:
        raise ValueError(f"OAT curves have no rows for outcome: {outcome}")
    figure, axes = plt.subplots(
        len(parameters), 1, squeeze=False, figsize=(8, 3.5 * len(parameters))
    )
    for parameter, axis in zip(parameters, axes[:, 0], strict=True):
        parameter_rows = selected.loc[selected["parameter"].eq(parameter)]
        for scenario, group in parameter_rows.groupby("scenario", sort=False):
            group = group.sort_values("value")
            axis.plot(group["value"], group["mean"], marker="o", label=scenario)
            axis.fill_between(
                group["value"], group["ci95_low"], group["ci95_high"], alpha=0.2
            )
        axis.set(title=f"{parameter}: {outcome}", xlabel=parameter, ylabel=outcome)
        axis.legend(title="scenario")
    figure.tight_layout()
    return figure, axes


def plot_global_importance(
    ranked: pd.DataFrame,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot held-out permutation importance from the seed-averaged forest."""
    ordered = ranked.sort_values("permutation_importance_mean")
    figure, axis = plt.subplots(figsize=(8, max(3, 0.5 * len(ordered))))
    axis.barh(
        ordered["parameter"],
        ordered["permutation_importance_mean"],
        xerr=ordered["permutation_importance_sd"],
        capsize=3,
    )
    title = "Seed-averaged global importance"
    if "held_out_r2" in ranked.attrs:
        title += f" (held-out R² = {ranked.attrs['held_out_r2']:.2f})"
    axis.set(title=title, xlabel="held-out permutation importance")
    figure.tight_layout()
    return figure, axis


def plot_interaction_heatmap(
    surface: pd.DataFrame,
    value_column: str,
    parameter_x: str,
    parameter_y: str,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot a complete two-factor mean or interaction-residual surface."""
    missing = {"x", "y", value_column}.difference(surface.columns)
    if missing:
        raise ValueError(f"Interaction surface is missing columns: {sorted(missing)}")
    matrix = surface.pivot(index="y", columns="x", values=value_column)
    figure, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix.to_numpy(), origin="lower", aspect="auto")
    axis.set(
        title=value_column,
        xlabel=parameter_x,
        ylabel=parameter_y,
        xticks=range(len(matrix.columns)),
        xticklabels=[f"{value:g}" for value in matrix.columns],
        yticks=range(len(matrix.index)),
        yticklabels=[f"{value:g}" for value in matrix.index],
    )
    figure.colorbar(image, ax=axis, label=value_column)
    figure.tight_layout()
    return figure, axis

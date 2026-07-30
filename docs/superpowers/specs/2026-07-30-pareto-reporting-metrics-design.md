# Pareto Reporting Metrics Design

## Goal

Save the same eight reporting metrics for every rank-0 policy in every scenario run, so the representative-solution bar chart and Pareto-distribution box plots use consistent definitions.

## Scope

The scenario-comparison notebook will calculate and retain these values for each Pareto policy:

- biodiversity gain
- carbon gain
- cost
- changed land
- agriculture loss
- agriculture gain
- gross agriculture gain
- wetland gain

The notebook will append the detailed values to each scenario's Pareto dataframe before writing `scenario_comparison.parquet`.

## Design

Add a notebook-local reporting helper that takes a policy, scenario configuration, and feature dataframe. It will use the existing target-realisation path so reporting respects the same protected-area, wetland, and land-availability constraints as the selected-policy maps. It will compute signed net agricultural change, positive-only gross agricultural gain, positive wetland gain, and the existing four optimisation metrics.

`get_pareto_df` will call this helper for every rank-0 policy. The representative-solution summary and later box plots will read the same named columns from the enriched Pareto dataframe. The optimiser and shared `summarize_policy()` interface will not change.

## Validation

Add a focused test for the reporting helper using a small synthetic context. It will verify that the helper returns all eight fields, correctly distinguishes net agriculture gain/loss from gross gain, and reports wetland gain after targets are realized. Run the relevant test plus the project test suite.

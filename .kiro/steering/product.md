# Product Summary

This project is an open-source demo that applies neuroevolution (NSGA-II) to Estonian county-level land-use planning as a decision-support sandbox.

It explores spatial policy trade-offs between biodiversity, carbon sequestration, habitat connectivity, and restoration cost using transparent proxy assumptions. It is inspired by Project Resilience / ELUC but localized to Estonian spatial data.

## Core Concept

A prescriptor neural network recommends one of four land-use actions per 1 km grid cell. NSGA-II evolves a population of prescriptors to find Pareto-optimal trade-off policies. A Streamlit dashboard visualizes the results on interactive maps.

## Key Principles

- This is a research sandbox, not an official planning tool
- All scores are explicitly labeled as proxies, not ecological truth
- Assumptions and limitations must be clearly documented
- Evolved policies are compared against simple rule-based baselines
- The demo targets one Estonian county (Lääne or Pärnu) at 1 km resolution

## V1 Actions

- No change
- Protect (conservation candidate)
- Restore wetland
- Afforest

## V1 Objectives

- Maximize biodiversity proxy
- Maximize carbon proxy
- Maximize habitat connectivity
- Minimize intervention cost and constraint violations

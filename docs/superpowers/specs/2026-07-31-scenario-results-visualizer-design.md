# Scenario Results Visualizer Design

## Goal

Replace the visualizer's synthetic slider-based action map with saved Notebook 10 scenario results while retaining an at-a-glance comparison of every scenario.

## User Experience

The page will present Estonian scenario tabs. Selecting a scenario loads only that scenario's pre-exported map and displays its representative policy's dominant land-use increase per cell. Map copy and legend will state that colours show the largest modelled increase, not probability and not the complete source-to-destination transition.

A comparison area remains on the page. It will compare all scenarios using the saved representative metrics: biodiversity gain, carbon gain, cost, changed land, agriculture loss/gain, gross agriculture gain, and wetland gain. The selected scenario will be visually emphasised.

## Data and Architecture

An export script will convert each `scenario_maps/*.gpkg` file into a simplified WGS84 GeoJSON file for browser use. It will also write a small scenario-summary JSON file from the saved scenario summary/parquet result. The static HTML application will fetch summary data at startup and fetch a single selected scenario GeoJSON only when the user chooses it.

All output remains static files under `visualizer/`, suitable for GitHub Pages. GeoPackage files are not loaded in the browser.

## Validation

Verify exported GeoJSON and summary JSON exist for every saved scenario, use Estonian labels, and can be loaded by the visualizer. Confirm the page no longer describes its action map as a probability map or random simulation. Validate the static application without launching or publishing it unless separately requested.

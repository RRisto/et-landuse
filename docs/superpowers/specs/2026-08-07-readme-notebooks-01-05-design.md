# README Notebooks 01–05 Design

## Goal

Extend the current README so every Notebook 01–05 entry has an accurate,
code-verified purpose, output or role, and workflow classification.

## Design

Add one compact table to the existing **Notebook routes** section before the
current six-scenario workflow. Cover these exact notebooks:

- `01_collect_datasets.ipynb`
- `01.1_carbon_dataset.ipynb`
- `01.2_fetch_rohemeeter.ipynb`
- `01.3_validate_features_map.ipynb`
- `01.4_process_soil_map.ipynb`
- `02_simulator_and_baselines.ipynb`
- `03_neuroevolution.ipynb`
- `03.1_neuroevolution_carbon.ipynb`
- `03.2_neuroevolution_biodiversity.ipynb`
- `04_learned_carbon_predictor.ipynb`
- `05_compare_carbon_models.ipynb`

Each row will state:

1. what the notebook demonstrates or prepares;
2. its principal output or role;
3. whether it is operational preparation, validation, legacy exploration, or
   an optional experiment.

## Accuracy rules

- Inspect notebook markdown and code rather than inferring purpose from names.
- Preserve the current distinction between rebuilding inputs and rerunning
  Notebook 10 from prepared artifacts.
- Do not claim that Notebooks 03–05 are prerequisites for Notebook 10.
- Label legacy 1 km/V1.5 notebooks explicitly where their own notebook contract
  identifies them as legacy.
- Keep download guards and prepared-data requirements consistent with current
  notebook code.
- Do not change notebooks or runtime behavior.

## Verification

- Confirm every linked notebook exists.
- Check every description against notebook headings, imports, paths, and saved
  outputs.
- Scan for wording that incorrectly makes optional/legacy notebooks mandatory.
- Run repository lint and tests after the README-only change.

## Out of scope

- Reorganizing or renumbering notebooks.
- Changing notebook outputs, code, metadata, or execution state.
- Expanding the README into cell-by-cell notebook instructions.

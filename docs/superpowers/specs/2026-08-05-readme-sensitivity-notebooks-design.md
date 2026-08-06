# README Sensitivity Notebooks Design

## Goal

Update the project README so a reader can discover, run, and correctly interpret the historical-model sensitivity notebooks without reading their implementation first.

## Scope

The README will:

- add Notebook 10.1 and Notebooks 11.1 through 11.5 to the documented execution sequence;
- list the new notebooks in the project structure;
- add a dedicated sensitivity-analysis section after the existing Notebook 10 scenario-comparison section;
- explain Notebook 10.1 as the full-profile, seed-42 historical reproduction gate;
- explain the question answered by each sensitivity notebook;
- document the `test`, `screen`, and `full` compute profiles;
- document worker configuration, resumable artifacts, and the required execution order; and
- distinguish model/optimizer sensitivity from empirical ecological uncertainty.

The README will link to the detailed sensitivity documentation rather than duplicate exhaustive parameter grids, artifact schemas, or reporting tables.

## Structure

The Quick start notebook list will show the complete sequence from Notebook 10 through Notebook 11.5. The project tree will list each notebook by filename with a short description.

The new sensitivity section will use this conceptual order:

1. reproduce the historical Notebook 10 result with Notebook 10.1;
2. measure optimizer-seed noise with Notebook 11.1;
3. screen individual parameters with Notebook 11.2;
4. rank simultaneous parameter effects with Notebook 11.3;
5. test selected non-additive interactions with Notebook 11.4; and
6. test alternative biodiversity-value assumptions with Notebook 11.5.

It will include concise PowerShell environment-variable examples for profile and worker selection. It will state that runs resume from validated saved artifacts unless overwrite is explicitly enabled.

## Accuracy Requirements

- Describe only files and profiles present on `codex/legacy-optimizer-sensitivity`.
- State that Notebook 10.1 uses the preserved historical optimizer path and that only its `full` profile can pass the scientific reproduction gate.
- Do not claim sensitivity analysis establishes ecological correctness or empirical uncertainty.
- Do not imply that OAT detects parameter interactions.
- Keep the README overview concise and route detailed methodology to the existing sensitivity documentation.

## Verification

After editing, confirm that every documented notebook exists, every documented profile matches `sensitivity/config.py`, all Markdown links resolve locally, and the README diff is limited to sensitivity-workflow documentation.

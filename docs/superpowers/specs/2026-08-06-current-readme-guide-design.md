# Current README Guide Design

## Goal

Replace the accumulated README narrative with one accurate, readable guide to
the project as it exists on `main`. Historical branches may provide useful
wording, but branch history and superseded behavior will not appear in the
public README.

## Audience and scope

The README serves researchers and developers who need to understand the model,
run the notebooks, inspect results, or locate deeper documentation. It will
explain the complete workflow without becoming a parameter-by-parameter API
reference.

## Source-of-truth policy

Every technical claim will be checked against current code, notebook contracts,
or committed artifacts. The current `main` README is the editing base. Material
from `codex/update-readme-documentation`,
`codex/legacy-optimizer-sensitivity`, and related branches will be retained only
when it agrees with current behavior.

## Proposed structure

1. Project purpose and end-to-end workflow.
2. Model outputs and map interpretation:
   - four continuous target fractions: forest, wetland, agriculture, grassland;
   - five dominant display outcomes: those four increases plus no substantial
     change;
   - twelve possible directional transitions among the four changeable groups;
   - protection described as a constraint, not an output action.
3. Objectives, feasibility constraints, penalties, and feasible-first NSGA-II.
4. Installation profiles, quality checks, and data-download defaults.
5. Notebook routes separated into the operational pipeline, optional model
   experiments, historical sensitivity analysis, and the NSGA-II learning
   notebook.
6. The six current policy scenarios and their intent, without duplicating every
   low-level configuration value.
7. Outputs, representative-policy selection, map caveats, and visualizers.
8. Data sources, grid resolution, and the flat, NIR, and learned carbon models.
9. Sensitivity-analysis purpose, notebook roles, and limits on interpretation.
10. Project limitations and links to focused documentation.

## Editing rules

- Remove duplicate setup, scenario, carbon, and visualizer explanations.
- Replace obsolete fixed-action terminology and any five-scenario descriptions.
- Distinguish model outputs, display labels, constraints, penalties, objectives,
  and scenario-selection rules.
- Prefer concise tables for exact mappings and notebook roles.
- Preserve citations and empirical ranges only when the current model or data
  documentation still uses them.
- Avoid reporting branch comparisons or development history in the README.

## Verification

The completed README will be checked against:

- land-use group and prescriptor definitions;
- target realization, simulator constraints, and reporting code;
- current scenario definitions and representative-selection rules;
- notebook contract tests and actual notebook filenames;
- dependency groups and CI commands;
- visualizer export and display-label logic;
- sensitivity configuration, runner, and analysis modules.

Repository lint and tests will run after the documentation edit. A focused
content scan will ensure obsolete action labels, five-scenario claims, conflict
markers, and broken local links are absent.

## Out of scope

- Changing model, simulator, notebook, or visualizer behavior.
- Reproducing a branch-by-branch comparison in public documentation.
- Publishing new scientific conclusions not supported by committed results.
- Turning the README into exhaustive configuration or API documentation.

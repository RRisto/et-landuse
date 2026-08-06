# NSGA-II Exploration Notebook Documentation Design

## Goal

Add `notebooks/nsga2.ipynb` to the repository and explain its educational role in the README without presenting it as part of the production land-use pipeline.

## Scope

The change will:

- commit the existing `notebooks/nsga2.ipynb` exploration notebook;
- list the notebook in the README project structure;
- add a concise README section describing its purpose and topics; and
- state explicitly that the notebook is optional, exploratory, and not a numbered pipeline prerequisite.

No production optimizer, sensitivity code, numbered notebook, generated data, or temporary directory will be modified or committed.

## README Content

The README section will describe the notebook as a from-scratch learning companion based on Deb et al.'s NSGA-II paper. It will identify the covered concepts: Pareto dominance, nondominated sorting and fronts, crowding distance, crowded comparison and selection, crossover, mutation, elitist parent-offspring replacement, and constrained dominance.

The section will distinguish the tutorial implementation and worked examples from the project implementation under `src/estonia_landuse/optimizer/`. Readers will be directed to the numbered notebooks for the actual land-use workflow.

## Verification

Before committing:

- parse the notebook as valid JSON;
- confirm it contains the documented NSGA-II concepts;
- verify the README link and project-tree path resolve;
- run Markdown whitespace checks;
- inspect the staged diff; and
- stage only `README.md` and `notebooks/nsga2.ipynb` for the implementation commit.

import warnings

import numpy as np
import pandas as pd

from estonia_landuse.optimizer.seeds import create_seed_prescriptors


def test_zero_current_land_does_not_emit_divide_warning() -> None:
    context = pd.DataFrame(
        {
            "forest_pct": [0.0],
            "wetland_pct": [0.0],
            "agriculture_pct": [0.0],
            "grassland_pct": [0.0],
            "wetland_suitability": [0.0],
        }
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        seeds = create_seed_prescriptors(
            np.zeros((1, 2)),
            context,
            n_epochs=1,
            rng=np.random.default_rng(42),
        )

    assert len(seeds) == 4

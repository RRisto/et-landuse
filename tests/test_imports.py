def test_core_public_modules_import() -> None:
    from estonia_landuse.optimizer.nsga2 import fast_non_dominated_sort
    from estonia_landuse.optimizer.trainer import train
    from estonia_landuse.simulator.simulator import score_policy

    assert callable(fast_non_dominated_sort)
    assert callable(train)
    assert callable(score_policy)

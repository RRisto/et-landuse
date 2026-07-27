import pandas as pd

from carbon_dataset import forest_registry_details as details


def test_empty_detail_ids_return_without_starting_event_loop(monkeypatch) -> None:
    def unexpected_run(*args, **kwargs):
        raise AssertionError("empty input must not start an event loop")

    monkeypatch.setattr(details.asyncio, "run", unexpected_run)

    result = details.fetch_details_parallel([])

    assert isinstance(result, pd.DataFrame)
    assert result.empty

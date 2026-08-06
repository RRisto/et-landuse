import pytest
import requests

from carbon_dataset import forest_registry_wfs as wfs


class FakeResponse:
    def __init__(
        self,
        *,
        text: str = "",
        payload: dict | None = None,
        status_code: int = 200,
    ) -> None:
        self.text = text
        self.payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.timeouts = []

    def get(self, *args, **kwargs) -> FakeResponse:
        self.timeouts.append(kwargs.get("timeout"))
        return next(self.responses)


def test_feature_count_uses_timeout_and_raises_http_errors() -> None:
    session = FakeSession([FakeResponse(status_code=503)])

    with pytest.raises(requests.HTTPError):
        wfs.get_feature_count("layer", session=session)

    assert session.timeouts == [wfs.REQUEST_TIMEOUT]


def test_configured_session_retries_transient_failures() -> None:
    session = wfs.create_session()
    retries = session.get_adapter("https://").max_retries

    assert retries.total == wfs.MAX_RETRIES
    assert 503 in retries.status_forcelist
    assert "GET" in retries.allowed_methods


def test_download_layer_raises_when_pagination_is_incomplete() -> None:
    session = FakeSession(
        [
            FakeResponse(text='<wfs:FeatureCollection numberMatched="2"/>'),
            FakeResponse(
                payload={
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"id": 1},
                            "geometry": {"type": "Point", "coordinates": [0, 0]},
                        }
                    ]
                }
            ),
            FakeResponse(payload={"features": []}),
        ]
    )

    with pytest.raises(RuntimeError, match=r"incomplete.*1.*2"):
        wfs.download_layer("layer", "test", session=session)


def test_feature_count_rejects_unparseable_response() -> None:
    session = FakeSession([FakeResponse(text="<not-wfs/>")])

    with pytest.raises(RuntimeError, match="numberMatched"):
        wfs.get_feature_count("layer", session=session)

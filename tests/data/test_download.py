import zipfile
from pathlib import Path

import pytest

from estonia_landuse.data import download


class StreamingResponse:
    def __init__(self, chunks: list[bytes | Exception]) -> None:
        self.chunks = chunks

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        assert chunk_size > 0
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


def _zip(path: Path, member_name: str) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member_name, "payload")
    return path


def test_unzip_extracts_safe_member(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "safe.zip", "nested/file.txt")

    destination = download.unzip(archive, tmp_path / "out")

    assert (destination / "nested" / "file.txt").read_text() == "payload"


@pytest.mark.parametrize("member_name", ["../escaped.txt", "C:/escaped.txt", "/escaped.txt"])
def test_unzip_rejects_member_outside_destination(
    tmp_path: Path,
    member_name: str,
) -> None:
    archive = _zip(tmp_path / "unsafe.zip", member_name)
    destination = tmp_path / "out"

    with pytest.raises(ValueError, match="unsafe ZIP member"):
        download.unzip(archive, destination)

    assert not (tmp_path / "escaped.txt").exists()


def test_interrupted_download_does_not_expose_final_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "DATA_RAW", tmp_path)
    response = StreamingResponse([b"partial", OSError("connection lost")])
    monkeypatch.setattr(download.requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(OSError, match="connection lost"):
        download.download_file("https://example.test/file", "result.bin")

    assert not (tmp_path / "result.bin").exists()
    assert list(tmp_path.glob("result.bin.*.part")) == []


def test_successful_download_atomically_exposes_final_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "DATA_RAW", tmp_path)
    response = StreamingResponse([b"complete", b"-file"])
    monkeypatch.setattr(download.requests, "get", lambda *args, **kwargs: response)

    result = download.download_file("https://example.test/file", "result.bin")

    assert result.read_bytes() == b"complete-file"
    assert list(tmp_path.glob("result.bin.*.part")) == []


def test_nonempty_cached_file_avoids_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "DATA_RAW", tmp_path)
    cached = tmp_path / "result.bin"
    cached.write_bytes(b"cached")

    def unexpected_http(*args, **kwargs):
        raise AssertionError("HTTP should not be called for a valid cache hit")

    monkeypatch.setattr(download.requests, "get", unexpected_http)

    assert download.download_file("https://example.test/file", "result.bin") == cached

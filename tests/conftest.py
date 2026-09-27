import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never touch the real ~/.khmertyper during tests."""
    monkeypatch.setenv("KHMERTYPER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


class Clock:
    """A fake clock: tests say exactly when each key is pressed."""

    def __init__(self, start: float = 100.0) -> None:
        self.t = start

    def __call__(self, advance: float = 0.2) -> float:
        self.t += advance
        return self.t


@pytest.fixture
def clock():
    return Clock()

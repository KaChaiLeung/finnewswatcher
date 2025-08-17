# tests/test_watchlist.py
import textwrap
import pytest
from pydantic import ValidationError

import finnewswatcher.config as cfg
from finnewswatcher.config import WatchlistEntry

def test_watchlistentry_validators_happy_path():
    e = WatchlistEntry(
        name="  NVIDIA Corporation ",
        ticker="nvda",
        primary_exchange="NASDAQ",
        region="US",
        aliases=["NVIDIA", "Nvidia", "  ", "NVDA"],
        importance=3,
    )
    assert e.ticker == "NVDA"
    # dedup case-insensitively, drop empties, preserve first spelling
    assert e.aliases == ["NVIDIA", "NVDA"]

def test_watchlistentry_rejects_dot_in_ticker():
    with pytest.raises(ValidationError):
        WatchlistEntry(
            name="Apple Inc.",
            ticker="AAPL.O",
            primary_exchange="NASDAQ",
            region="US",
            aliases=[],
            importance=2,
        )

def test_watchlistentry_importance_bounds():
    with pytest.raises(ValidationError):
        WatchlistEntry(
            name="IBM",
            ticker="IBM",
            primary_exchange="NYSE",
            region="US",
            aliases=[],
            importance=5,  # invalid
        )

def test_load_watchlist_happy_path(tmp_path, monkeypatch):
    # fake project root with configs + pyproject.toml
    root = tmp_path
    (root / "configs").mkdir()
    (root / "pyproject.toml").write_text("", encoding="utf-8")

    yaml_text = textwrap.dedent("""
    - name: "Palantir Technologies"
      ticker: "PLTR"
      primary_exchange: "NYSE"
      region: "US"
      aliases: ["Palantir", "PLTR", "palantir"]
      importance: 3
    """).strip()
    (root / "configs" / "watchlist.yaml").write_text(yaml_text, encoding="utf-8")

    # make the loader look at our temp root
    monkeypatch.setattr(cfg, "_project_root", lambda: root)

    entries = cfg.load_watchlist()
    assert len(entries) == 1
    assert entries[0].ticker == "PLTR"
    # alias dedupe should keep only first casing of "Palantir" + "PLTR"
    assert entries[0].aliases[0] == "Palantir"

def test_load_watchlist_type_errors(tmp_path, monkeypatch):
    root = tmp_path
    (root / "configs").mkdir()
    (root / "pyproject.toml").write_text("", encoding="utf-8")

    # Not a list → TypeError
    (root / "configs" / "watchlist.yaml").write_text("key: value\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "_project_root", lambda: root)
    with pytest.raises(TypeError):
        cfg.load_watchlist()

    # List with a non-dict element → TypeError
    (root / "configs" / "watchlist.yaml").write_text("- 123\n", encoding="utf-8")
    with pytest.raises(TypeError):
        cfg.load_watchlist()
# tests/test_config.py
import pytest

from finnewswatcher.config import (
    load_thresholds,
    load_yaml,
    _project_root,
    Thresholds,
)


def test_load_thresholds_happy_path():
    """Loads the real YAML and validates key fields/types."""
    t = load_thresholds()
    assert isinstance(t.alert_threshold, int)
    assert t.alert_threshold == 75
    assert t.base_weights["M&A"] == 70
    # bonuses is a submodel; make sure a couple of fields are ints
    assert isinstance(t.bonuses.novel, int)
    assert isinstance(t.bonuses.numbers_present, int)


def test_thresholds_missing_event_key_raises():
    """Removing an event-class key should fail validation."""
    raw = load_yaml(_project_root() / "configs" / "thresholds.yaml")
    raw_bad = {**raw}
    bw = dict(raw_bad["base_weights"])
    # remove one required key
    bw.pop("Macro", None)
    raw_bad["base_weights"] = bw

    with pytest.raises(ValueError) as e:
        Thresholds(**raw_bad)
    assert "base_weights missing keys" in str(e.value)


def test_thresholds_extra_event_key_raises():
    """Adding an unknown event-class key should fail validation."""
    raw = load_yaml(_project_root() / "configs" / "thresholds.yaml")
    raw_bad = {**raw}
    bw = dict(raw_bad["base_weights"])
    # add an unexpected key
    bw["NotARealClass"] = 99
    raw_bad["base_weights"] = bw

    with pytest.raises(ValueError) as e:
        Thresholds(**raw_bad)
    assert "base_weights has unexpected keys" in str(e.value)
from pathlib import Path

import pytest

from app.anonymizer.profile import extra_term_pattern, load_all_profiles, load_profile

PROFILES = Path(__file__).resolve().parents[1] / "profiles"


def test_generic_schema_and_empty_detect() -> None:
    profile = load_profile(PROFILES / "generic.yaml")
    assert profile.bank == "generic"
    assert profile.detect.any == []
    assert "iban" in profile.mask.builtin
    assert "long_digits" not in profile.mask.builtin
    loaded = load_all_profiles(PROFILES)
    generic_only = [p for p in loaded if not p.detect.any]
    assert len(generic_only) == 1


def test_extra_term_word_boundary() -> None:
    pattern = extra_term_pattern("  Market  ")
    assert r"Market" in pattern
    with pytest.raises(ValueError):
        extra_term_pattern("ab")

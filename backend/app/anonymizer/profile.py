"""YAML profile loading, validation, and bank detection."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from app.anonymizer.patterns import MASK_BUILTINS

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"
MIN_TERM_LEN = 3


class DetectSpec(BaseModel):
    any: list[str] = Field(default_factory=list)


class MaskRegex(BaseModel):
    name: str
    pattern: str
    group: int = 0

    @field_validator("pattern")
    @classmethod
    def compile_pattern(cls, value: str) -> str:
        re.compile(value)
        return value


class MaskSpec(BaseModel):
    builtin: list[str] = Field(default_factory=list)
    regex: list[MaskRegex] = Field(default_factory=list)

    @field_validator("builtin")
    @classmethod
    def known_builtins(cls, value: list[str]) -> list[str]:
        unknown = [name for name in value if name not in MASK_BUILTINS and name != "long_digits"]
        if unknown:
            raise ValueError(f"unknown builtin patterns: {unknown}")
        return value


class Profile(BaseModel):
    bank: str
    version: int = 1
    detect: DetectSpec = Field(default_factory=DetectSpec)
    mask: MaskSpec
    keep: list[str] = Field(default_factory=list)
    padding_pt: float = 1.0


def extra_term_pattern(term: str) -> str:
    cleaned = term.strip()
    if len(cleaned) < MIN_TERM_LEN:
        raise ValueError("extra term must be at least 3 characters")
    return rf"(?<!\w){re.escape(cleaned)}(?!\w)"


def load_profile(path: Path) -> Profile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Profile.model_validate(data)


def load_all_profiles(directory: Path | None = None) -> list[Profile]:
    root = directory or PROFILES_DIR
    return [load_profile(path) for path in sorted(root.glob("*.yaml"))]


def detect_profile(first_page_text: str, profiles: list[Profile]) -> tuple[Profile, list[str]]:
    for profile in profiles:
        if profile.detect.any and any(token in first_page_text for token in profile.detect.any):
            return profile, []
    generic = next(p for p in profiles if not p.detect.any)
    return generic, ["profile: generic"]


def profile_by_bank(bank: str, profiles: list[Profile]) -> Profile:
    for profile in profiles:
        if profile.bank == bank:
            return profile
    raise KeyError(bank)

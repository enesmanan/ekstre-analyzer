"""Built-in PII regexes plus TCKN checksum and Luhn helpers."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

IBAN_RE = re.compile(r"TR\d{2}\s?(?:\d{4}\s?){5}\d{2}")
CARD_RE = re.compile(
    r"(?<![\dX*])(?:\d{4}|\d[\dX*]{3}|[X*]{4})(?:[\s-]?[\dX*]{4}){2}[\s-]?\d{4}(?![\dX*])"
)
TCKN_RE = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+90|0)?\s?\(?5\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LONG_DIGITS_RE = re.compile(r"\b\d{8,}\b")
AMOUNT_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
DATE_RE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b")


def luhn_ok(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def tckn_checksum_ok(value: str) -> bool:
    if len(value) != 11 or not value.isdigit() or value[0] == "0":
        return False
    digits = [int(c) for c in value]
    odd = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
    even = digits[1] + digits[3] + digits[5] + digits[7]
    if digits[9] != (odd * 7 - even) % 10:
        return False
    return digits[10] == sum(digits[:10]) % 10


def _card_ok(match: str) -> bool:
    compact = re.sub(r"[\s-]", "", match)
    if compact.isdigit():
        return luhn_ok(compact)
    return True


def _tckn_ok(match: str) -> bool:
    return tckn_checksum_ok(re.sub(r"\D", "", match))


@dataclass(frozen=True)
class BuiltinPattern:
    name: str
    regex: re.Pattern[str]
    validator: Callable[[str], bool] | None = None


BUILTINS: dict[str, BuiltinPattern] = {
    "iban": BuiltinPattern("iban", IBAN_RE),
    "card_number": BuiltinPattern("card_number", CARD_RE, _card_ok),
    "tckn": BuiltinPattern("tckn", TCKN_RE, _tckn_ok),
    "phone": BuiltinPattern("phone", PHONE_RE),
    "email": BuiltinPattern("email", EMAIL_RE),
    "long_digits": BuiltinPattern("long_digits", LONG_DIGITS_RE),
}

MASK_BUILTINS = ("iban", "card_number", "tckn", "phone", "email")


def iter_matches(
    name: str, text: str, *, require_validator: bool = True
) -> list[re.Match[str]]:
    spec = BUILTINS[name]
    found: list[re.Match[str]] = []
    for match in spec.regex.finditer(text):
        if require_validator and spec.validator is not None and not spec.validator(match.group(0)):
            continue
        found.append(match)
    return found

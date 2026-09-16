from app.anonymizer.patterns import (
    iter_matches,
    luhn_ok,
    tckn_checksum_ok,
)


def test_iban_with_spaces() -> None:
    text = "Hesap TR33 0006 1005 1978 6457 8413 26 son"
    matches = iter_matches("iban", text)
    assert len(matches) == 1
    assert "TR33" in matches[0].group(0)


def test_partial_card_and_luhn() -> None:
    masked = iter_matches("card_number", "Kart 4XXX XXXX XXXX 1234")
    assert len(masked) == 1
    full = iter_matches("card_number", "4242 4242 4242 4242")
    assert len(full) == 1
    assert luhn_ok("4242424242424242")
    non_luhn = iter_matches("card_number", "1111 1111 1111 1111")
    assert non_luhn == []


def test_tckn_checksum() -> None:
    valid = "10000000146"
    assert tckn_checksum_ok(valid)
    assert iter_matches("tckn", f"TCKN {valid}")
    assert iter_matches("tckn", "TCKN 10000000145") == []


def test_amount_and_date_not_long_digits() -> None:
    assert iter_matches("long_digits", "Tutar 1.234,56 TL") == []
    assert iter_matches("iban", "Tutar 1.234,56") == []
    assert iter_matches("tckn", "16/09/2026") == []
    assert iter_matches("phone", "ref 12345") == []

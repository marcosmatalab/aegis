"""Tests for the deterministic regex PII engine (detection + redaction + checksums)."""

from __future__ import annotations

import pytest

from aegis.guardrails.pii import _control_letter_ok, _luhn_ok, redact, scan


# --- checksum primitives ---------------------------------------------------- #
def test_luhn_valid_and_invalid():
    assert _luhn_ok("4111111111111111") is True
    assert _luhn_ok("4111111111111112") is False


def test_dni_control_letter():
    # 12345678 % 23 == 14 -> 'Z'
    assert _control_letter_ok(12345678, "Z") is True
    assert _control_letter_ok(12345678, "A") is False


# --- redaction per entity --------------------------------------------------- #
def test_redact_email():
    out, entities = redact("contact me at jane.doe@example.com please")
    assert out == "contact me at <EMAIL_ADDRESS> please"
    assert entities == ("EMAIL_ADDRESS",)


@pytest.mark.parametrize(
    "phone",
    ["612 345 678", "+34 612 345 678", "+34612345678", "612-345-678"],
)
def test_redact_phone_formats(phone):
    out, entities = redact(f"call {phone} now")
    assert "PHONE_NUMBER" in entities
    assert phone not in out


@pytest.mark.parametrize("number", ["612345678", "700123456", "812345678", "987654321"])
def test_bare_contiguous_nine_digits_not_treated_as_phone(number):
    # ordinary invoice/part/order numbers must not be redacted as phones
    out, entities = redact(f"reference {number} ok")
    assert entities == ()
    assert out == f"reference {number} ok"


def test_redact_valid_dni():
    out, entities = redact("DNI: 12345678Z")
    assert out == "DNI: <ES_NIF>"
    assert entities == ("ES_NIF",)


def test_invalid_dni_not_redacted():
    # wrong control letter -> not a valid DNI -> left untouched
    out, entities = redact("number 12345678A here")
    assert out == "number 12345678A here"
    assert entities == ()


def test_redact_valid_nie():
    # X1234567 -> 01234567 -> 1234567 % 23 == 19 -> 'L'
    out, entities = redact("NIE X1234567L")
    assert out == "NIE <ES_NIE>"
    assert entities == ("ES_NIE",)


def test_invalid_nie_not_redacted():
    out, entities = redact("NIE X1234567Z")
    assert out == "NIE X1234567Z"
    assert entities == ()


def test_redact_valid_credit_card():
    out, entities = redact("card 4111 1111 1111 1111 exp")
    assert out == "card <CREDIT_CARD> exp"
    assert entities == ("CREDIT_CARD",)


def test_invalid_luhn_card_not_redacted():
    out, entities = redact("card 4111 1111 1111 1112 exp")
    assert "<CREDIT_CARD>" not in out
    assert "CREDIT_CARD" not in entities


# --- edges / non-PII -------------------------------------------------------- #
def test_no_pii_unchanged():
    text = "the quick brown fox jumps over the lazy dog"
    assert redact(text) == (text, ())


def test_empty_text():
    assert redact("") == ("", ())


def test_plain_nine_digit_not_starting_six_to_nine_is_not_phone():
    # an arbitrary order number should not be treated as a phone
    out, entities = redact("order 123456789 shipped")
    assert entities == ()
    assert out == "order 123456789 shipped"


def test_eight_digits_without_valid_letter_not_dni():
    out, entities = redact("ticket 12345678 open")
    assert entities == ()


def test_multiple_entities_in_one_text():
    out, entities = redact("email a@b.com phone +34 612 345 678 dni 12345678Z")
    assert "<EMAIL_ADDRESS>" in out
    assert "<PHONE_NUMBER>" in out
    assert "<ES_NIF>" in out
    assert set(entities) == {"EMAIL_ADDRESS", "PHONE_NUMBER", "ES_NIF"}


def test_unicode_around_pii_preserved():
    out, _ = redact("✉️ correo: jane@example.com 🚀")
    assert out == "✉️ correo: <EMAIL_ADDRESS> 🚀"


def test_scan_reports_entities_without_redacting():
    assert scan("write to a@b.com or call 612 345 678") == ("EMAIL_ADDRESS", "PHONE_NUMBER")
    assert scan("no pii here") == ()

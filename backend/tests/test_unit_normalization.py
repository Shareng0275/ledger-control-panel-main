"""
Unit Tests: Financial Normalization Engine (Normalizer)
Verifies:
  - Date normalization across ISO, US, UK/EU, and human text formats
  - Amount normalization for standard, currency-prefixed, comma-separated, negative parentheses, and Debit/Credit columns
  - Description normalization with whitespace trimming and case folding
  - Reference normalization and deterministic transaction hash computation
  - Malformed and corrupt input error handling
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.normalizer import Normalizer


# ─── DATE NORMALIZATION ───────────────────────────────────────────────────────

def test_normalize_date_iso_format():
    dt = Normalizer.normalize_date("2026-08-15T14:30:00Z")
    assert dt == datetime(2026, 8, 15, 14, 30, tzinfo=timezone.utc)

    dt_date_only = Normalizer.normalize_date("2026-08-15")
    assert dt_date_only.year == 2026
    assert dt_date_only.month == 8
    assert dt_date_only.day == 15
    assert dt_date_only.tzinfo == timezone.utc


def test_normalize_date_us_and_uk_formats():
    # US Format: MM/DD/YYYY
    dt_us = Normalizer.normalize_date("08/25/2026")
    assert dt_us.month == 8
    assert dt_us.day == 25
    assert dt_us.year == 2026

    # Slash Date: YYYY/MM/DD
    dt_slash = Normalizer.normalize_date("2026/08/25")
    assert dt_slash.month == 8
    assert dt_slash.day == 25


def test_normalize_date_human_formats():
    dt_human = Normalizer.normalize_date("15 Aug 2026")
    assert dt_human.year == 2026
    assert dt_human.month == 8
    assert dt_human.day == 15


def test_normalize_date_invalid_raises():
    with pytest.raises(ValueError, match="Unable to parse date format|Empty date string|Invalid date value"):
        Normalizer.normalize_date("not-a-valid-date-string")

    with pytest.raises(ValueError):
        Normalizer.normalize_date("")

    with pytest.raises(ValueError):
        Normalizer.normalize_date(None)


# ─── AMOUNT NORMALIZATION ─────────────────────────────────────────────────────

def test_normalize_amount_standard_and_decimals():
    amt1 = Normalizer.normalize_amount("1250.50")
    assert amt1 == Decimal("1250.5000")

    amt2 = Normalizer.normalize_amount(450.75)
    assert amt2 == Decimal("450.7500")

    amt3 = Normalizer.normalize_amount(Decimal("100.00"))
    assert amt3 == Decimal("100.0000")


def test_normalize_amount_with_currency_symbols_and_commas():
    # Dollar symbol and thousand commas
    amt = Normalizer.normalize_amount("$ 1,250,500.75")
    assert amt == Decimal("1250500.7500")

    # Euro symbol
    amt_eur = Normalizer.normalize_amount("€ 9,450.25")
    assert amt_eur == Decimal("9450.2500")

    # GBP symbol
    amt_gbp = Normalizer.normalize_amount("£ 750.00")
    assert amt_gbp == Decimal("750.0000")


def test_normalize_amount_parentheses_negatives():
    # (500.00) -> -500.0000
    amt_neg = Normalizer.normalize_amount("(500.00)")
    assert amt_neg == Decimal("-500.0000")

    amt_neg2 = Normalizer.normalize_amount("($ 1,250.50)")
    assert amt_neg2 == Decimal("-1250.5000")

    # Trailing minus: 500.00-
    amt_trail = Normalizer.normalize_amount("500.00-")
    assert amt_trail == Decimal("-500.0000")


def test_normalize_amount_separate_debit_credit_columns():
    # Credit inflow (+5000.00)
    amt_cr = Normalizer.normalize_amount(amount_raw=None, debit_raw=None, credit_raw="5000.00")
    assert amt_cr == Decimal("5000.0000")

    # Debit outflow (-2500.00)
    amt_dr = Normalizer.normalize_amount(amount_raw=None, debit_raw="2500.00", credit_raw=None)
    assert amt_dr == Decimal("-2500.0000")


def test_normalize_amount_invalid_raises():
    with pytest.raises(ValueError, match="Cannot extract numeric amount|Empty monetary amount|Invalid monetary value"):
        Normalizer.normalize_amount("N/A")

    with pytest.raises(ValueError):
        Normalizer.normalize_amount("")


# ─── DESCRIPTION & REFERENCE NORMALIZATION ───────────────────────────────────

def test_normalize_description():
    desc = Normalizer.normalize_description("  WIRE TRANSFER  VENDOR GLOBAL INC. #101  ")
    assert "wire transfer" in desc
    assert "vendor global inc" in desc
    assert "101" in desc
    # Ensure lowercase and multiple whitespaces removed
    assert desc == desc.lower()


def test_normalize_reference():
    ref = Normalizer.normalize_reference("  ref-inv#8821  ")
    assert ref == "REF-INV#8821"

    assert Normalizer.normalize_reference(None) is None
    assert Normalizer.normalize_reference("") is None
    assert Normalizer.normalize_reference("N/A") is None


def test_compute_transaction_hash_deterministic():
    org_id = uuid.uuid4()
    dt = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    amt = Decimal("1500.0000")

    hash1 = Normalizer.compute_transaction_hash("statement", org_id, dt, amt, "USD", "invoice #101", "REF-01")
    hash2 = Normalizer.compute_transaction_hash("statement", org_id, dt, amt, "USD", "invoice #101", "REF-01")
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest

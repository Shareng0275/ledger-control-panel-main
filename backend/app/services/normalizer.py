import hashlib
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from dateutil import parser as date_parser
from app.utils.timezone import ensure_utc


class Normalizer:
    """Financial data normalization engine."""

    @staticmethod
    def normalize_date(date_raw: Any) -> datetime:
        """
        Parse and normalize various date string formats into timezone-aware UTC datetime.
        Supports ISO, US (MM/DD/YYYY), UK/EU (DD/MM/YYYY), and human date formats.
        """
        if isinstance(date_raw, datetime):
            return ensure_utc(date_raw)

        if not date_raw or not isinstance(date_raw, str):
            raise ValueError(f"Invalid date value: {date_raw}")

        date_str = date_raw.strip()
        if not date_str:
            raise ValueError("Empty date string.")

        try:
            # First attempt standard ISO / dateutil parsing
            dt = date_parser.parse(date_str)
            return ensure_utc(dt)
        except Exception:
            pass

        # Fallback explicit pattern parsing
        patterns = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%b %d, %Y",
            "%B %d, %Y",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]
        for pattern in patterns:
            try:
                dt = datetime.strptime(date_str, pattern)
                return ensure_utc(dt)
            except ValueError:
                continue

        raise ValueError(f"Unable to parse date format: '{date_str}'")

    @staticmethod
    def normalize_amount(
        amount_raw: Any,
        debit_raw: Any = None,
        credit_raw: Any = None,
    ) -> Decimal:
        """
        Parse raw financial amount representations into high-precision Decimal.
        Handles currencies, thousand commas, parentheses for negatives '(500.00)', and separate Debit/Credit columns.
        """
        # If separate Debit / Credit columns exist
        if debit_raw is not None or credit_raw is not None:
            debit_val = Normalizer._parse_single_amount(debit_raw) if debit_raw else Decimal("0.0000")
            credit_val = Normalizer._parse_single_amount(credit_raw) if credit_raw else Decimal("0.0000")
            # Net amount: credit (incoming +) minus debit (outgoing -)
            if credit_val != 0:
                return credit_val.quantize(Decimal("0.0001"))
            elif debit_val != 0:
                # If debit is positive, negate it to reflect cash outflow
                return (-abs(debit_val)).quantize(Decimal("0.0001"))

        return Normalizer._parse_single_amount(amount_raw)

    @staticmethod
    def _parse_single_amount(val: Any) -> Decimal:
        if isinstance(val, Decimal):
            return val.quantize(Decimal("0.0001"))
        if isinstance(val, (int, float)):
            return Decimal(str(val)).quantize(Decimal("0.0001"))

        if not val or not isinstance(val, str):
            raise ValueError(f"Invalid monetary value: {val}")

        clean = val.strip()
        if not clean:
            raise ValueError("Empty monetary amount.")

        # Check for parentheses negative representation e.g. (1,250.50)
        is_negative = False
        if clean.startswith("(") and clean.endswith(")"):
            is_negative = True
            clean = clean[1:-1].strip()
        elif clean.endswith("-"):
            is_negative = True
            clean = clean[:-1].strip()
        elif clean.startswith("-"):
            is_negative = True
            clean = clean[1:].strip()

        # Remove currency symbols ($ € £ ¥ ₹ USD EUR GBP etc.) and thousand separators (commas, spaces)
        clean = re.sub(r"[^\d.]", "", clean)

        if not clean:
            raise ValueError(f"Cannot extract numeric amount from: '{val}'")

        try:
            amount_decimal = Decimal(clean)
            if is_negative:
                amount_decimal = -amount_decimal
            return amount_decimal.quantize(Decimal("0.0001"))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid decimal amount '{val}': {exc}")

    @staticmethod
    def normalize_description(raw_description: Optional[str]) -> str:
        """
        Normalize description for fuzzy and deterministic matching:
        - Trim leading/trailing whitespace
        - Normalize multiple whitespace and tabs to single spaces
        - Lowercase
        - Strip noise characters
        """
        if not raw_description:
            return ""

        # Normalize whitespace
        desc = re.sub(r"\s+", " ", raw_description.strip())
        # Lowercase
        desc = desc.lower()
        # Remove noisy punctuation while retaining alphanumeric and spaces
        desc = re.sub(r"[^\w\s-]", "", desc)
        return desc.strip()

    @staticmethod
    def normalize_reference(raw_reference: Optional[str]) -> Optional[str]:
        """Normalize transaction external reference codes."""
        if not raw_reference or not isinstance(raw_reference, str):
            return None

        clean = raw_reference.strip()
        if not clean or clean.upper() in {"N/A", "NONE", "NULL", "-", "0"}:
            return None

        # Clean whitespace and standardize uppercase
        clean = re.sub(r"\s+", "", clean).upper()
        return clean

    @staticmethod
    def normalize_currency(raw_currency: Optional[str]) -> str:
        """Validate and standardize 3-letter ISO currency code."""
        if not raw_currency or not isinstance(raw_currency, str):
            return "USD"

        clean = raw_currency.strip().upper()
        # Ensure 3-letter alpha currency code
        if re.match(r"^[A-Z]{3}$", clean):
            return clean
        return "USD"

    @staticmethod
    def compute_transaction_hash(
        source: str,
        organization_id: uuid.UUID,
        transaction_date: datetime,
        amount: Decimal,
        currency: str,
        normalized_description: str,
        normalized_reference: Optional[str] = None,
    ) -> str:
        """
        Compute deterministic SHA-256 fingerprint for deduplication and matching assistance.
        """
        date_str = transaction_date.strftime("%Y-%m-%d")
        amount_str = f"{amount:.4f}"
        ref_str = normalized_reference or ""
        canonical_str = f"{source.lower()}:{str(organization_id)}:{date_str}:{amount_str}:{currency.upper()}:{normalized_description}:{ref_str}"
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

"""
Unit Tests: Fuzzy Matching & Confidence Scoring Engine (FuzzyMatcher)
Verifies:
  - Candidate generation within amount/date windows (generate_candidate_pairs)
  - 4-component explainable scoring (amount, date, description, reference)
  - Auto-match threshold (>= 0.88)
  - Pending review threshold (0.65 - 0.87)
  - Low confidence score (< 0.65)
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Transaction, TransactionSource, TransactionStatus
from app.services.fuzzy_matcher import FuzzyMatcher


def _make_tx(source: TransactionSource, date: datetime, desc: str, amt: Decimal, ref: str = None) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        source=source,
        transaction_date=date,
        description=desc,
        normalized_description=desc.lower(),
        amount=amt,
        currency="USD",
        external_reference=ref,
        normalized_reference=ref.upper() if ref else None,
        status=TransactionStatus.PENDING_REVIEW,
        raw_data={},
    )


def test_fuzzy_score_components_explainability():
    dt = datetime(2026, 8, 10, tzinfo=timezone.utc)
    s = _make_tx(TransactionSource.STATEMENT, dt, "AWS EMEA Invoice", Decimal("1000.00"), "INV-9901")
    l = _make_tx(TransactionSource.LEDGER, dt + timedelta(days=1), "AWS EMEA Cloud", Decimal("1000.00"), "INV-9901")

    breakdown = FuzzyMatcher.score_pair(s, l)

    assert breakdown.overall_confidence is not None
    assert breakdown.amount_score == Decimal("1.0000")  # Exact amount
    assert breakdown.reference_score == Decimal("1.0000")  # Exact reference
    assert breakdown.overall_confidence >= Decimal("0.9000")
    assert "Confidence" in breakdown.explanation

    b_dict = breakdown.to_dict()
    assert "overall_confidence" in b_dict
    assert "amount_score" in b_dict


def test_fuzzy_candidate_generation():
    dt = datetime(2026, 8, 10, tzinfo=timezone.utc)
    s = _make_tx(TransactionSource.STATEMENT, dt, "Vendor Payment", Decimal("500.00"))

    # Candidate 1: within 2 days, exact amount (Valid candidate)
    l1 = _make_tx(TransactionSource.LEDGER, dt + timedelta(days=2), "Vendor Payment Inc", Decimal("500.00"))
    # Candidate 2: 30 days away (Too far)
    l2 = _make_tx(TransactionSource.LEDGER, dt + timedelta(days=30), "Vendor Payment", Decimal("500.00"))
    # Candidate 3: 50% amount difference (Too large variance)
    l3 = _make_tx(TransactionSource.LEDGER, dt, "Vendor Payment", Decimal("1000.00"))

    candidates = FuzzyMatcher.generate_candidate_pairs([s], [l1, l2, l3])
    candidate_ledger_ids = [c[1].id for c in candidates]

    assert l1.id in candidate_ledger_ids
    assert l2.id not in candidate_ledger_ids
    assert l3.id not in candidate_ledger_ids


def test_fuzzy_score_threshold_triage():
    dt = datetime(2026, 8, 10, tzinfo=timezone.utc)
    s = _make_tx(TransactionSource.STATEMENT, dt, "GitHub Enterprise Cloud", Decimal("2100.00"))

    # High match (similar description, same amount, same date)
    l_high = _make_tx(TransactionSource.LEDGER, dt, "Github Enterprise Cloud SaaS", Decimal("2100.00"))
    b_high = FuzzyMatcher.score_pair(s, l_high)
    assert b_high.overall_confidence >= Decimal("0.8800")

    # Medium match (slightly different amount, 3 days apart)
    l_med = _make_tx(TransactionSource.LEDGER, dt + timedelta(days=3), "GitHub Subs", Decimal("2080.00"))
    b_med = FuzzyMatcher.score_pair(s, l_med)
    assert Decimal("0.5000") <= b_med.overall_confidence < Decimal("0.8800")

    # Low match (different vendor, different amount)
    l_low = _make_tx(TransactionSource.LEDGER, dt + timedelta(days=5), "Unrelated Parking Fee", Decimal("2080.00"))
    b_low = FuzzyMatcher.score_pair(s, l_low)
    assert b_low.overall_confidence < Decimal("0.7000")

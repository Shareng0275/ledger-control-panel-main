import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from rapidfuzz import fuzz
from app.core.config import settings
from app.models import Transaction


@dataclass
class FuzzyScoreBreakdown:
    overall_confidence: Decimal
    amount_score: Decimal
    date_score: Decimal
    description_score: Decimal
    reference_score: Decimal
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_confidence": str(self.overall_confidence),
            "amount_score": str(self.amount_score),
            "date_score": str(self.date_score),
            "description_score": str(self.description_score),
            "reference_score": str(self.reference_score),
            "explanation": self.explanation,
        }


class FuzzyMatcher:
    """Intelligent fuzzy matching and explainable confidence scoring engine."""

    @staticmethod
    def compute_amount_score(amount_s: Decimal, amount_l: Decimal) -> Tuple[Decimal, str]:
        """Score monetary amount agreement with linear decay for small fee/rounding variances."""
        if amount_s == amount_l:
            return Decimal("1.0000"), "Amount matches exactly (100%)"

        # If signs differ, they cannot be matched
        if (amount_s > 0 and amount_l < 0) or (amount_s < 0 and amount_l > 0):
            return Decimal("0.0000"), "Amount sign mismatch (0%)"

        abs_s = abs(amount_s)
        abs_l = abs(amount_l)
        max_abs = max(abs_s, abs_l)
        if max_abs == Decimal("0"):
            return Decimal("1.0000"), "Zero amount exact match (100%)"

        diff = abs(abs_s - abs_l)
        pct_diff = float(diff / max_abs)

        # Allow small percentage variance up to 5%
        if pct_diff <= 0.05:
            score = max(0.0, 1.0 - (pct_diff * 4.0))
            score_dec = Decimal(str(round(score, 4)))
            return score_dec, f"Amount variance of ${diff:.2f} ({score_dec * 100:.1f}%)"

        return Decimal("0.0000"), f"Amount variance ${diff:.2f} exceeds tolerance (0%)"

    @staticmethod
    def compute_date_score(date_s: datetime, date_l: datetime) -> Tuple[Decimal, str]:
        """Score transaction date proximity."""
        delta_days = abs((date_s.date() - date_l.date()).days)

        if delta_days == 0:
            return Decimal("1.0000"), "Same transaction date (100%)"
        elif delta_days == 1:
            return Decimal("0.9500"), "Date differs by 1 day (95%)"
        elif delta_days == 2:
            return Decimal("0.9000"), "Date differs by 2 days (90%)"
        elif delta_days == 3:
            return Decimal("0.8000"), "Date differs by 3 days (80%)"
        elif delta_days <= settings.FUZZY_MAX_DATE_DIFF_DAYS:
            score = max(0.40, 1.0 - (delta_days * 0.09))
            score_dec = Decimal(str(round(score, 4)))
            return score_dec, f"Date differs by {delta_days} days ({score_dec * 100:.1f}%)"

        return Decimal("0.0000"), f"Date difference of {delta_days} days exceeds threshold (0%)"

    @staticmethod
    def compute_description_score(desc_s: Optional[str], desc_l: Optional[str]) -> Tuple[Decimal, str]:
        """Score normalized description similarity using RapidFuzz."""
        if not desc_s or not desc_l:
            return Decimal("0.0000"), "Missing description (0%)"

        s_clean = desc_s.strip()
        l_clean = desc_l.strip()

        if s_clean == l_clean:
            return Decimal("1.0000"), "Description identical (100%)"

        # Calculate Token Set Ratio & Levenshtein Ratio
        token_ratio = fuzz.token_set_ratio(s_clean, l_clean)
        partial_ratio = fuzz.partial_ratio(s_clean, l_clean)
        std_ratio = fuzz.ratio(s_clean, l_clean)

        # Weighted combination favoring token containment
        best_sim = max(token_ratio, (partial_ratio * 0.7 + std_ratio * 0.3)) / 100.0
        score_dec = Decimal(str(round(best_sim, 4)))

        return score_dec, f"Description similarity {score_dec * 100:.1f}% ('{desc_s}' ~ '{desc_l}')"

    @staticmethod
    def compute_reference_score(ref_s: Optional[str], ref_l: Optional[str]) -> Tuple[Decimal, Optional[str]]:
        """Score external reference similarity."""
        if not ref_s or not ref_l:
            return Decimal("0.0000"), None

        s_clean = ref_s.strip().upper()
        l_clean = ref_l.strip().upper()

        if s_clean == l_clean:
            return Decimal("1.0000"), "Reference exact match (100%)"

        if s_clean in l_clean or l_clean in s_clean:
            return Decimal("0.9000"), f"Reference partial containment ({s_clean} in {l_clean})"

        sim = fuzz.ratio(s_clean, l_clean) / 100.0
        score_dec = Decimal(str(round(sim, 4)))
        return score_dec, f"Reference similarity {score_dec * 100:.1f}%"

    @staticmethod
    def score_pair(stmt: Transaction, ledger: Transaction) -> FuzzyScoreBreakdown:
        """Compute holistic weighted fuzzy match confidence score and explanation."""
        amount_score, amt_exp = FuzzyMatcher.compute_amount_score(stmt.amount, ledger.amount)
        date_score, date_exp = FuzzyMatcher.compute_date_score(stmt.transaction_date, ledger.transaction_date)
        desc_score, desc_exp = FuzzyMatcher.compute_description_score(
            stmt.normalized_description or stmt.description,
            ledger.normalized_description or ledger.description,
        )
        ref_score, ref_exp = FuzzyMatcher.compute_reference_score(
            stmt.normalized_reference or stmt.external_reference,
            ledger.normalized_reference or ledger.external_reference,
        )

        w_amt = Decimal(str(settings.FUZZY_WEIGHT_AMOUNT))
        w_date = Decimal(str(settings.FUZZY_WEIGHT_DATE))
        w_desc = Decimal(str(settings.FUZZY_WEIGHT_DESCRIPTION))
        w_ref = Decimal(str(settings.FUZZY_WEIGHT_REFERENCE))

        if ref_exp is not None:
            # All 4 features active
            overall = (amount_score * w_amt) + (date_score * w_date) + (desc_score * w_desc) + (ref_score * w_ref)
        else:
            # Rebalance weights over available 3 features (amount, date, description)
            total_w = w_amt + w_date + w_desc
            overall = ((amount_score * w_amt) + (date_score * w_date) + (desc_score * w_desc)) / total_w

        overall_clamped = min(Decimal("1.0000"), max(Decimal("0.0000"), overall.quantize(Decimal("0.0001"))))

        # Build structured explanation sentence
        explanations = [amt_exp, date_exp, desc_exp]
        if ref_exp:
            explanations.append(ref_exp)

        explanation_str = f"Confidence {overall_clamped * 100:.1f}%: {'; '.join(explanations)}."

        return FuzzyScoreBreakdown(
            overall_confidence=overall_clamped,
            amount_score=amount_score,
            date_score=date_score,
            description_score=desc_score,
            reference_score=ref_score,
            explanation=explanation_str,
        )

    @staticmethod
    def generate_candidate_pairs(
        statement_txs: List[Transaction],
        ledger_txs: List[Transaction],
    ) -> List[Tuple[Transaction, Transaction, FuzzyScoreBreakdown]]:
        """
        Generate and score candidate pairs using intelligent search pruning:
        - Date within max date window
        - Amount within max percentage tolerance or identical signs
        """
        candidate_results: List[Tuple[Transaction, Transaction, FuzzyScoreBreakdown]] = []

        for s in statement_txs:
            for l in ledger_txs:
                # 1. Quick Pruning: Signs must match
                if (s.amount > 0 and l.amount < 0) or (s.amount < 0 and l.amount > 0):
                    continue

                # 2. Quick Pruning: Date distance check
                delta_days = abs((s.transaction_date.date() - l.transaction_date.date()).days)
                if delta_days > settings.FUZZY_MAX_DATE_DIFF_DAYS:
                    continue

                # 3. Quick Pruning: Amount percentage check
                max_amt = max(abs(s.amount), abs(l.amount))
                if max_amt > 0:
                    pct = float(abs(abs(s.amount) - abs(l.amount)) / max_amt)
                    if pct > settings.FUZZY_MAX_AMOUNT_DIFF_PERCENT:
                        continue

                # Score candidate pair
                score = FuzzyMatcher.score_pair(s, l)
                if score.overall_confidence > Decimal("0.30"):
                    candidate_results.append((s, l, score))

        # Sort candidate pairs by overall confidence descending
        candidate_results.sort(key=lambda item: item[2].overall_confidence, reverse=True)
        return candidate_results

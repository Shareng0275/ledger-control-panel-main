import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    ExceptionPriority,
    ExceptionStatus,
    Match,
    MatchMethod,
    ReconciliationException,
    ReconciliationRun,
    Transaction,
    TransactionSource,
    TransactionStatus,
)
from app.schemas.insight import InsightsListResponse, RunInsight


class InsightsService:
    """
    AI Predictive Financial Anomaly Detection & Insights Engine.
    
    Implements 5 explainable, evidence-based anomaly detection algorithms:
    1. Unusual Amount Anomaly (Vendor & Portfolio Z-Score / Standard Deviation)
    2. Unusual Frequency Anomaly (Burst / Repetition deviation)
    3. Near Duplicate Anomaly (Fuzzy near-duplicate billing / duplicate debit)
    4. Suspicious Mismatch Anomaly (Reconciliation variance & reference mismatch)
    5. High-Risk Exception Anomaly (Critical exposure / unhedged breaks)
    """

    @classmethod
    async def get_insights(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        run_id: Optional[uuid.UUID] = None,
        severity_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> InsightsListResponse:
        """
        Executes all 5 anomaly detection passes against real PostgreSQL records.
        Applies strict organization isolation and optional filters.
        """
        # 1. Fetch organization transactions
        tx_query = select(Transaction).where(Transaction.organization_id == organization_id)
        if run_id:
            tx_query = tx_query.where(Transaction.reconciliation_run_id == run_id)
        tx_res = await db.execute(tx_query.order_by(Transaction.transaction_date.asc()))
        transactions = list(tx_res.scalars().all())

        # 2. Fetch organization exceptions
        exc_query = (
            select(ReconciliationException)
            .where(
                ReconciliationException.organization_id == organization_id,
                ReconciliationException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.REVIEWING]),
            )
            .options(
                selectinload(ReconciliationException.transaction),
                selectinload(ReconciliationException.best_candidate_transaction),
            )
        )
        if run_id:
            exc_query = exc_query.where(ReconciliationException.reconciliation_run_id == run_id)
        exc_res = await db.execute(exc_query)
        exceptions = list(exc_res.scalars().all())

        # 3. Fetch organization matches
        match_query = (
            select(Match)
            .where(Match.organization_id == organization_id)
            .options(
                selectinload(Match.statement_transaction),
                selectinload(Match.ledger_transaction),
            )
        )
        if run_id:
            match_query = match_query.where(Match.reconciliation_run_id == run_id)
        match_res = await db.execute(match_query)
        matches = list(match_res.scalars().all())

        # 4. Execute 5 Detection Passes
        all_insights: List[RunInsight] = []

        all_insights.extend(cls._detect_unusual_amounts(transactions, organization_id, run_id))
        all_insights.extend(cls._detect_unusual_frequency(transactions, organization_id, run_id))
        all_insights.extend(cls._detect_near_duplicates(transactions, organization_id, run_id))
        all_insights.extend(cls._detect_suspicious_mismatches(matches, exceptions, organization_id, run_id))
        all_insights.extend(cls._detect_high_risk_exceptions(exceptions, organization_id, run_id))

        # 5. Apply Filters
        filtered_insights: List[RunInsight] = []
        severity_counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        category_counts: Dict[str, int] = defaultdict(int)

        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        for insight in all_insights:
            sev = insight.severity.lower()
            cat = insight.category.lower()

            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            category_counts[cat] += 1

            if severity_filter and sev != severity_filter.lower():
                continue
            if category_filter and cat != category_filter.lower():
                continue

            filtered_insights.append(insight)

        # Sort insights by severity descending (critical -> high -> medium -> low)
        filtered_insights.sort(key=lambda x: severity_rank.get(x.severity.lower(), 0), reverse=True)

        return InsightsListResponse(
            insights=filtered_insights,
            total=len(filtered_insights),
            severity_counts=severity_counts,
            category_counts=dict(category_counts),
        )

    # ─── 1. Unusual Amount Detection ─────────────────────────────────────────
    @classmethod
    def _detect_unusual_amounts(
        cls,
        transactions: List[Transaction],
        organization_id: uuid.UUID,
        run_id: Optional[uuid.UUID],
    ) -> List[RunInsight]:
        """Detect amounts significantly deviating from vendor or portfolio baselines using Z-Scores."""
        insights: List[RunInsight] = []
        if len(transactions) < 3:
            return insights

        # Group amounts by normalized description (vendor)
        vendor_groups: Dict[str, List[Transaction]] = defaultdict(list)
        all_amounts: List[float] = []

        for tx in transactions:
            key = (tx.normalized_description or tx.description or "").strip().lower()
            # Clean vendor key (take first 3 tokens)
            vendor_key = " ".join(key.split()[:3]) if key else "unspecified"
            vendor_groups[vendor_key].append(tx)
            all_amounts.append(float(abs(tx.amount)))

        # (a) Vendor-Level Leave-One-Out Robust Z-Score Analysis
        for vendor_key, v_txs in vendor_groups.items():
            if len(v_txs) >= 3:
                v_amounts = [float(abs(t.amount)) for t in v_txs]
                for i, tx in enumerate(v_txs):
                    amt = float(abs(tx.amount))
                    other_amts = [v_amounts[j] for j in range(len(v_amounts)) if j != i]
                    if not other_amts:
                        continue
                    
                    mean_other = sum(other_amts) / len(other_amts)
                    if len(other_amts) > 1:
                        var_other = sum((x - mean_other) ** 2 for x in other_amts) / (len(other_amts) - 1)
                        stdev_other = math.sqrt(var_other)
                    else:
                        stdev_other = max(10.0, mean_other * 0.1)

                    effective_stdev = max(stdev_other, max(10.0, mean_other * 0.05))
                    z_score = (amt - mean_other) / effective_stdev

                    if z_score >= 2.5 and (amt - mean_other) >= 100.0:
                        severity = "critical" if z_score >= 4.0 else ("high" if z_score >= 3.0 else "medium")
                        insights.append(
                            RunInsight(
                                id=uuid.uuid4(),
                                organization_id=organization_id,
                                related_transaction_id=tx.id,
                                reconciliation_run_id=tx.reconciliation_run_id or run_id,
                                category="unusual_amount",
                                type="unusual_amount",
                                title=f"Unusual Transaction Amount ({tx.currency} {tx.amount:.2f})",
                                severity=severity,
                                explanation=(
                                    f"Transaction amount of {tx.currency} {tx.amount:.2f} is {z_score:.1f} standard deviations "
                                    f"above the baseline historical average of {tx.currency} {mean_other:.2f} for '{tx.description}' "
                                    f"(historical baseline range: {min(other_amts):.2f} - {max(other_amts):.2f})."
                                ),
                                message=(
                                    f"Transaction amount of {tx.currency} {tx.amount:.2f} is {z_score:.1f} standard deviations "
                                    f"above vendor average of {tx.currency} {mean_other:.2f}."
                                ),
                                score=round(min(1.0, z_score / 5.0), 4),
                                score_details={
                                    "z_score": round(z_score, 2),
                                    "vendor_mean": round(mean_other, 2),
                                    "vendor_stdev": round(effective_stdev, 2),
                                    "sample_size": len(v_txs),
                                },
                            )
                        )

        # (b) Overall Portfolio Extreme Outlier Detection
        if len(all_amounts) >= 5:
            p_mean = sum(all_amounts) / len(all_amounts)
            p_variance = sum((x - p_mean) ** 2 for x in all_amounts) / max(1, len(all_amounts) - 1)
            p_stdev = math.sqrt(p_variance)

            if p_stdev > 20.0:
                for tx in transactions:
                    amt = float(abs(tx.amount))
                    p_z = (amt - p_mean) / p_stdev
                    # Flag extreme portfolio outliers exceeding $5,000 and 2.5 stdev
                    if p_z >= 2.5 and amt >= 5000.0:
                        # Avoid duplicate insight if already flagged at vendor level
                        if not any(i.related_transaction_id == tx.id and i.category == "unusual_amount" for i in insights):
                            insights.append(
                                RunInsight(
                                    id=uuid.uuid4(),
                                    organization_id=organization_id,
                                    related_transaction_id=tx.id,
                                    reconciliation_run_id=tx.reconciliation_run_id or run_id,
                                    category="unusual_amount",
                                    type="unusual_amount",
                                    title=f"Significant Outlier Amount ({tx.currency} {tx.amount:.2f})",
                                    severity="critical" if p_z >= 4.0 else "high",
                                    explanation=(
                                        f"Transaction amount of {tx.currency} {tx.amount:.2f} on {tx.transaction_date.strftime('%Y-%m-%d')} "
                                        f"is {p_z:.1f} standard deviations above the organizational average ({tx.currency} {p_mean:.2f})."
                                    ),
                                    message=f"Significant outlier: {p_z:.1f} standard deviations above portfolio average.",
                                    score=round(min(1.0, p_z / 5.0), 4),
                                    score_details={"portfolio_z_score": round(p_z, 2), "portfolio_mean": round(p_mean, 2)},
                                )
                            )

        return insights

    # ─── 2. Unusual Frequency Detection ──────────────────────────────────────
    @classmethod
    def _detect_unusual_frequency(
        cls,
        transactions: List[Transaction],
        organization_id: uuid.UUID,
        run_id: Optional[uuid.UUID],
    ) -> List[RunInsight]:
        """Detect abnormal burst repetitions of transactions for the same vendor/account."""
        insights: List[RunInsight] = []
        if len(transactions) < 3:
            return insights

        # Group by (date, vendor_token)
        day_vendor_map: Dict[Tuple[Any, str], List[Transaction]] = defaultdict(list)
        for tx in transactions:
            d = tx.transaction_date.date()
            key = (tx.normalized_description or tx.description or "").strip().lower()
            vendor_token = " ".join(key.split()[:2]) if key else "unspecified"
            day_vendor_map[(d, vendor_token)].append(tx)

        for (d, vendor_token), group in day_vendor_map.items():
            count = len(group)
            if count >= 3:
                total_amt = sum(t.amount for t in group)
                severity = "critical" if count >= 5 else ("high" if count >= 4 else "medium")
                primary_tx = group[0]
                insights.append(
                    RunInsight(
                        id=uuid.uuid4(),
                        organization_id=organization_id,
                        related_transaction_id=primary_tx.id,
                        reconciliation_run_id=primary_tx.reconciliation_run_id or run_id,
                        category="unusual_frequency",
                        type="unusual_frequency",
                        title=f"Unusual Transaction Frequency ({count} items on {d})",
                        severity=severity,
                        explanation=(
                            f"Detected an abnormal velocity of {count} transactions totaling "
                            f"{primary_tx.currency} {total_amt:.2f} for '{primary_tx.description}' "
                            f"within a single day ({d}). Typical cadence is 1 transaction per billing cycle."
                        ),
                        message=f"{count} transactions detected for '{primary_tx.description}' on {d}.",
                        score=round(min(1.0, count / 5.0), 4),
                        score_details={
                            "burst_count": count,
                            "date": str(d),
                            "total_amount": float(total_amt),
                            "transaction_ids": [str(t.id) for t in group],
                        },
                    )
                )

        return insights

    # ─── 3. Near Duplicate Detection ─────────────────────────────────────────
    @classmethod
    def _detect_near_duplicates(
        cls,
        transactions: List[Transaction],
        organization_id: uuid.UUID,
        run_id: Optional[uuid.UUID],
    ) -> List[RunInsight]:
        """Detect near-duplicate transactions with identical amounts and close dates/descriptions."""
        insights: List[RunInsight] = []
        if len(transactions) < 2:
            return insights

        # Index transactions by exact absolute amount
        amt_map: Dict[Decimal, List[Transaction]] = defaultdict(list)
        for tx in transactions:
            amt_map[abs(tx.amount)].append(tx)

        seen_pairs = set()

        for amt, tx_list in amt_map.items():
            if len(tx_list) >= 2:
                for i in range(len(tx_list)):
                    for j in range(i + 1, len(tx_list)):
                        t1 = tx_list[i]
                        t2 = tx_list[j]
                        if t1.id == t2.id or t1.source != t2.source:
                            continue

                        pair_key = tuple(sorted([t1.id, t2.id]))
                        if pair_key in seen_pairs:
                            continue

                        # Check date closeness (within 2 days)
                        date_diff = abs((t1.transaction_date.date() - t2.transaction_date.date()).days)
                        if date_diff <= 2:
                            # Check string similarity
                            d1 = t1.normalized_description or t1.description
                            d2 = t2.normalized_description or t2.description
                            similarity = fuzz.token_sort_ratio(d1, d2) / 100.0

                            if similarity >= 0.70:
                                seen_pairs.add(pair_key)
                                severity = "high" if date_diff == 0 else "medium"
                                insights.append(
                                    RunInsight(
                                        id=uuid.uuid4(),
                                        organization_id=organization_id,
                                        related_transaction_id=t1.id,
                                        reconciliation_run_id=t1.reconciliation_run_id or run_id,
                                        category="near_duplicate",
                                        type="near_duplicate",
                                        title=f"Potential Duplicate Charge ({t1.currency} {amt:.2f})",
                                        severity=severity,
                                        explanation=(
                                            f"Potential duplicate billing detected: Two transactions of {t1.currency} {amt:.2f} "
                                            f"occurred {date_diff} day(s) apart with {similarity * 100:.0f}% description similarity "
                                            f"('{t1.description}' on {t1.transaction_date.strftime('%Y-%m-%d')} vs "
                                            f"'{t2.description}' on {t2.transaction_date.strftime('%Y-%m-%d')})."
                                        ),
                                        message=f"Duplicate billing alert: {t1.currency} {amt:.2f} detected {date_diff} day(s) apart.",
                                        score=round(similarity, 4),
                                        score_details={
                                            "tx_id_1": str(t1.id),
                                            "tx_id_2": str(t2.id),
                                            "date_diff_days": date_diff,
                                            "similarity": round(similarity, 2),
                                            "amount": float(amt),
                                        },
                                    )
                                )

        return insights

    # ─── 4. Suspicious Mismatch Detection ────────────────────────────────────
    @classmethod
    def _detect_suspicious_mismatches(
        cls,
        matches: List[Match],
        exceptions: List[ReconciliationException],
        organization_id: uuid.UUID,
        run_id: Optional[uuid.UUID],
    ) -> List[RunInsight]:
        """Detect reconciliation matches or exceptions with suspicious amount variances or inverted signs."""
        insights: List[RunInsight] = []

        # (a) Check fuzzy matches with significant amount differences
        for match in matches:
            if match.statement_transaction and match.ledger_transaction:
                s_amt = abs(match.statement_transaction.amount)
                l_amt = abs(match.ledger_transaction.amount)
                diff = abs(s_amt - l_amt)
                if diff > Decimal("20.00"):
                    pct = (diff / max(s_amt, Decimal("1.00"))) * 100
                    severity = "critical" if diff >= Decimal("1000.00") else ("high" if diff >= Decimal("100.00") else "medium")
                    insights.append(
                        RunInsight(
                            id=uuid.uuid4(),
                            organization_id=organization_id,
                            related_transaction_id=match.statement_transaction_id,
                            reconciliation_run_id=match.reconciliation_run_id or run_id,
                            category="suspicious_mismatch",
                            type="suspicious_mismatch",
                            title=f"Reconciliation Variance Discrepancy (${diff:.2f})",
                            severity=severity,
                            explanation=(
                                f"Suspicious match variance: Statement record (${s_amt:.2f}) differs from Ledger candidate "
                                f"(${l_amt:.2f}) by ${diff:.2f} ({pct:.1f}% variance) on matched pair."
                            ),
                            message=f"Reconciliation variance of ${diff:.2f} between matched statement and ledger.",
                            score=round(float(min(Decimal("1.0"), diff / Decimal("1000.0"))), 4),
                            score_details={
                                "statement_amount": float(s_amt),
                                "ledger_amount": float(l_amt),
                                "difference": float(diff),
                                "variance_percent": round(float(pct), 2),
                            },
                        )
                    )

        # (b) Check exceptions where reference matched but amount was different
        for exc in exceptions:
            if exc.transaction and exc.best_candidate_transaction:
                tx = exc.transaction
                cand = exc.best_candidate_transaction
                if tx.normalized_reference and cand.normalized_reference and tx.normalized_reference == cand.normalized_reference:
                    diff = abs(tx.amount - cand.amount)
                    if diff > Decimal("0.00"):
                        insights.append(
                            RunInsight(
                                id=uuid.uuid4(),
                                organization_id=organization_id,
                                related_transaction_id=tx.id,
                                exception_id=exc.id,
                                reconciliation_run_id=exc.reconciliation_run_id or run_id,
                                category="suspicious_mismatch",
                                type="suspicious_mismatch",
                                title=f"Reference Collision with Mismatched Amount (${diff:.2f})",
                                severity="critical" if diff >= Decimal("500.00") else "high",
                                explanation=(
                                    f"Exact reference match ('{tx.external_reference}') failed reconciliation due to amount discrepancy: "
                                    f"Statement amount ${tx.amount:.2f} vs Ledger amount ${cand.amount:.2f} (variance: ${diff:.2f})."
                                ),
                                message=f"Reference '{tx.external_reference}' matched but amounts differ by ${diff:.2f}.",
                                score=0.90,
                                score_details={
                                    "reference": tx.external_reference,
                                    "statement_amount": float(tx.amount),
                                    "candidate_amount": float(cand.amount),
                                    "difference": float(diff),
                                },
                            )
                        )

        return insights

    # ─── 5. High-Risk Exception Detection ────────────────────────────────────
    @classmethod
    def _detect_high_risk_exceptions(
        cls,
        exceptions: List[ReconciliationException],
        organization_id: uuid.UUID,
        run_id: Optional[uuid.UUID],
    ) -> List[RunInsight]:
        """Prioritize critical unresolved exceptions with material financial exposure."""
        insights: List[RunInsight] = []

        for exc in exceptions:
            tx = exc.transaction
            if not tx:
                continue

            amt = abs(tx.amount)
            is_critical = exc.priority in [ExceptionPriority.HIGH, ExceptionPriority.CRITICAL] or amt >= Decimal("5000.00")

            if is_critical:
                severity = "critical" if (amt >= Decimal("10000.00") or exc.priority == ExceptionPriority.CRITICAL) else "high"
                cand_info = "with no matching counterpart found in ledger records" if not exc.best_candidate_transaction else "with unresolved matching candidates"
                insights.append(
                    RunInsight(
                        id=uuid.uuid4(),
                        organization_id=organization_id,
                        related_transaction_id=tx.id,
                        exception_id=exc.id,
                        reconciliation_run_id=exc.reconciliation_run_id or run_id,
                        category="high_risk_exception",
                        type="high_risk_exception",
                        title=f"High-Exposure Unresolved Exception ({tx.currency} {amt:.2f})",
                        severity=severity,
                        explanation=(
                            f"Material financial break: [{exc.priority.value.upper()}] transaction of {tx.currency} {amt:.2f} "
                            f"('{tx.description}') on {tx.transaction_date.strftime('%Y-%m-%d')} remains open {cand_info}. "
                            f"Reason: {exc.reason_text}"
                        ),
                        message=f"High-exposure break of {tx.currency} {amt:.2f} remains open.",
                        score=round(float(min(Decimal("1.0"), amt / Decimal("10000.0"))), 4),
                        score_details={
                            "amount": float(amt),
                            "priority": exc.priority.value if hasattr(exc.priority, "value") else str(exc.priority),
                            "has_candidate": exc.best_candidate_transaction_id is not None,
                        },
                    )
                )

        return insights

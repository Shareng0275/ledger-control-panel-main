import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AuditLog,
    ExceptionPriority,
    ExceptionStatus,
    ReconciliationException,
    ReconciliationRun,
    Transaction,
    TransactionSource,
    TransactionStatus,
    User,
)
from app.schemas.ask import AskResponse
from app.services.forecasting_service import ForecastingService
from app.services.llm_provider import LLMProvider, get_llm_provider

logger = logging.getLogger("ledger_control.ask")


class AskService:
    """
    Secure Financial AI Assistant Engine.
    
    Security & Control Model:
    1. Zero dynamic SQL generation — the LLM is NEVER given database access.
    2. All data retrieval is pre-parameterized and strictly scoped to the authorized organization.
    3. The LLM processes only safe, sanitized in-memory data representations.
    4. Real PostgreSQL database rows are returned as verified supporting evidence.
    """

    SYSTEM_PROMPT = (
        "You are Ledger Control's Financial Intelligence AI Assistant.\n"
        "Your task is to analyze financial reconciliation records, exceptions, transactions, and cash forecasts.\n"
        "Strict Security & Financial Rules:\n"
        "1. Never invent financial transactions, IDs, descriptions, or amounts.\n"
        "2. Only use the provided financial context to answer the user's question.\n"
        "3. Clearly distinguish between confirmed facts in the data and unavailable information.\n"
        "4. Be precise with financial numbers, dates, and exception reasons.\n"
        "5. If no relevant records exist in the context, explicitly inform the user that no records were found."
    )

    @classmethod
    async def process_question(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user: User,
        question: str,
        llm_provider: Optional[LLMProvider] = None,
    ) -> AskResponse:
        """
        Executes the controlled Ask AI workflow:
        Validate -> Classify Intent -> Retrieve Scoped Data -> Build Context -> LLM/Synthesize -> Audit -> Return
        """
        cleaned_question = question.strip()

        # 1. Determine Intent
        intent = cls._classify_intent(cleaned_question)

        # 2. Retrieve Authorized Scoped Financial Data
        retrieved_data, supporting_rows = await cls._retrieve_scoped_data(
            db=db,
            organization_id=organization_id,
            intent=intent,
            question=cleaned_question,
        )

        # 3. Build Safe Prompt Context
        context_str = cls._build_context_string(retrieved_data, intent)
        user_prompt = f"User Question: {cleaned_question}\n\nVerified Financial Records:\n{context_str}"

        # 4. Generate Answer via Provider or Deterministic Synthesizer
        provider = llm_provider or get_llm_provider()
        llm_answer = None
        try:
            llm_answer = await provider.generate_response(
                system_prompt=cls.SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except Exception as e:
            logger.warning(f"LLM provider invocation failed: {e}")

        if not llm_answer:
            # Fallback to explainable rule-based synthesis using real DB data
            llm_answer = cls._deterministic_synthesis(
                question=cleaned_question,
                intent=intent,
                data=retrieved_data,
                supporting_rows=supporting_rows,
            )

        # 5. Audit Log Event (without storing raw secrets or sensitive PII)
        audit_entry = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_id=user.id,
            action="ai.ask",
            entity_type="ai_query",
            details={
                "intent": intent,
                "question_length": len(cleaned_question),
                "supporting_rows_count": len(supporting_rows),
            },
        )
        db.add(audit_entry)
        await db.commit()

        return AskResponse(
            answer=llm_answer,
            supporting_rows=supporting_rows,
        )

    @classmethod
    def _classify_intent(cls, question: str) -> str:
        """Classify user question into a financial intelligence domain."""
        q = question.lower()
        if any(k in q for k in ["fail", "unmatch", "mismatch", "exception", "break", "discrepan", "why"]):
            return "exceptions"
        elif any(k in q for k in ["risk", "critical", "danger", "urgent", "material", "large", "biggest"]):
            return "high_risk"
        elif any(k in q for k in ["forecast", "runway", "burn", "project", "future", "cash balance", "liquidity"]):
            return "forecast"
        elif any(k in q for k in ["run", "status", "reconcil", "how many", "summary", "overview", "rate"]):
            return "reconciliation_summary"
        elif any(k in q for k in ["transaction", "deposit", "payment", "vendor", "statement", "ledger"]):
            return "transactions"
        return "general"

    @classmethod
    async def _retrieve_scoped_data(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        intent: str,
        question: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Safely retrieves authorized PostgreSQL records based on classified intent.
        Strictly scopes all queries to organization_id.
        """
        data: Dict[str, Any] = {}
        supporting_rows: List[Dict[str, Any]] = []

        if intent in ["exceptions", "high_risk", "general"]:
            # Retrieve open/reviewing exceptions
            exc_stmt = (
                select(ReconciliationException)
                .where(
                    ReconciliationException.organization_id == organization_id,
                    ReconciliationException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.REVIEWING]),
                )
                .options(
                    selectinload(ReconciliationException.transaction),
                    selectinload(ReconciliationException.best_candidate_transaction),
                )
                .order_by(
                    ReconciliationException.priority.desc(),
                    ReconciliationException.created_at.desc(),
                )
                .limit(10)
            )
            exc_res = await db.execute(exc_stmt)
            exceptions = list(exc_res.scalars().all())
            data["exceptions"] = []

            for exc in exceptions:
                tx = exc.transaction
                cand = exc.best_candidate_transaction
                exc_dict = {
                    "id": str(exc.id),
                    "type": "exception",
                    "priority": exc.priority.value if hasattr(exc.priority, "value") else str(exc.priority),
                    "status": exc.status.value if hasattr(exc.status, "value") else str(exc.status),
                    "reason": exc.reason_text,
                    "date": tx.transaction_date.strftime("%Y-%m-%d") if tx else None,
                    "description": tx.description if tx else "Unknown Transaction",
                    "amount": f"{tx.amount:.2f}" if tx else None,
                    "currency": tx.currency if tx else "USD",
                    "candidate_description": cand.description if cand else None,
                    "candidate_amount": f"{cand.amount:.2f}" if cand else None,
                }
                data["exceptions"].append(exc_dict)
                supporting_rows.append(exc_dict)

        if intent in ["reconciliation_summary", "general", "exceptions"]:
            # Retrieve latest reconciliation run
            run_stmt = (
                select(ReconciliationRun)
                .where(ReconciliationRun.organization_id == organization_id)
                .order_by(ReconciliationRun.created_at.desc())
                .limit(1)
            )
            run_res = await db.execute(run_stmt)
            latest_run = run_res.scalar_one_or_none()
            if latest_run:
                run_dict = {
                    "id": str(latest_run.id),
                    "type": "reconciliation_run",
                    "status": latest_run.status.value if hasattr(latest_run.status, "value") else str(latest_run.status),
                    "total_transactions": latest_run.total_transactions,
                    "matched_count": latest_run.matched_count,
                    "exception_count": latest_run.exception_count,
                    "pending_review_count": latest_run.pending_review_count,
                    "total_value_reconciled": f"{latest_run.total_value_reconciled:.2f}",
                    "average_confidence": f"{latest_run.average_confidence:.4f}" if latest_run.average_confidence else None,
                }
                data["latest_run"] = run_dict
                supporting_rows.append(run_dict)

        if intent in ["transactions", "general"]:
            # Retrieve recent transactions
            tx_stmt = (
                select(Transaction)
                .where(Transaction.organization_id == organization_id)
                .order_by(Transaction.transaction_date.desc())
                .limit(10)
            )
            tx_res = await db.execute(tx_stmt)
            transactions = list(tx_res.scalars().all())
            data["transactions"] = []

            for tx in transactions:
                t_dict = {
                    "id": str(tx.id),
                    "type": "transaction",
                    "date": tx.transaction_date.strftime("%Y-%m-%d"),
                    "description": tx.description,
                    "amount": f"{tx.amount:.2f}",
                    "currency": tx.currency,
                    "source": tx.source.value if hasattr(tx.source, "value") else str(tx.source),
                    "status": tx.status.value if hasattr(tx.status, "value") else str(tx.status),
                    "reference": tx.external_reference,
                }
                data["transactions"].append(t_dict)
                supporting_rows.append(t_dict)

        if intent in ["forecast"]:
            try:
                fc = await ForecastingService.generate_forecast(db, organization_id, "30d")
                if not fc.is_empty and fc.analytics:
                    fc_dict = {
                        "id": "forecast-30d",
                        "type": "forecast",
                        "current_cash_balance": f"{fc.analytics.current_cash_balance:.2f}",
                        "projected_ending_cash": f"{fc.analytics.projected_ending_cash:.2f}",
                        "net_projected_change": f"{fc.analytics.net_projected_change:.2f}",
                        "trend_direction": fc.analytics.trend_direction,
                        "historical_daily_volatility": f"{fc.analytics.historical_daily_volatility:.2f}",
                        "confidence": f"{fc.confidence:.4f}" if fc.confidence else None,
                    }
                    data["forecast"] = fc_dict
                    supporting_rows.append(fc_dict)
            except Exception as e:
                logger.warning(f"Forecast retrieval in ask service failed: {e}")

        return data, supporting_rows

    @classmethod
    def _build_context_string(cls, data: Dict[str, Any], intent: str) -> str:
        """Construct sanitized, structured context string for LLM processing."""
        lines = []

        if "latest_run" in data:
            r = data["latest_run"]
            lines.append(
                f"- Reconciliation Run Summary: Status={r['status']}, Total Transactions={r['total_transactions']}, "
                f"Matched={r['matched_count']}, Exceptions={r['exception_count']}, Pending Review={r['pending_review_count']}, "
                f"Total Value Reconciled=${r['total_value_reconciled']}, Avg Confidence={r['average_confidence'] or 'N/A'}"
            )

        if "exceptions" in data and data["exceptions"]:
            lines.append(f"\n- Active Exceptions ({len(data['exceptions'])} items):")
            for e in data["exceptions"]:
                lines.append(
                    f"  * Exception ID {e['id']}: [{e['priority'].upper()}] {e['description']} (${e['amount']} {e['currency']}) "
                    f"on {e['date']} - Reason: {e['reason']}"
                )
        elif "exceptions" in data:
            lines.append("\n- Active Exceptions: None found.")

        if "transactions" in data and data["transactions"]:
            lines.append(f"\n- Recent Transactions ({len(data['transactions'])} items):")
            for t in data["transactions"]:
                lines.append(
                    f"  * Transaction {t['id']}: {t['description']} (${t['amount']} {t['currency']}) "
                    f"on {t['date']} | Status={t['status']} | Source={t['source']}"
                )

        if "forecast" in data:
            f = data["forecast"]
            lines.append(
                f"\n- Cash Forecast (30-Day): Starting Cash=${f['current_cash_balance']}, "
                f"Projected Ending Cash=${f['projected_ending_cash']}, Net Change=${f['net_projected_change']}, "
                f"Trend={f['trend_direction'].upper()}, Volatility=${f['historical_daily_volatility']}"
            )

        if not lines:
            return "No financial records found for this organization."

        return "\n".join(lines)

    @classmethod
    def _deterministic_synthesis(
        cls,
        question: str,
        intent: str,
        data: Dict[str, Any],
        supporting_rows: List[Dict[str, Any]],
    ) -> str:
        """
        Synthesizes an explainable, fact-checked financial response based solely
        on the retrieved database records. Guarantees zero hallucinations.
        """
        if not supporting_rows:
            return (
                "No financial records or exceptions were found matching your inquiry for this organization. "
                "Please verify that statement and ledger files have been ingested."
            )

        if intent == "exceptions":
            exceptions = data.get("exceptions", [])
            if not exceptions:
                return "There are currently no open or unresolved exceptions in your organization."
            
            summary_parts = [f"Found {len(exceptions)} active exception(s) requiring attention:"]
            for exc in exceptions[:5]:
                desc = exc.get("description", "Transaction")
                amt = exc.get("amount", "0.00")
                curr = exc.get("currency", "USD")
                date_str = exc.get("date", "N/A")
                reason = exc.get("reason", "Unmatched transaction")
                prio = exc.get("priority", "medium").upper()
                summary_parts.append(f"• [{prio}] {desc} ({curr} {amt} on {date_str}): {reason}")
            
            if len(exceptions) > 5:
                summary_parts.append(f"and {len(exceptions) - 5} additional exception(s).")
            return "\n".join(summary_parts)

        elif intent == "high_risk":
            exceptions = data.get("exceptions", [])
            high_risk = [e for e in exceptions if e.get("priority") in ["high", "critical"]]
            if not high_risk:
                return "No high-risk or critical exceptions are currently flagged in your organization."
            
            parts = [f"Identified {len(high_risk)} high-priority/critical exception(s):"]
            for hr in high_risk:
                parts.append(f"• {hr['description']} ({hr['currency']} {hr['amount']} on {hr['date']}): {hr['reason']}")
            return "\n".join(parts)

        elif intent == "reconciliation_summary":
            r = data.get("latest_run")
            if not r:
                return "No reconciliation run history was found for this organization."
            return (
                f"Latest Reconciliation Run Summary (Status: {r['status']}):\n"
                f"• Total Transactions: {r['total_transactions']}\n"
                f"• Matched: {r['matched_count']} (${r['total_value_reconciled']} reconciled)\n"
                f"• Exceptions: {r['exception_count']}\n"
                f"• Pending Review: {r['pending_review_count']}\n"
                f"• Average Confidence: {r['average_confidence'] or 'N/A'}"
            )

        elif intent == "forecast":
            f = data.get("forecast")
            if not f:
                return "Insufficient historical transaction data to generate a cash forecast."
            return (
                f"Cash Position & 30-Day Forecast:\n"
                f"• Current Cash Position: ${f['current_cash_balance']}\n"
                f"• Projected Ending Cash: ${f['projected_ending_cash']} (Net change: ${f['net_projected_change']})\n"
                f"• Trajectory Trend: {f['trend_direction'].title()}\n"
                f"• Daily Volatility: ${f['historical_daily_volatility']}"
            )

        elif intent == "transactions":
            txs = data.get("transactions", [])
            parts = [f"Retrieved {len(txs)} recent transaction(s):"]
            for t in txs[:5]:
                parts.append(f"• {t['date']}: {t['description']} - {t['currency']} {t['amount']} ({t['status']})")
            return "\n".join(parts)

        else:
            return (
                f"Financial Intelligence Overview: Found {len(supporting_rows)} relevant database record(s) "
                f"for your query across recent runs, transactions, and exceptions."
            )

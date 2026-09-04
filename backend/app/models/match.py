import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import Enum, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MatchMethod

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.reconciliation_run import ReconciliationRun
    from app.models.transaction import Transaction


class Match(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Pairs a Statement Transaction with a Ledger Transaction.
    Stores confidence metrics and granular JSONB scoring details.
    """
    __tablename__ = "matches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    statement_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ledger_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method: Mapped[MatchMethod] = mapped_column(
        Enum(MatchMethod, name="match_method", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )
    score_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="matches")
    reconciliation_run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", back_populates="matches")
    statement_transaction: Mapped["Transaction"] = relationship(
        "Transaction", foreign_keys=[statement_transaction_id]
    )
    ledger_transaction: Mapped["Transaction"] = relationship(
        "Transaction", foreign_keys=[ledger_transaction_id]
    )

    __table_args__ = (
        Index("ix_matches_org_run", "organization_id", "reconciliation_run_id"),
        Index("ix_matches_statement_tx", "statement_transaction_id"),
        Index("ix_matches_ledger_tx", "ledger_transaction_id"),
    )

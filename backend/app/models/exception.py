import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ExceptionPriority, ExceptionStatus

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.reconciliation_run import ReconciliationRun
    from app.models.transaction import Transaction
    from app.models.user import User


class Exception(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Reconciliation discrepancies, unmatched transactions, or confidence issues
    requiring manual analyst or automated resolution.
    """
    __tablename__ = "exceptions"

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
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    best_candidate_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[ExceptionPriority] = mapped_column(
        Enum(ExceptionPriority, name="exception_priority", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ExceptionPriority.MEDIUM,
        index=True,
    )
    status: Mapped[ExceptionStatus] = mapped_column(
        Enum(ExceptionStatus, name="exception_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ExceptionStatus.OPEN,
        index=True,
    )
    resolution_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="exceptions")
    reconciliation_run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", back_populates="exceptions")
    transaction: Mapped["Transaction"] = relationship("Transaction", foreign_keys=[transaction_id])
    best_candidate_transaction: Mapped[Optional["Transaction"]] = relationship(
        "Transaction", foreign_keys=[best_candidate_transaction_id]
    )
    resolver: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("ix_exceptions_org_status_priority", "organization_id", "status", "priority"),
        Index("ix_exceptions_org_run", "organization_id", "reconciliation_run_id"),
    )

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ReconciliationStatus

if TYPE_CHECKING:
    from app.models.exception import Exception as ReconciliationException
    from app.models.match import Match
    from app.models.organization import Organization
    from app.models.transaction import Transaction
    from app.models.upload import Upload
    from app.models.user import User


class ReconciliationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Execution run combining a Statement Upload and a Ledger Upload for matching.
    Stores aggregate financial reconciliation metrics, status, and timestamps.
    """
    __tablename__ = "reconciliation_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    statement_upload_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ledger_upload_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(
            ReconciliationStatus,
            name="reconciliation_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ReconciliationStatus.PENDING,
        index=True,
    )

    total_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exception_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Strictly Numeric for monetary values and confidence scores
    total_value_reconciled: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    average_confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="reconciliation_runs")
    statement_upload: Mapped[Optional["Upload"]] = relationship("Upload", foreign_keys=[statement_upload_id])
    ledger_upload: Mapped[Optional["Upload"]] = relationship("Upload", foreign_keys=[ledger_upload_id])
    creator: Mapped[Optional["User"]] = relationship("User")

    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="reconciliation_run"
    )
    matches: Mapped[List["Match"]] = relationship(
        "Match", back_populates="reconciliation_run", cascade="all, delete-orphan"
    )
    exceptions: Mapped[List["ReconciliationException"]] = relationship(
        "Exception", back_populates="reconciliation_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Optimized for status polling and dashboard listings
        Index("ix_reconciliation_runs_org_status", "organization_id", "status"),
        Index("ix_reconciliation_runs_id_status", "id", "status"),
    )

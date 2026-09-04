import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TransactionSource, TransactionStatus

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.reconciliation_run import ReconciliationRun
    from app.models.upload import Upload


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Financial transaction record extracted from Bank Statements or Gateway/Internal Ledgers.
    Stores strict Decimal monetary values and JSONB raw payload.
    """
    __tablename__ = "transactions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reconciliation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[TransactionSource] = mapped_column(
        Enum(TransactionSource, name="transaction_source", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Strictly Numeric for financial precision (NEVER float)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    external_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    normalized_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    normalized_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TransactionStatus.PENDING_REVIEW,
        index=True,
    )
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    raw_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="transactions")
    reconciliation_run: Mapped[Optional["ReconciliationRun"]] = relationship(
        "ReconciliationRun", back_populates="transactions"
    )
    upload: Mapped["Upload"] = relationship("Upload", back_populates="transactions")

    __table_args__ = (
        # Optimized lookup and filtering indexes
        Index("ix_transactions_org_status", "organization_id", "status"),
        Index("ix_transactions_org_run", "organization_id", "reconciliation_run_id"),
        Index("ix_transactions_org_date", "organization_id", "transaction_date"),
        Index("ix_transactions_org_hash", "organization_id", "normalized_hash"),
    )

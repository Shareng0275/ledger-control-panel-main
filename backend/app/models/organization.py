import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.exception import Exception as ReconciliationException
    from app.models.match import Match
    from app.models.membership import Membership
    from app.models.reconciliation_run import ReconciliationRun
    from app.models.transaction import Transaction
    from app.models.upload import Upload


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tenant root entity for multi-tenant isolation.
    Every financial dataset, run, and transaction belongs to an organization.
    """
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    # Relationships
    memberships: Mapped[List["Membership"]] = relationship(
        "Membership", back_populates="organization", cascade="all, delete-orphan"
    )
    uploads: Mapped[List["Upload"]] = relationship(
        "Upload", back_populates="organization", cascade="all, delete-orphan"
    )
    reconciliation_runs: Mapped[List["ReconciliationRun"]] = relationship(
        "ReconciliationRun", back_populates="organization", cascade="all, delete-orphan"
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="organization", cascade="all, delete-orphan"
    )
    matches: Mapped[List["Match"]] = relationship(
        "Match", back_populates="organization", cascade="all, delete-orphan"
    )
    exceptions: Mapped[List["ReconciliationException"]] = relationship(
        "Exception", back_populates="organization", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_organizations_slug_trgm", "slug"),
    )

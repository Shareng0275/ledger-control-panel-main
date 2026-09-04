import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UploadStatus, UploadType

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.transaction import Transaction
    from app.models.user import User


class Upload(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tracks raw file uploads (Bank Statements or Internal/Gateway Ledgers).
    Contains validation metadata, row counts, and error payloads stored as JSONB.
    """
    __tablename__ = "uploads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_type: Mapped[UploadType] = mapped_column(
        Enum(UploadType, name="upload_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UploadStatus.PENDING,
    )
    validation_errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="uploads")
    uploader: Mapped[Optional["User"]] = relationship("User")
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="upload", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_uploads_org_status", "organization_id", "status"),
        Index("ix_uploads_org_type", "organization_id", "upload_type"),
    )

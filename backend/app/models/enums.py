from enum import StrEnum


class MembershipRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UploadType(StrEnum):
    STATEMENT = "statement"
    LEDGER = "ledger"


class UploadStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    PROCESSING = "processing"
    FAILED = "failed"


class ReconciliationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class TransactionSource(StrEnum):
    STATEMENT = "statement"
    LEDGER = "ledger"


class TransactionStatus(StrEnum):
    MATCHED = "matched"
    EXCEPTION = "exception"
    PENDING_REVIEW = "pending_review"


class MatchMethod(StrEnum):
    DETERMINISTIC = "deterministic"
    FUZZY = "fuzzy"
    MANUAL = "manual"


class ExceptionPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionStatus(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    REJECTED = "rejected"

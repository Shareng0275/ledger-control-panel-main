import csv
import io
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.core.storage import storage_service
from app.models import AuditLog, Transaction, TransactionSource, TransactionStatus, Upload, UploadStatus, UploadType, User
from app.schemas.upload import UploadResponse
from app.services.audit_service import AuditService
from app.services.normalizer import Normalizer

# Header candidate aliases for automated column discovery
DATE_HEADERS = {"date", "transaction_date", "trans_date", "posting_date", "value_date", "tx_date", "booking_date", "timestamp"}
DESC_HEADERS = {"description", "narrative", "details", "memo", "name", "payee", "payer", "transaction_details", "particulars", "notes", "account_memo"}
AMOUNT_HEADERS = {"amount", "net_amount", "value", "total", "sum", "transaction_amount"}
DEBIT_HEADERS = {"debit", "withdrawal", "outflow", "paid_out", "dr", "debit_amount"}
CREDIT_HEADERS = {"credit", "deposit", "inflow", "paid_in", "cr", "credit_amount"}
REF_HEADERS = {"reference", "ref", "external_reference", "external_ref", "tx_id", "transaction_id", "invoice_id", "check_number", "cheque_number", "id", "journal_id"}
CURRENCY_HEADERS = {"currency", "ccy", "curr"}


def re_clean(header: str) -> str:
    """Normalize header string for fuzzy matching."""
    return header.strip().lower().replace(" ", "_").replace("-", "_")


class IngestionService:
    """Service handling financial CSV decoding, validation, normalization, deduplication, and persistence."""

    @staticmethod
    def _decode_csv_content(raw_bytes: bytes) -> str:
        """Decode raw file bytes trying UTF-8-BOM, UTF-8, Latin-1, and CP1252."""
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        for enc in encodings:
            try:
                return raw_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode file content. Please provide a valid UTF-8 or Latin-1 encoded CSV file.",
        )

    @staticmethod
    def _detect_columns(headers: List[str]) -> Dict[str, str]:
        """Detect and map CSV columns based on header candidate names."""
        clean_map = {re_clean(h): h for h in headers if h}
        mapping: Dict[str, str] = {}

        assigned_cols: set[str] = set()

        def find_match(candidates: set[str]) -> Optional[str]:
            # 1. Exact match on cleaned header
            for cand in candidates:
                if cand in clean_map and clean_map[cand] not in assigned_cols:
                    assigned_cols.add(clean_map[cand])
                    return clean_map[cand]
            # 2. Word-level token match (e.g. "transaction_date", "total_amount")
            for cand in candidates:
                for clean_h, original_h in clean_map.items():
                    if original_h in assigned_cols:
                        continue
                    tokens = clean_h.split("_")
                    if cand in tokens or clean_h.startswith(cand + "_") or clean_h.endswith("_" + cand):
                        assigned_cols.add(original_h)
                        return original_h
            return None

        date_col = find_match(DATE_HEADERS)
        desc_col = find_match(DESC_HEADERS)
        amount_col = find_match(AMOUNT_HEADERS)
        debit_col = find_match(DEBIT_HEADERS) if not amount_col else None
        credit_col = find_match(CREDIT_HEADERS) if not amount_col else None
        ref_col = find_match(REF_HEADERS)
        currency_col = find_match(CURRENCY_HEADERS)

        if date_col:
            mapping["date"] = date_col
        if desc_col:
            mapping["description"] = desc_col
        if amount_col:
            mapping["amount"] = amount_col
        if debit_col:
            mapping["debit"] = debit_col
        if credit_col:
            mapping["credit"] = credit_col
        if ref_col:
            mapping["reference"] = ref_col
        if currency_col:
            mapping["currency"] = currency_col

        return mapping

    @staticmethod
    async def process_upload(
        db: AsyncSession,
        file: UploadFile,
        organization_id: uuid.UUID,
        upload_type: UploadType,
        user: User,
        ip_address: Optional[str] = None,
    ) -> UploadResponse:
        """Execute the end-to-end ingestion pipeline."""
        # 1. Read file bytes and enforce size limits
        content = await file.read()
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # 2. Decode text content
        text_content = IngestionService._decode_csv_content(content)

        # 3. Detect Delimiter and Parse CSV rows
        lines = [line for line in text_content.splitlines() if line.strip()]
        if not lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file contains no data.",
            )

        first_line = lines[0]
        delimiter = ","
        if ";" in first_line and first_line.count(";") > first_line.count(","):
            delimiter = ";"
        elif "\t" in first_line and first_line.count("\t") > first_line.count(","):
            delimiter = "\t"
        elif "|" in first_line and first_line.count("|") > first_line.count(","):
            delimiter = "|"

        reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
        raw_fieldnames = reader.fieldnames or []
        fieldnames = [h.strip() for h in raw_fieldnames if h and h.strip()]

        if not fieldnames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV header line missing or empty.",
            )

        # 4. Map columns
        col_map = IngestionService._detect_columns(fieldnames)

        # Check required columns
        missing_required = []
        if "date" not in col_map:
            missing_required.append("Date (e.g. 'Date', 'Transaction Date')")
        if "description" not in col_map:
            missing_required.append("Description (e.g. 'Description', 'Details', 'Memo')")
        if "amount" not in col_map and ("debit" not in col_map and "credit" not in col_map):
            missing_required.append("Amount (or separate Debit/Credit columns)")

        upload_id = uuid.uuid4()
        source = TransactionSource.STATEMENT if upload_type == UploadType.STATEMENT else TransactionSource.LEDGER

        if missing_required:
            validation_errors = {
                "header_errors": [f"Missing required columns: {', '.join(missing_required)}"],
                "detected_columns": col_map,
                "available_headers": fieldnames,
            }
            # Record failed upload
            failed_upload = Upload(
                id=upload_id,
                organization_id=organization_id,
                uploaded_by=user.id,
                filename=file.filename or f"{upload_type.value}.csv",
                upload_type=upload_type,
                storage_path=f"{organization_id}/{upload_id}_{file.filename or 'upload.csv'}",
                row_count=0,
                status=UploadStatus.INVALID,
                validation_errors=validation_errors,
            )
            db.add(failed_upload)
            await db.flush()

            # Record failed validation audit log
            await AuditService.log_upload_validation_failed(
                db=db,
                organization_id=organization_id,
                user_id=user.id,
                upload_id=upload_id,
                filename=file.filename or f"{upload_type.value}.csv",
                upload_type=upload_type.value,
                validation_errors=validation_errors,
                ip_address=ip_address,
            )
            return UploadResponse.model_validate(failed_upload)

        # 5. Fetch existing hashes for duplicate detection in this organization
        existing_hashes_stmt = select(Transaction.normalized_hash).where(
            Transaction.organization_id == organization_id,
            Transaction.source == source,
        )
        hash_res = await db.execute(existing_hashes_stmt)
        existing_hashes = set(hash_res.scalars().all())

        # 6. Parse and normalize each row
        transactions_to_insert: List[Transaction] = []
        row_errors: List[Dict[str, Any]] = []
        seen_batch_hashes: set[str] = set()

        row_num = 1  # 1-indexed (row 1 is header)
        for row in reader:
            row_num += 1
            raw_data = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
            try:
                # Extract and normalize Date
                raw_date = raw_data.get(col_map["date"])
                norm_date = Normalizer.normalize_date(raw_date)

                # Extract and normalize Description
                raw_desc = raw_data.get(col_map["description"], "").strip()
                if not raw_desc:
                    raise ValueError("Description field cannot be empty.")
                norm_desc = Normalizer.normalize_description(raw_desc)

                # Extract and normalize Amount
                raw_amount = raw_data.get(col_map.get("amount")) if "amount" in col_map else None
                raw_debit = raw_data.get(col_map.get("debit")) if "debit" in col_map else None
                raw_credit = raw_data.get(col_map.get("credit")) if "credit" in col_map else None
                norm_amount = Normalizer.normalize_amount(
                    amount_raw=raw_amount,
                    debit_raw=raw_debit,
                    credit_raw=raw_credit,
                )

                # Extract and normalize Reference & Currency
                raw_ref = raw_data.get(col_map.get("reference")) if "reference" in col_map else None
                norm_ref = Normalizer.normalize_reference(raw_ref)

                raw_curr = raw_data.get(col_map.get("currency")) if "currency" in col_map else None
                norm_curr = Normalizer.normalize_currency(raw_curr)

                # Compute deterministic hash
                tx_hash = Normalizer.compute_transaction_hash(
                    source=source.value,
                    organization_id=organization_id,
                    transaction_date=norm_date,
                    amount=norm_amount,
                    currency=norm_curr,
                    normalized_description=norm_desc,
                    normalized_reference=norm_ref,
                )

                # Flag duplicate safely without silent deletion
                is_duplicate = (tx_hash in existing_hashes) or (tx_hash in seen_batch_hashes)
                seen_batch_hashes.add(tx_hash)

                raw_payload = {
                    **raw_data,
                    "_row_number": row_num,
                    "_is_duplicate": is_duplicate,
                }

                tx = Transaction(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    upload_id=upload_id,
                    source=source,
                    transaction_date=norm_date,
                    description=raw_desc,
                    normalized_description=norm_desc,
                    amount=norm_amount,
                    currency=norm_curr,
                    external_reference=raw_ref.strip() if raw_ref else None,
                    normalized_reference=norm_ref,
                    normalized_hash=tx_hash,
                    status=TransactionStatus.PENDING_REVIEW,
                    raw_data=raw_payload,
                )
                transactions_to_insert.append(tx)

            except Exception as row_exc:
                row_errors.append({
                    "row": row_num,
                    "error": str(row_exc),
                    "raw_data": raw_data,
                })

        # 7. Save file to storage
        relative_storage_path = f"{organization_id}/{upload_id}_{file.filename or 'upload.csv'}"
        await storage_service.save_file(content, relative_storage_path)

        # 8. Determine final upload status
        final_status = UploadStatus.VALID
        if not transactions_to_insert and row_errors:
            final_status = UploadStatus.INVALID
        elif row_errors:
            final_status = UploadStatus.VALID  # Valid with partial row warnings

        validation_payload = {
            "total_rows_processed": row_num - 1,
            "valid_rows_count": len(transactions_to_insert),
            "invalid_rows_count": len(row_errors),
            "errors": row_errors[:50],  # Limit to first 50 row errors in summary
            "column_mapping": col_map,
        } if row_errors else None

        # 9. Persist Upload and Transactions
        upload_record = Upload(
            id=upload_id,
            organization_id=organization_id,
            uploaded_by=user.id,
            filename=file.filename or f"{upload_type.value}.csv",
            upload_type=upload_type,
            storage_path=relative_storage_path,
            row_count=len(transactions_to_insert),
            status=final_status,
            validation_errors=validation_payload,
        )
        db.add(upload_record)

        if transactions_to_insert:
            db.add_all(transactions_to_insert)

        # Audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_id=user.id,
            action=f"upload.{upload_type.value}_uploaded",
            entity_type="Upload",
            entity_id=upload_id,
            details={
                "filename": file.filename,
                "upload_type": upload_type.value,
                "valid_rows": len(transactions_to_insert),
                "errors_count": len(row_errors),
            },
            ip_address=ip_address,
        )
        db.add(audit)

        await db.flush()

        logger.info(
            f"Processed {upload_type.value} upload {upload_id}: "
            f"{len(transactions_to_insert)} transactions saved, {len(row_errors)} errors."
        )

        return UploadResponse.model_validate(upload_record)

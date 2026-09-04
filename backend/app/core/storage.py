import os
from pathlib import Path
from typing import Protocol
from app.core.config import settings
from app.core.logging import logger


class StorageService(Protocol):
    """Storage service abstraction interface for local filesystem, S3, or Blob storage."""

    async def save_file(self, content: bytes, relative_path: str) -> str:
        """Save file content and return the relative storage path."""
        ...

    async def read_file(self, relative_path: str) -> bytes:
        """Read and return file content from the storage path."""
        ...

    async def delete_file(self, relative_path: str) -> None:
        """Delete file at the storage path."""
        ...


class LocalStorageService:
    """Local disk storage implementation for file persistence."""

    def __init__(self, base_dir: str = settings.STORAGE_DIR):
        p = Path(base_dir)
        if not p.is_absolute():
            backend_dir = Path(__file__).resolve().parent.parent.parent
            self.base_dir = (backend_dir / p).resolve()
        else:
            self.base_dir = p.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, content: bytes, relative_path: str) -> str:
        target_path = (self.base_dir / relative_path).resolve()

        # Prevent directory traversal attacks
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError("Invalid storage path: directory traversal detected.")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved file ({len(content)} bytes) to local storage: {relative_path}")
        return relative_path

    async def read_file(self, relative_path: str) -> bytes:
        target_path = (self.base_dir / relative_path).resolve()
        if not str(target_path).startswith(str(self.base_dir)) or not target_path.exists():
            raise FileNotFoundError(f"Stored file not found: {relative_path}")

        with open(target_path, "rb") as f:
            return f.read()

    async def delete_file(self, relative_path: str) -> None:
        target_path = (self.base_dir / relative_path).resolve()
        if str(target_path).startswith(str(self.base_dir)) and target_path.exists():
            target_path.unlink()
            logger.info(f"Deleted file from local storage: {relative_path}")


# Global storage service instance
storage_service: StorageService = LocalStorageService()

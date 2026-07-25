import uuid
from pathlib import Path

from fastapi import UploadFile

from settings import get_settings


class FileTooLargeError(Exception):
    """Raised when an upload exceeds the configured maximum size."""


class StorageService:
    """Filesystem mechanics only: naming, directories, writing bytes.

    Deliberately has no knowledge of KnowledgeDocument, MIME allowlists, or
    HTTP - those are ingestion business rules that belong in the calling
    service, so this class can be reused by future ingestion sources
    (URL, YouTube, etc.) without dragging knowledge-domain logic with it.
    """

    def __init__(self, base_path: str | None = None, max_size_bytes: int | None = None):
        settings = get_settings()
        self.base_path = Path(base_path if base_path is not None else settings.upload_storage_path)
        self.max_size_bytes = (
            max_size_bytes if max_size_bytes is not None else settings.max_upload_size_bytes
        )

    def _generate_filename(self, original_filename: str | None) -> str:
        extension = Path(original_filename).suffix if original_filename else ""
        return f"{uuid.uuid4().hex}{extension}"

    def save_upload(self, upload_file: UploadFile, organization_id: int) -> tuple[str, int]:
        """Save an uploaded file under a per-organization directory.

        Returns (storage_path, file_size_bytes). Raises FileTooLargeError,
        without leaving a partial file behind, if the upload exceeds the
        configured maximum size.
        """
        directory = self.base_path / str(organization_id)
        directory.mkdir(parents=True, exist_ok=True)

        destination = directory / self._generate_filename(upload_file.filename)

        size = 0
        chunk_size = 1024 * 1024
        try:
            with destination.open("wb") as buffer:
                while True:
                    chunk = upload_file.file.read(chunk_size)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_size_bytes:
                        raise FileTooLargeError(
                            f"Upload exceeds maximum size of {self.max_size_bytes} bytes"
                        )
                    buffer.write(chunk)
        except FileTooLargeError:
            destination.unlink(missing_ok=True)
            raise

        return str(destination), size

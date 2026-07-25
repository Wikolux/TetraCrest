# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog principles.

---

## Unreleased

### Added
- Modular Knowledge Ingestion Framework.
- `BaseIngestor` abstraction for pluggable ingestion sources.
- `UploadIngestor` implementation.
- Placeholder ingestors for:
  - URL
  - YouTube
  - Image
  - Audio
  - Video

### Changed
- Refactored `KnowledgeService` to delegate ingestion responsibilities to dedicated ingestors.
- Improved separation of concerns between storage, ingestion, and business logic.

### Testing
- All automated tests passing (60/60).

---

# v0.2.0

**Release Date:** 2026-07-25

## Added

- Pagination across all API list endpoints.
- CRUD Update endpoints.
- CRUD Delete endpoints.
- Update schemas for all core resources.
- Shared authorization dependencies.
- Tenant-aware authorization.
- Cross-tenant protection.
- Knowledge Upload API.
- File storage service.
- Upload metadata model.
- Upload validation.
- Configurable upload directory.
- Configurable upload size limit.

## Changed

- Repository pagination standardized.
- Services updated for pagination support.
- Routes now support PATCH and DELETE.
- Knowledge upload pipeline integrated into the Knowledge Engine.

## Security

- Authentication required for all mutation endpoints.
- Cross-tenant update protection.
- Cross-tenant delete protection.
- Upload MIME validation.
- Upload size enforcement.

## Testing

- Pagination tests.
- CRUD lifecycle tests.
- Tenant isolation tests.
- Upload ingestion tests.

**Total:** 60 automated tests passing.

---

# v0.1.0

## Added

- Initial FastAPI backend.
- Authentication.
- Repository pattern.
- Service layer.
- CRUD foundation.
- Database models.
- Project architecture.
- AI blueprint documentation.

### Added

- URL ingestion support
- URL endpoint
- HTML text extraction

### Added

- URL ingestion
- YouTube ingestion
- Transcript retrieval
- YouTube metadata extraction

### Testing

- 77 passing automated tests

### Added

- Image ingestion
- Image upload endpoint
- Image metadata persistence

### Testing

- 83 passing automated tests

### Added

- Audio ingestion
- Audio upload endpoint
- Audio metadata persistence

### Testing

89 passing automated tests
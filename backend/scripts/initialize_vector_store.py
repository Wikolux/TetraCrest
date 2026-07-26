#!/usr/bin/env python
"""Deployment entry point for preparing the pgvector-backed vector store schema.

Run this once, out-of-band from the application, before anything uses
vector_store_provider=pgvector - e.g. as a deploy-pipeline step, a
Kubernetes Job/init container, or manually against a fresh database:

    python scripts/initialize_vector_store.py

This is deliberately NOT invoked by the FastAPI app (no startup event calls
it) and NOT invoked by the test suite (pytest never imports this module -
it isn't named test_*.py and nothing under app/ imports it). Schema
provisioning is a deployment concern, kept separate from both request
handling and testing:

- Running DDL on every app boot/restart/autoscale event would be wasted
  work at best and a startup race between concurrently-booting instances
  at worst.
- The app needs to boot identically whether the configured backend is
  NullVectorStore (no schema needed) or PgVectorStore (real Postgres) -
  and it needs to boot against the test suite's in-memory SQLite without
  ever attempting Postgres-only DDL (CREATE EXTENSION, a `vector` column
  type) that SQLite can't execute.
- A failed schema-prep step should fail a deploy pipeline, not surface as
  a crashed or half-initialized running application.
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.db.vector_initializer import VectorSchemaInitializer  # noqa: E402
from app.logging_utils import get_logger  # noqa: E402
from app.services.vector_store.base_store import VectorStoreError  # noqa: E402

logger = get_logger("vector_store_initializer")


def main() -> int:
    try:
        VectorSchemaInitializer().initialize()
    except VectorStoreError:
        logger.error("vector_store_schema_initialization_failed", exc_info=True)
        return 1
    logger.info("vector_store_schema_initialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

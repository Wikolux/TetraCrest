"""SQL statement builders for the pgvector-backed vector store schema.

Pure string construction, no I/O - kept separate from VectorSchemaInitializer
(which executes these against a real connection) so the schema definition
itself can be read and unit-tested without a database.
"""


def create_extension_statement() -> str:
    return "CREATE EXTENSION IF NOT EXISTS vector"


def create_table_statement(table_name: str, dimensions: int) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {table_name} ("
        "vector_id VARCHAR(255) PRIMARY KEY, "
        "organization_id INTEGER, "
        "resource_type VARCHAR(64), "
        "resource_id INTEGER, "
        f"embedding vector({dimensions}) NOT NULL, "
        "metadata JSONB, "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )


def create_index_statements(table_name: str) -> list[str]:
    return [
        f"CREATE INDEX IF NOT EXISTS {table_name}_organization_id_idx "
        f"ON {table_name} (organization_id)",
        f"CREATE INDEX IF NOT EXISTS {table_name}_resource_type_idx "
        f"ON {table_name} (resource_type)",
        f"CREATE INDEX IF NOT EXISTS {table_name}_org_resource_idx "
        f"ON {table_name} (organization_id, resource_type)",
    ]


def all_statements(table_name: str, dimensions: int) -> list[str]:
    """Every statement required to prepare the vector store schema, in order."""
    return [
        create_extension_statement(),
        create_table_statement(table_name, dimensions),
        *create_index_statements(table_name),
    ]

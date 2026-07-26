import importlib
import importlib.util
import sys
from pathlib import Path

from app.db.vector_initializer import VectorSchemaInitializer
from app.services.vector_store.base_store import VectorStoreError

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "initialize_vector_store.py"


def _load_script_module():
    """Import scripts/initialize_vector_store.py by path.

    It isn't a package member (deliberately - it's a standalone deployment
    entry point, not application code), so it's loaded the same way any
    external tool would run it: as a script file.
    """
    spec = importlib.util.spec_from_file_location("initialize_vector_store_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_calls_vector_schema_initializer(monkeypatch):
    calls: list[None] = []

    def _fake_initialize(self, table_name=None, dimensions=None):
        calls.append(None)

    monkeypatch.setattr(VectorSchemaInitializer, "initialize", _fake_initialize)

    module = _load_script_module()
    exit_code = module.main()

    assert len(calls) == 1
    assert exit_code == 0


def test_script_is_idempotent(monkeypatch):
    calls: list[None] = []

    def _fake_initialize(self, table_name=None, dimensions=None):
        calls.append(None)

    monkeypatch.setattr(VectorSchemaInitializer, "initialize", _fake_initialize)

    module = _load_script_module()
    module.main()
    module.main()

    assert len(calls) == 2  # safe to run repeatedly, each run just re-applies IF NOT EXISTS


def test_script_returns_nonzero_and_logs_on_failure(monkeypatch):
    def _fake_initialize(self, table_name=None, dimensions=None):
        raise VectorStoreError("no permission")

    monkeypatch.setattr(VectorSchemaInitializer, "initialize", _fake_initialize)

    module = _load_script_module()
    exit_code = module.main()

    assert exit_code == 1


def test_main_module_import_never_invokes_vector_schema_initializer(monkeypatch):
    """The FastAPI app must never trigger schema provisioning on its own -
    importing/reloading main.py must not call VectorSchemaInitializer."""
    import main as main_module

    def _boom(self, table_name=None, dimensions=None):
        raise AssertionError("VectorSchemaInitializer.initialize must not run automatically")

    monkeypatch.setattr(VectorSchemaInitializer, "initialize", _boom)

    importlib.reload(main_module)


def test_script_is_not_collected_by_pytest_as_a_test_module():
    # pytest's default discovery only collects test_*.py / *_test.py; this
    # script's name and location guarantee it's never picked up as a test.
    assert not SCRIPT_PATH.name.startswith("test_")
    assert "app/tests" not in str(SCRIPT_PATH)
    assert SCRIPT_PATH.name not in sys.modules

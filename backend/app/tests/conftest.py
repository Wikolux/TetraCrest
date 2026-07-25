import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  ensures all models are registered on Base
import database
from app.models.user import User
from main import app
from security import create_access_token
from settings import get_settings


@pytest.fixture(autouse=True)
def _isolated_upload_storage(tmp_path, monkeypatch):
    """Redirect file uploads to a pytest tmp dir so tests never write into the
    real project's uploads/ directory."""
    monkeypatch.setenv("UPLOAD_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        database.Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    TestSessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine):
    TestSessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def org_id(client):
    response = client.post("/api/v1/organizations", json={"name": "Acme", "slug": "acme"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture()
def project_id(client, org_id):
    response = client.post(
        "/api/v1/projects", json={"name": "Rocket", "organization_id": org_id}
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture()
def make_user(db_session):
    """Create a user bound to a given organization and return a bearer access token for it.

    Bypasses the registration endpoint (which currently hardcodes organization_id=1,
    a separate known gap) so tenant-scoping tests can exercise users in arbitrary
    organizations independently of that issue.
    """

    def _make_user(username: str, organization_id: int) -> str:
        user = User(
            organization_id=organization_id,
            username=username,
            email=f"{username}@example.com",
            full_name=username,
            hashed_password="unused-in-tests",
            roles="viewer",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.commit()
        return create_access_token(username)

    return _make_user


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

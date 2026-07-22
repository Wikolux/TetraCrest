from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_create_organization_route(monkeypatch):
    class FakeOrganizationService:
        def __init__(self, db):
            self.db = db

        def create(self, name, slug, description=None):
            return {"id": 1, "name": name, "slug": slug, "description": description, "active": True}

    monkeypatch.setattr("app.api.v1.routes.organizations.OrganizationService", FakeOrganizationService)

    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "description": "Test org"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Acme"

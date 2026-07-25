import pytest

RESOURCES = ["organizations", "projects", "tasks", "knowledge", "memory"]

# The org_id/project_id fixtures create one organization ("Acme") and one
# project ("Rocket") up front so tasks/knowledge/memory have a valid parent
# to attach to. Those two rows themselves show up when listing the
# "organizations" and "projects" resources respectively.
BASELINE = {"organizations": 1, "projects": 1, "tasks": 0, "knowledge": 0, "memory": 0}


def _seed(client, resource, org_id, project_id, count):
    for i in range(count):
        if resource == "organizations":
            path = "/api/v1/organizations"
            payload = {"name": f"Org {i}", "slug": f"org-{i}"}
        elif resource == "projects":
            path = "/api/v1/projects"
            payload = {"name": f"Project {i}", "organization_id": org_id}
        elif resource == "tasks":
            path = "/api/v1/tasks"
            payload = {"title": f"Task {i}", "organization_id": org_id, "project_id": project_id}
        elif resource == "knowledge":
            path = "/api/v1/knowledge"
            payload = {"title": f"Doc {i}", "content": "content", "organization_id": org_id}
        elif resource == "memory":
            path = "/api/v1/memory"
            payload = {"key": f"key-{i}", "value": "value", "organization_id": org_id}
        else:
            raise ValueError(f"unknown resource {resource}")
        response = client.post(path, json=payload)
        assert response.status_code == 201


def _list_path(resource, org_id, project_id):
    if resource == "organizations":
        return "/api/v1/organizations"
    if resource == "tasks":
        return f"/api/v1/tasks/project/{project_id}"
    return f"/api/v1/{resource}/organization/{org_id}"


SEED_COUNT = 5


@pytest.mark.parametrize("resource", RESOURCES)
def test_default_pagination(client, org_id, project_id, resource):
    _seed(client, resource, org_id, project_id, count=SEED_COUNT)

    response = client.get(_list_path(resource, org_id, project_id))

    assert response.status_code == 200
    assert len(response.json()) == BASELINE[resource] + SEED_COUNT


@pytest.mark.parametrize("resource", RESOURCES)
def test_custom_skip(client, org_id, project_id, resource):
    _seed(client, resource, org_id, project_id, count=SEED_COUNT)
    reference = client.get(
        _list_path(resource, org_id, project_id), params={"skip": 0, "limit": 100}
    ).json()

    response = client.get(_list_path(resource, org_id, project_id), params={"skip": 2})

    assert response.status_code == 200
    assert response.json() == reference[2:]


@pytest.mark.parametrize("resource", RESOURCES)
def test_custom_limit(client, org_id, project_id, resource):
    _seed(client, resource, org_id, project_id, count=SEED_COUNT)
    reference = client.get(
        _list_path(resource, org_id, project_id), params={"skip": 0, "limit": 100}
    ).json()

    response = client.get(_list_path(resource, org_id, project_id), params={"limit": 2})

    assert response.status_code == 200
    assert response.json() == reference[:2]


@pytest.mark.parametrize("resource", RESOURCES)
def test_skip_zero_is_valid(client, org_id, project_id, resource):
    _seed(client, resource, org_id, project_id, count=SEED_COUNT)
    reference = client.get(
        _list_path(resource, org_id, project_id), params={"skip": 0, "limit": 100}
    ).json()

    response = client.get(_list_path(resource, org_id, project_id), params={"skip": 0})

    assert response.status_code == 200
    assert response.json() == reference


@pytest.mark.parametrize("resource", RESOURCES)
def test_limit_100_is_valid(client, org_id, project_id, resource):
    _seed(client, resource, org_id, project_id, count=SEED_COUNT)

    response = client.get(_list_path(resource, org_id, project_id), params={"limit": 100})

    assert response.status_code == 200
    assert len(response.json()) == BASELINE[resource] + SEED_COUNT


@pytest.mark.parametrize("resource", RESOURCES)
def test_negative_skip_is_rejected(client, org_id, project_id, resource):
    response = client.get(_list_path(resource, org_id, project_id), params={"skip": -1})

    assert response.status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_limit_zero_is_rejected(client, org_id, project_id, resource):
    response = client.get(_list_path(resource, org_id, project_id), params={"limit": 0})

    assert response.status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_limit_101_is_rejected(client, org_id, project_id, resource):
    response = client.get(_list_path(resource, org_id, project_id), params={"limit": 101})

    assert response.status_code == 422

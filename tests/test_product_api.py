import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import product_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_store(monkeypatch):
    store: dict[int, dict] = {}
    seq = {"id": 0}

    def create(data):
        seq["id"] += 1
        row = {"product_id": seq["id"], "status": "active", **data}
        store[seq["id"]] = row
        return {**row, "indexed_points": 2}

    def get(pid):
        return store.get(pid)

    def update(pid, changes):
        if pid not in store:
            return None
        store[pid].update(changes)
        return {**store[pid], "indexed_points": 2}

    def soft_delete(pid):
        if pid not in store:
            return False
        store[pid]["status"] = "inactive"
        return True

    monkeypatch.setattr(product_service, "create_product", create)
    monkeypatch.setattr(product_service, "get_product", get)
    monkeypatch.setattr(product_service, "update_product", update)
    monkeypatch.setattr(product_service, "soft_delete_product", soft_delete)
    return store


def test_product_crud_flow(client, fake_store):
    created = client.post(
        "/api/products",
        json={
            "name": "Balo",
            "description": "vải dù",
            "category": "thoi_trang",
            "price": 450000,
        },
    )
    assert created.status_code == 201
    pid = created.json()["product_id"]
    assert created.json()["indexed_points"] == 2

    got = client.get(f"/api/products/{pid}")
    assert got.status_code == 200

    updated = client.put(f"/api/products/{pid}", json={"price": 400000})
    assert updated.json()["price"] == 400000

    assert client.delete(f"/api/products/{pid}").status_code == 204
    assert fake_store[pid]["status"] == "inactive"


def test_missing_product_returns_404(client, fake_store):
    assert client.get("/api/products/999").status_code == 404
    assert client.put("/api/products/999", json={"price": 1}).status_code == 404
    assert client.delete("/api/products/999").status_code == 404


def test_create_rejects_negative_price(client, fake_store):
    resp = client.post("/api/products", json={"name": "X", "price": -5})
    assert resp.status_code == 422


def test_create_rejects_category_outside_taxonomy(client, fake_store):
    # A free-text category (e.g. "Smartphone") would never match the fixed
    # dien_tu/thoi_trang values analyze_query() infers, so chat could never
    # find the product again — reject it at creation time instead.
    resp = client.post(
        "/api/products",
        json={"name": "iPhone 15", "category": "Smartphone", "price": 1},
    )
    assert resp.status_code == 422

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import database, models, whatsapp_service
from backend.main import app


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    sent_messages = []
    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_msg",
        lambda to_number, message_body: sent_messages.append((to_number, message_body)),
    )
    app.dependency_overrides[database.get_db] = override_get_db

    with TestClient(app) as test_client:
        test_client.sent_messages = sent_messages
        yield test_client

    app.dependency_overrides.clear()


def add_menu_item(client, name="Pizza", is_available=True):
    return client.post(
        "/menu/",
        json={
            "name": name,
            "description": f"{name} description",
            "price": 199.0,
            "is_available": is_available,
        },
    )


def place_order(client, items=None):
    return client.post(
        "/orders/",
        json={
            "customer_name": "John Doe",
            "whatsapp_number": "+917904854535",
            "items": items or ["Pizza"],
        },
    )


def test_menu_management(client):
    created = add_menu_item(client)
    assert created.status_code == 200
    item = created.json()
    assert item["id"] == 1
    assert item["is_available"] is True

    listed = client.get("/menu/")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Pizza"

    fetched = client.get("/menu/1")
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Pizza description"


def test_menu_rejects_duplicates_and_toggles_availability(client):
    assert add_menu_item(client, name="Pizza").status_code == 200

    duplicate = add_menu_item(client, name="pizza")
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Menu item already exists"

    toggled = client.patch("/menu/1/availability", json={"is_available": False})
    assert toggled.status_code == 200
    assert toggled.json()["is_available"] is False

    unavailable_order = place_order(client, ["Pizza"])
    assert unavailable_order.status_code == 400
    assert "Unavailable menu items" in unavailable_order.json()["detail"]


def test_order_creation_sends_whatsapp_notification(client):
    add_menu_item(client)

    response = place_order(client)

    assert response.status_code == 200
    order = response.json()
    assert order["status"] == "pending"
    assert order["items"] == ["Pizza"]
    assert client.sent_messages
    assert client.sent_messages[0][0] == "+917904854535"
    assert "Your order for Pizza has been received" in client.sent_messages[0][1]


def test_order_rejects_unknown_or_unavailable_items(client):
    add_menu_item(client, name="Pizza", is_available=False)

    unavailable = place_order(client, ["Pizza"])
    assert unavailable.status_code == 400
    assert "Unavailable menu items" in unavailable.json()["detail"]

    unknown = place_order(client, ["Burger"])
    assert unknown.status_code == 400
    assert "Unknown menu items" in unknown.json()["detail"]


def test_status_updates_must_follow_required_order(client):
    add_menu_item(client)
    order_id = place_order(client).json()["id"]

    skipped = client.patch(f"/orders/{order_id}", json={"status": "delivered"})
    assert skipped.status_code == 400
    assert "pending to preparing" in skipped.json()["detail"]

    preparing = client.patch(f"/orders/{order_id}", json={"status": "preparing"})
    assert preparing.status_code == 200

    repeated = client.patch(f"/orders/{order_id}", json={"status": "preparing"})
    assert repeated.status_code == 400

    out_for_delivery = client.patch(f"/orders/{order_id}", json={"status": "out-for-delivery"})
    assert out_for_delivery.status_code == 200

    delivered = client.patch(f"/orders/{order_id}", json={"status": "delivered"})
    assert delivered.status_code == 200

    after_delivered = client.patch(f"/orders/{order_id}", json={"status": "preparing"})
    assert after_delivered.status_code == 400
    assert "Delivered orders cannot be updated" in after_delivered.json()["detail"]


def test_cancel_order_marks_cancelled_and_sends_notification(client):
    add_menu_item(client)
    order_id = place_order(client).json()["id"]

    cancelled = client.delete(f"/orders/{order_id}")
    assert cancelled.status_code == 200
    assert cancelled.json()["message"] == "Order cancelled"
    assert client.sent_messages[-1] == ("+917904854535", "Your order has been cancelled.")

    fetched = client.get(f"/orders/{order_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "cancelled"

    active_orders = client.get("/orders/")
    assert active_orders.status_code == 200
    assert active_orders.json() == []


def test_invalid_requests(client):
    missing_order = client.get("/orders/999")
    assert missing_order.status_code == 404

    invalid_status = client.patch("/orders/999", json={"status": "done"})
    assert invalid_status.status_code == 422

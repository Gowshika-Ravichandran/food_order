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


def add_menu_item(client, name="Pizza", is_available=True, restaurant_name="Default"):
    return client.post(
        "/menu/",
        json={
            "name": name,
            "description": f"{name} description",
            "price": 199.0,
            "is_available": is_available,
            "restaurant_name": restaurant_name,
        },
    )


def place_order(client, items=None, whatsapp_number="+917904854535", restaurant_name="Default", coupon_code=None):
    payload = {
        "customer_name": "John Doe",
        "whatsapp_number": whatsapp_number,
        "items": items or ["Pizza"],
        "restaurant_name": restaurant_name,
    }
    if coupon_code is not None:
        payload["coupon_code"] = coupon_code
    return client.post(
        "/orders/",
        json=payload,
    )


def create_coupon(client, code="SAVE10", restaurant_name="Default"):
    return client.post(
        "/coupons/",
        json={
            "code": code,
            "discount_type": "percentage",
            "discount_value": 10,
            "restaurant_name": restaurant_name,
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
    assert "Estimated delivery" not in client.sent_messages[-1][1]
    assert client.get(f"/orders/{order_id}").json()["estimated_delivery_time"] is None

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

    all_orders = client.get("/orders/?include_all=true")
    assert all_orders.status_code == 200
    assert all_orders.json()[0]["status"] == "cancelled"


def test_invalid_requests(client):
    missing_order = client.get("/orders/999")
    assert missing_order.status_code == 404

    invalid_status = client.patch("/orders/999", json={"status": "done"})
    assert invalid_status.status_code == 422


def test_update_menu_item(client):
    add_menu_item(client, name="Pizza")

    updated = client.patch(
        "/menu/1",
        json={
            "name": "Veggie Pizza",
            "description": "Crispy crust with fresh vegetables",
            "price": 249.0,
            "is_available": False,
        },
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Veggie Pizza"
    assert updated.json()["description"] == "Crispy crust with fresh vegetables"
    assert updated.json()["price"] == 249.0
    assert updated.json()["is_available"] is False


def test_update_menu_item_rejects_duplicate_name(client):
    add_menu_item(client, name="Pizza")
    add_menu_item(client, name="Burger")

    duplicate = client.patch(
        "/menu/2",
        json={
            "name": "Pizza",
            "description": "Burger description",
            "price": 180.0,
            "is_available": True,
        },
    )

    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Menu item already exists"


def test_order_estimate_is_given_after_confirmation_only(client):
    add_menu_item(client)

    invalid = place_order(client, whatsapp_number="abc")
    assert invalid.status_code == 400
    assert "valid phone number" in invalid.json()["detail"]

    ordered = place_order(client)
    assert ordered.status_code == 200
    assert ordered.json()["estimated_delivery_time"] is None
    assert "Estimated delivery" not in client.sent_messages[0][1]
    assert "Pending confirmation" in client.sent_messages[0][1]

    confirmed = client.patch(f"/orders/{ordered.json()['id']}", json={"status": "preparing"})
    assert confirmed.status_code == 200
    assert "Estimated delivery" in client.sent_messages[-1][1]

    fetched = client.get(f"/orders/{ordered.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["estimated_delivery_time"]


def test_incoming_whatsapp_cancel_message_cancels_latest_active_order(client):
    add_menu_item(client)
    order_id = place_order(client).json()["id"]

    webhook = client.post("/whatsapp/incoming", json={"from": "+917904854535", "body": "Cancel"})

    assert webhook.status_code == 200
    assert webhook.json()["message"] == "Order cancelled via WhatsApp"
    assert client.get(f"/orders/{order_id}").json()["status"] == "cancelled"


def test_customer_gets_random_next_order_coupon(client):
    add_menu_item(client)

    ordered = place_order(client)

    assert ordered.status_code == 200
    coupon_code = ordered.json()["generated_coupon_code"]
    assert coupon_code.startswith("NEXT")
    coupon_messages = [message for _, message in client.sent_messages if coupon_code in message]
    assert coupon_messages
    assert "10% off your next order" in coupon_messages[0]


def test_generated_next_order_coupon_applies_once(client):
    add_menu_item(client)

    first_order = place_order(client)
    assert first_order.status_code == 200
    coupon_code = first_order.json()["generated_coupon_code"]

    discounted_order = place_order(client, whatsapp_number="+917904854536", coupon_code=coupon_code)
    assert discounted_order.status_code == 200
    assert discounted_order.json()["coupon_code"] == coupon_code
    assert discounted_order.json()["discount_amount"] == pytest.approx(20.9)
    assert discounted_order.json()["total_amount"] == pytest.approx(188.05)

    reused_coupon = place_order(client, whatsapp_number="+917904854537", coupon_code=coupon_code)
    assert reused_coupon.status_code == 400
    assert reused_coupon.json()["detail"] == "Coupon has reached its usage limit"


def test_multi_restaurant_orders_use_selected_restaurant(client):
    add_menu_item(client, name="Pizza", restaurant_name="North")
    add_menu_item(client, name="Burger", restaurant_name="South")

    north_order = place_order(client, items=["Pizza"], restaurant_name="North")
    assert north_order.status_code == 200
    assert north_order.json()["restaurant_name"] == "North"

    south_order = place_order(client, items=["Burger"], restaurant_name="South")
    assert south_order.status_code == 200
    assert south_order.json()["restaurant_name"] == "South"

    wrong_restaurant = place_order(client, items=["Burger"], restaurant_name="North")
    assert wrong_restaurant.status_code == 400
    assert "restaurant 'North'" in wrong_restaurant.json()["detail"]


def test_coupon_discount_can_be_validated_and_applied(client):
    add_menu_item(client)
    assert create_coupon(client).status_code == 200

    validation = client.post(
        "/coupons/validate",
        json={"coupon_code": "SAVE10", "items": ["Pizza"], "restaurant_name": "Default"},
    )
    assert validation.status_code == 200
    assert validation.json()["discount_amount"] == pytest.approx(20.9)

    ordered = place_order(client, coupon_code="SAVE10")
    assert ordered.status_code == 200
    assert ordered.json()["coupon_code"] == "SAVE10"
    assert ordered.json()["discount_amount"] == pytest.approx(20.9)
    assert ordered.json()["total_amount"] == pytest.approx(188.05)

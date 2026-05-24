from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import re
import secrets
import string
from typing import List
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import database, models, schemas, whatsapp_service

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def run_database_migration():
    database.ensure_schema(database.engine)


ORDER_STATUS_FLOW = ["pending", "preparing", "out-for-delivery", "delivered"]
DEFAULT_RESTAURANT = "Default"
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")
ETA_MINUTES = {
    "pending": 30,
    "preparing": 20,
    "out-for-delivery": 10,
    "delivered": 0,
    "cancelled": 0,
}
TAX_RATE = 0.05
MONEY = Decimal("0.01")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = []
    for error in exc.errors():
        field = " -> ".join(str(part) for part in error.get("loc", []) if part != "body")
        message = error.get("msg", "Invalid value")
        messages.append(f"{field}: {message}" if field else message)
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request payload. " + "; ".join(messages)},
    )


def validate_status_transition(current_status: str, requested_status: str):
    if requested_status not in ORDER_STATUS_FLOW:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed statuses: {', '.join(ORDER_STATUS_FLOW)}",
        )
    if current_status not in ORDER_STATUS_FLOW:
        raise HTTPException(
            status_code=400,
            detail=f"Order is {current_status} and cannot continue through the delivery flow.",
        )

    current_index = ORDER_STATUS_FLOW.index(current_status)
    requested_index = ORDER_STATUS_FLOW.index(requested_status)
    if requested_index != current_index + 1:
        next_status = (
            ORDER_STATUS_FLOW[current_index + 1]
            if current_index + 1 < len(ORDER_STATUS_FLOW)
            else None
        )
        detail = (
            f"Invalid status transition. Order must move from {current_status} to {next_status}."
            if next_status
            else "Invalid status transition. Delivered orders cannot be updated further."
        )
        raise HTTPException(status_code=400, detail=detail)


def normalize_phone_number(phone_number: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", phone_number or "")
    if not PHONE_PATTERN.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number. Enter a valid phone number in international format, for example +919876543210.",
        )
    return cleaned if cleaned.startswith("+") else f"+{cleaned}"


def normalize_restaurant_name(restaurant_name: str | None) -> str:
    value = restaurant_name.strip() if restaurant_name else ""
    return value or DEFAULT_RESTAURANT


def normalize_item_names(item_names: List[str]) -> List[str]:
    normalized = []
    for item_name in item_names:
        value = str(item_name).strip() if item_name is not None else ""
        if not value:
            raise HTTPException(status_code=400, detail="Menu item names cannot be empty")
        normalized.append(value)
    return normalized


def format_estimated_delivery_time(status: str) -> str:
    eta = datetime.now(timezone.utc) + timedelta(minutes=ETA_MINUTES.get(status, 0))
    return eta.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def estimated_delivery_time_for_status(status: str) -> str | None:
    if status in {"pending", "delivered", "cancelled"}:
        return None
    return format_estimated_delivery_time(status)


def round_money(value: float) -> float:
    return float(Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP))


def serialize_order(order: models.Order):
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "whatsapp_number": order.whatsapp_number,
        "items": [item.strip() for item in order.items.split(",") if item.strip()],
        "status": order.status,
        "restaurant_name": getattr(order, "restaurant_name", DEFAULT_RESTAURANT) or DEFAULT_RESTAURANT,
        "coupon_code": getattr(order, "coupon_code", None),
        "estimated_delivery_time": estimated_delivery_time_for_status(order.status),
        "discount_amount": round_money(getattr(order, "discount_amount", 0) or 0),
        "total_amount": round_money(getattr(order, "total_amount", 0) or 0),
    }


def generate_next_order_coupon(db: Session, restaurant_name: str) -> models.Coupon:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = "NEXT" + "".join(secrets.choice(alphabet) for _ in range(6))
        existing_coupon = db.query(models.Coupon).filter(models.Coupon.code == code).first()
        if not existing_coupon:
            coupon = models.Coupon(
                code=code,
                discount_type="percentage",
                discount_value=10,
                restaurant_name=normalize_restaurant_name(restaurant_name),
                usage_limit=1,
                is_active=True,
            )
            db.add(coupon)
            return coupon
    raise HTTPException(status_code=500, detail="Unable to generate coupon code. Please try again.")


def get_selected_menu_items(item_names: List[str], restaurant_name: str, db: Session):
    if not item_names:
        raise HTTPException(status_code=400, detail="Order must contain at least one menu item")

    normalized_names = normalize_item_names(item_names)
    selected_restaurant = normalize_restaurant_name(restaurant_name)
    menu_items = (
        db.query(models.MenuItem)
        .filter(models.MenuItem.restaurant_name == selected_restaurant)
        .all()
    )
    if not menu_items:
        raise HTTPException(
            status_code=400,
            detail=f"Restaurant '{selected_restaurant}' has no menu items. Choose another restaurant.",
        )

    menu_by_name = {item.name.strip().lower(): item for item in menu_items}
    missing = [name for name in normalized_names if name.lower() not in menu_by_name]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown menu items for restaurant '{selected_restaurant}': {', '.join(missing)}",
        )

    requested = {name.lower() for name in normalized_names}
    unavailable = [item.name for item in menu_items if item.name.lower() in requested and not item.is_available]
    if unavailable:
        raise HTTPException(
            status_code=400,
            detail=f"Unavailable menu items for restaurant '{selected_restaurant}': {', '.join(unavailable)}",
        )

    selected_items = [menu_by_name[name.lower()] for name in normalized_names]
    subtotal = round_money(sum(item.price for item in selected_items))
    return normalized_names, selected_items, subtotal


def get_coupon(coupon_code: str, db: Session):
    coupon = (
        db.query(models.Coupon)
        .filter(models.Coupon.code.ilike(coupon_code.strip()), models.Coupon.is_active == True)
        .first()
    )
    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid coupon code")
    return coupon


def calculate_bill_total(subtotal: float) -> float:
    return round_money(subtotal + (subtotal * TAX_RATE))


def calculate_discount(coupon: models.Coupon, discount_base: float, restaurant_name: str) -> float:
    if coupon.restaurant_name and coupon.restaurant_name != normalize_restaurant_name(restaurant_name):
        raise HTTPException(status_code=400, detail="Coupon is not valid for this restaurant")
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise HTTPException(status_code=400, detail="Coupon has reached its usage limit")
    if discount_base < (coupon.min_order_value or 0):
        raise HTTPException(status_code=400, detail=f"Minimum order value of {coupon.min_order_value} is required for this coupon")
    if coupon.discount_type == "percentage":
        return round_money(discount_base * (coupon.discount_value / 100))
    return round_money(min(discount_base, coupon.discount_value))


def send_whatsapp_or_raise(to_number: str, message_body: str):
    try:
        whatsapp_service.send_whatsapp_msg(to_number, message_body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to send WhatsApp message: {exc}") from exc


def cancel_order_record(order: models.Order, db: Session):
    if order.status == "delivered":
        raise HTTPException(status_code=400, detail="Delivered orders cannot be cancelled")
    order.status = "cancelled"
    db.commit()
    send_whatsapp_or_raise(order.whatsapp_number, "Your order has been cancelled.")
    return {"message": "Order cancelled"}


# --- Menu Endpoints ---
@app.post("/menu/", response_model=schemas.MenuItem, operation_id="add_menu_item")
def create_menu_item(item: schemas.MenuItemCreate, db: Session = Depends(database.get_db)):
    restaurant_name = normalize_restaurant_name(item.restaurant_name)
    existing_item = (
        db.query(models.MenuItem)
        .filter(models.MenuItem.name.ilike(item.name.strip()), models.MenuItem.restaurant_name == restaurant_name)
        .first()
    )
    if existing_item:
        raise HTTPException(status_code=400, detail="Menu item already exists")

    db_item = models.MenuItem(
        name=item.name.strip(),
        description=item.description.strip(),
        price=item.price,
        is_available=item.is_available,
        restaurant_name=restaurant_name,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.patch("/menu/{item_id}", response_model=schemas.MenuItem, operation_id="update_menu_item")
def update_menu_item(item_id: int, item: schemas.MenuItemUpdate, db: Session = Depends(database.get_db)):
    db_item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    restaurant_name = normalize_restaurant_name(item.restaurant_name)
    duplicate_item = (
        db.query(models.MenuItem)
        .filter(
            models.MenuItem.name.ilike(item.name.strip()),
            models.MenuItem.restaurant_name == restaurant_name,
            models.MenuItem.id != item_id,
        )
        .first()
    )
    if duplicate_item:
        raise HTTPException(status_code=400, detail="Menu item already exists")

    db_item.name = item.name.strip()
    db_item.description = item.description.strip()
    db_item.price = item.price
    db_item.is_available = item.is_available
    db_item.restaurant_name = restaurant_name
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/menu/", response_model=List[schemas.MenuItem], operation_id="list_menu_items")
def get_menu(db: Session = Depends(database.get_db)):
    return db.query(models.MenuItem).all()


@app.get("/menu/{item_id}", response_model=schemas.MenuItem, operation_id="get_menu_item_by_id")
def get_menu_item(item_id: int, db: Session = Depends(database.get_db)):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return item


@app.patch("/menu/{item_id}/availability", response_model=schemas.MenuItem, operation_id="update_menu_item_availability")
def update_menu_item_availability(item_id: int, availability: schemas.MenuAvailabilityUpdate, db: Session = Depends(database.get_db)):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    item.is_available = availability.is_available
    db.commit()
    db.refresh(item)
    return item


# --- Coupon Endpoints ---
@app.post("/coupons/", response_model=schemas.Coupon, operation_id="create_coupon")
def create_coupon(coupon: schemas.CouponCreate, db: Session = Depends(database.get_db)):
    existing_coupon = db.query(models.Coupon).filter(models.Coupon.code.ilike(coupon.code.strip())).first()
    if existing_coupon:
        raise HTTPException(status_code=400, detail="Coupon code already exists")

    db_coupon = models.Coupon(
        code=coupon.code.strip(),
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        restaurant_name=normalize_restaurant_name(coupon.restaurant_name),
        min_order_value=coupon.min_order_value,
        usage_limit=coupon.usage_limit,
        is_active=coupon.is_active,
    )
    db.add(db_coupon)
    db.commit()
    db.refresh(db_coupon)
    return db_coupon


@app.get("/coupons/", response_model=List[schemas.Coupon], operation_id="list_coupons")
def list_coupons(db: Session = Depends(database.get_db)):
    return db.query(models.Coupon).all()


@app.post("/coupons/validate", response_model=schemas.CouponValidationResponse, operation_id="validate_coupon")
def validate_coupon(coupon_request: schemas.CouponValidationRequest, db: Session = Depends(database.get_db)):
    _, _, subtotal = get_selected_menu_items(coupon_request.items, coupon_request.restaurant_name, db)
    bill_total = calculate_bill_total(subtotal)
    coupon = get_coupon(coupon_request.coupon_code, db)
    discount = calculate_discount(coupon, bill_total, coupon_request.restaurant_name)
    return {"is_valid": True, "discount_amount": discount, "message": "Coupon applied"}


# --- Order Endpoints ---
@app.post("/orders/", response_model=schemas.Order, operation_id="place_order")
def place_order(order: schemas.OrderCreate, db: Session = Depends(database.get_db)):
    normalized_phone = normalize_phone_number(order.whatsapp_number)
    restaurant_name = normalize_restaurant_name(order.restaurant_name)
    normalized_items, _, subtotal = get_selected_menu_items(order.items, restaurant_name, db)
    bill_total = calculate_bill_total(subtotal)

    discount_amount = 0.0
    coupon = None
    if order.coupon_code:
        coupon = get_coupon(order.coupon_code, db)
        discount_amount = calculate_discount(coupon, bill_total, restaurant_name)

    total_amount = round_money(bill_total - discount_amount)
    new_order = models.Order(
        customer_name=order.customer_name,
        whatsapp_number=normalized_phone,
        items=", ".join(normalized_items),
        status="pending",
        restaurant_name=restaurant_name,
        coupon_code=coupon.code if coupon else None,
        discount_amount=discount_amount,
        total_amount=total_amount,
    )
    if coupon:
        coupon.used_count += 1
    next_coupon = generate_next_order_coupon(db, restaurant_name)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    db.refresh(next_coupon)

    ordered_items = ", ".join(normalized_items)
    discount_text = f" Discount applied: {discount_amount:.2f}." if discount_amount else ""
    send_whatsapp_or_raise(
        normalized_phone,
        f"Hello {order.customer_name}! Your order for {ordered_items} has been received from {restaurant_name}. Status: Pending confirmation.{discount_text} Use code {next_coupon.code} for 10% off your next order. Reply Cancel to cancel this order.",
    )

    response = serialize_order(new_order)
    response["generated_coupon_code"] = next_coupon.code
    return response


@app.patch("/orders/{order_id}", response_model=schemas.MessageResponse, operation_id="update_order_status")
def update_order_status(order_id: int, status_update: schemas.OrderStatusUpdate, db: Session = Depends(database.get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    validate_status_transition(order.status, status_update.status)
    order.status = status_update.status
    db.commit()
    estimated_delivery_time = estimated_delivery_time_for_status(order.status)
    eta_text = f" Estimated delivery: {estimated_delivery_time}." if estimated_delivery_time else ""
    send_whatsapp_or_raise(
        order.whatsapp_number,
        f"Update for your order: Status is now {order.status}.{eta_text}",
    )
    return {"message": "Status updated"}


@app.get("/orders/", response_model=List[schemas.Order], operation_id="list_orders")
def list_orders(include_all: bool = Query(False, description="Return cancelled and delivered orders too."), db: Session = Depends(database.get_db)):
    query = db.query(models.Order)
    if not include_all:
        query = query.filter(models.Order.status.notin_(["cancelled", "delivered"]))
    return [serialize_order(order) for order in query.all()]


@app.get("/orders/{order_id}", response_model=schemas.Order, operation_id="get_order_by_id")
def get_order(order_id: int, db: Session = Depends(database.get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return serialize_order(order)


@app.delete("/orders/{order_id}", response_model=schemas.MessageResponse, operation_id="cancel_order")
def cancel_order(order_id: int, db: Session = Depends(database.get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return cancel_order_record(order, db)


async def parse_whatsapp_message(request: Request) -> schemas.WhatsAppIncoming:
    content_type = request.headers.get("content-type", "")
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(status_code=400, detail="Missing WhatsApp payload")

    if "application/json" in content_type:
        payload = json.loads(raw_body.decode("utf-8"))
    else:
        parsed = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
        payload = {key: value[0] if value else "" for key, value in parsed.items()}

    from_value = payload.get("from") or payload.get("From")
    body_value = payload.get("body") or payload.get("Body")
    if not from_value or not body_value:
        raise HTTPException(status_code=400, detail="Missing from or body in WhatsApp payload")
    return schemas.WhatsAppIncoming.model_validate({"from": from_value, "body": body_value})


@app.post("/whatsapp/incoming", response_model=schemas.WhatsAppResponse, operation_id="incoming_whatsapp_message")
async def handle_incoming_whatsapp(request: Request, db: Session = Depends(database.get_db)):
    message = await parse_whatsapp_message(request)
    normalized_phone = normalize_phone_number(message.from_)
    if message.body.strip().lower() == "cancel":
        order = (
            db.query(models.Order)
            .filter(models.Order.whatsapp_number == normalized_phone, models.Order.status.notin_(["cancelled", "delivered"]))
            .order_by(models.Order.id.desc())
            .first()
        )
        if not order:
            raise HTTPException(status_code=404, detail="No active order found for this phone number")
        cancel_order_record(order, db)
        return {"message": "Order cancelled via WhatsApp"}

    return {"message": "Message received"}

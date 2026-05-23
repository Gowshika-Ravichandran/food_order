from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models, schemas, database, whatsapp_service 

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

ORDER_STATUS_FLOW = ["pending", "preparing", "out-for-delivery", "delivered"]


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
        if next_status:
            detail = f"Invalid status transition. Order must move from {current_status} to {next_status}."
        else:
            detail = "Invalid status transition. Delivered orders cannot be updated further."
        raise HTTPException(status_code=400, detail=detail)


def serialize_order(order: models.Order):
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "whatsapp_number": order.whatsapp_number,
        "items": [item.strip() for item in order.items.split(",") if item.strip()],
        "status": order.status,
    }


def validate_order_items(item_names: List[str], db: Session):
    if not item_names:
        raise HTTPException(status_code=400, detail="Order must contain at least one menu item")

    normalized_names = {name.strip().lower() for name in item_names}
    if "" in normalized_names:
        raise HTTPException(status_code=400, detail="Menu item names cannot be empty")

    menu_items = db.query(models.MenuItem).all()
    menu_by_name = {item.name.lower(): item for item in menu_items}

    missing = [name for name in item_names if name.strip().lower() not in menu_by_name]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown menu items: {', '.join(missing)}")

    unavailable = [
        item.name
        for item in menu_items
        if item.name.lower() in normalized_names and not item.is_available
    ]
    if unavailable:
        raise HTTPException(status_code=400, detail=f"Unavailable menu items: {', '.join(unavailable)}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Menu Endpoints ---
@app.post("/menu/", response_model=schemas.MenuItem, operation_id="add_menu_item")
def create_menu_item(item: schemas.MenuItemCreate, db: Session = Depends(database.get_db)):
    existing_item = (
        db.query(models.MenuItem)
        .filter(models.MenuItem.name.ilike(item.name.strip()))
        .first()
    )
    if existing_item:
        raise HTTPException(status_code=400, detail="Menu item already exists")

    item_data = item.model_dump()
    item_data["name"] = item_data["name"].strip()
    item_data["description"] = item_data["description"].strip()
    db_item = models.MenuItem(**item_data)
    db.add(db_item)
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
def update_menu_item_availability(
    item_id: int,
    availability: schemas.MenuAvailabilityUpdate,
    db: Session = Depends(database.get_db),
):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    item.is_available = availability.is_available
    db.commit()
    db.refresh(item)
    return item

# --- Order Endpoints ---
@app.post("/orders/", response_model=schemas.Order, operation_id="place_order")
def place_order(order: schemas.OrderCreate, db: Session = Depends(database.get_db)):
    validate_order_items(order.items, db)

    new_order = models.Order(
        customer_name=order.customer_name,
        whatsapp_number=order.whatsapp_number,
        items=", ".join(order.items),
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # Send WhatsApp Confirmation
    msg = f"Hello {order.customer_name}! Your order for {new_order.items} has been received. Status: Pending."
    whatsapp_service.send_whatsapp_msg(order.whatsapp_number, msg)
    
    return serialize_order(new_order)

@app.patch("/orders/{order_id}", response_model=schemas.MessageResponse, operation_id="update_order_status")
def update_order_status(order_id: int, status_update: schemas.OrderStatusUpdate, db: Session = Depends(database.get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    requested_status = status_update.status
    validate_status_transition(order.status, requested_status)
    
    order.status = requested_status
    db.commit()
    
    # Send WhatsApp Update
    msg = f"Update for your order: Status is now {order.status}."
    whatsapp_service.send_whatsapp_msg(order.whatsapp_number, msg)
    
    return {"message": "Status updated"}

@app.get("/orders/", response_model=List[schemas.Order], operation_id="list_orders")
def list_orders(db: Session = Depends(database.get_db)):
    active_orders = (
        db.query(models.Order)
        .filter(models.Order.status.notin_(["cancelled", "delivered"]))
        .all()
    )
    return [serialize_order(order) for order in active_orders]

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
    if order.status == "delivered":
        raise HTTPException(status_code=400, detail="Delivered orders cannot be cancelled")

    order.status = "cancelled"
    db.commit()
    whatsapp_service.send_whatsapp_msg(order.whatsapp_number, "Your order has been cancelled.")
    return {"message": "Order cancelled"}

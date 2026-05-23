from pydantic import BaseModel, ConfigDict
from typing import List, Literal

# --- Menu Item Schemas ---
class MenuItemBase(BaseModel):
    name: str
    description: str
    price: float
    is_available: bool = True

class MenuItemCreate(MenuItemBase):
    pass

class MenuAvailabilityUpdate(BaseModel):
    is_available: bool

class MenuItem(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int

# --- Order Schemas ---
class OrderBase(BaseModel):
    customer_name: str
    whatsapp_number: str
    items: List[str]

class OrderCreate(OrderBase):
    pass

class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "preparing", "out-for-delivery", "delivered"]

class Order(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str

class MessageResponse(BaseModel):
    message: str

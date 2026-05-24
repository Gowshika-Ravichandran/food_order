from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal

# --- Menu Item Schemas ---
class MenuItemBase(BaseModel):
    name: str
    description: str
    price: float
    is_available: bool = True
    restaurant_name: str = "Default"

class MenuItemCreate(MenuItemBase):
    pass

class MenuItemUpdate(MenuItemBase):
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
    restaurant_name: str = "Default"
    coupon_code: str | None = None

class OrderCreate(OrderBase):
    pass

class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "preparing", "out-for-delivery", "delivered"]

class CouponBase(BaseModel):
    code: str
    discount_type: Literal["percentage", "fixed"] = "percentage"
    discount_value: float = 10
    restaurant_name: str = "Default"
    min_order_value: float = 0
    usage_limit: int | None = None
    is_active: bool = True

class CouponCreate(CouponBase):
    pass

class Coupon(CouponBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    used_count: int

class CouponValidationRequest(BaseModel):
    coupon_code: str
    items: List[str]
    restaurant_name: str = "Default"

class CouponValidationResponse(BaseModel):
    is_valid: bool
    discount_amount: float
    message: str

class WhatsAppIncoming(BaseModel):
    from_: str = Field(alias="from")
    body: str

    model_config = ConfigDict(populate_by_name=True)

class WhatsAppResponse(BaseModel):
    message: str

class Order(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    estimated_delivery_time: str | None = None
    discount_amount: float = 0
    total_amount: float = 0
    generated_coupon_code: str | None = None

class MessageResponse(BaseModel):
    message: str

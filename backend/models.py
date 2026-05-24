from sqlalchemy import Boolean, Column, Float, Integer, String
from .database import Base

class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    price = Column(Float)
    is_available = Column(Boolean, default=True)
    restaurant_name = Column(String, default="Default")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String)
    whatsapp_number = Column(String)
    items = Column(String) # Simple string storage for items
    status = Column(String, default="pending") # pending, preparing, out-for-delivery, delivered, cancelled
    restaurant_name = Column(String, default="Default")
    coupon_code = Column(String, nullable=True)
    discount_amount = Column(Float, default=0)
    total_amount = Column(Float, default=0)


class Coupon(Base):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    discount_type = Column(String, default="percentage")
    discount_value = Column(Float, default=10)
    restaurant_name = Column(String, default="Default")
    min_order_value = Column(Float, default=0)
    usage_limit = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

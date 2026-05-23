from sqlalchemy import Column, Integer, String, Float, Boolean
from .database import Base

class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    price = Column(Float)
    is_available = Column(Boolean, default=True)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String)
    whatsapp_number = Column(String)
    items = Column(String) # Simple string storage for items
    status = Column(String, default="pending") # pending, preparing, out-for-delivery, delivered, cancelled
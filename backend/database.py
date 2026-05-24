from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./food_order.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema(target_engine):
    Base.metadata.create_all(bind=target_engine)
    inspector = inspect(target_engine)

    with target_engine.begin() as connection:
        menu_columns = {column["name"] for column in inspector.get_columns("menu_items")}
        if "restaurant_name" not in menu_columns:
            connection.execute(text("ALTER TABLE menu_items ADD COLUMN restaurant_name VARCHAR DEFAULT 'Default'"))
            connection.execute(text("UPDATE menu_items SET restaurant_name = 'Default' WHERE restaurant_name IS NULL"))

        order_columns = {column["name"] for column in inspector.get_columns("orders")}
        if "restaurant_name" not in order_columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN restaurant_name VARCHAR DEFAULT 'Default'"))
            connection.execute(text("UPDATE orders SET restaurant_name = 'Default' WHERE restaurant_name IS NULL"))
        if "coupon_code" not in order_columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN coupon_code VARCHAR"))
        if "discount_amount" not in order_columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN discount_amount FLOAT DEFAULT 0"))
            connection.execute(text("UPDATE orders SET discount_amount = 0 WHERE discount_amount IS NULL"))
        if "total_amount" not in order_columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN total_amount FLOAT DEFAULT 0"))
            connection.execute(text("UPDATE orders SET total_amount = 0 WHERE total_amount IS NULL"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

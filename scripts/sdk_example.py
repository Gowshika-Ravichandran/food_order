import food_order_sdk
from food_order_sdk.api.default_api import DefaultApi
from food_order_sdk.models.menu_item_create import MenuItemCreate
from food_order_sdk.models.order_create import OrderCreate
from food_order_sdk.models.order_status_update import OrderStatusUpdate


configuration = food_order_sdk.Configuration(host="http://localhost:8000")

with food_order_sdk.ApiClient(configuration) as api_client:
    api = DefaultApi(api_client)

    menu_item = api.add_menu_item(
        MenuItemCreate(
            name="Pizza",
            description="Cheese pizza",
            price=199.0,
            is_available=True,
        )
    )
    print("Created menu item:", menu_item)

    order = api.place_order(
        OrderCreate(
            customer_name="John Doe",
            whatsapp_number="+917904854535",
            items=["Pizza"],
        )
    )
    print("Created order:", order)

    api.update_order_status(order.id, OrderStatusUpdate(status="preparing"))

    orders = api.list_orders()
    print("Active orders:", orders)

    fetched_order = api.get_order_by_id(order.id)
    print("Fetched order:", fetched_order)

# WhatsApp Food Ordering System

Food ordering dashboard with a FastAPI + SQLite backend, React frontend, Twilio WhatsApp notifications, OpenAPI documentation, generated Python SDK workflow, and backend tests.

## Requirements

- Python 3.12+
- Node.js + npm
- Java 17+ for OpenAPI Generator CLI
- Twilio WhatsApp Sandbox or WhatsApp Business credentials

## Setup

Run:

```bat
setup.bat
```

This creates the Python virtual environment, installs backend dependencies, and installs React dependencies.

## WhatsApp Configuration

Create or update `.env` in the project root:

```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

For Twilio Sandbox testing, join the sandbox from the customer WhatsApp number before placing an order.

## Run

Start backend and frontend:

```bat
run.bat
```

Backend:

```text
http://localhost:8000
```

Frontend:

```text
http://localhost:3000
```

OpenAPI:

```text
http://localhost:8000/openapi.json
http://localhost:8000/docs
```

## Backend Endpoints

- `POST /menu/` add a menu item
- `GET /menu/` list menu items
- `GET /menu/{item_id}` get one menu item
- `POST /orders/` place an order and send WhatsApp confirmation
- `GET /orders/` list active orders
- `GET /orders/{order_id}` get one order
- `PATCH /orders/{order_id}` update order status and send WhatsApp update
- `DELETE /orders/{order_id}` cancel order and send WhatsApp cancellation

Order status must move in this exact order:

```text
pending -> preparing -> out-for-delivery -> delivered
```

## Generate Python SDK

Install Java 17 or later, then run:

```bat
generate_sdk.bat
```

The SDK will be generated into:

```text
sdk\python
```

Sample usage is in:

```text
scripts\sdk_example.py
```

## Tests

Run:

```bat
venv\Scripts\python.exe -m pytest -q
```

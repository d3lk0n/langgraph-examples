from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid
from enum import Enum

app = FastAPI(root_path='/pizza-api')

# Enums and Models
class OrderStatus(str, Enum):
    RECEIVED = "received"
    PREPARING = "preparing"
    ON_DELIVERY = "on_delivery"
    DELIVERED = "delivered"

class Address(BaseModel):
    city: str
    street: str
    house_number: str

class OrderCreate(BaseModel):
    pizza_id: int
    city: str
    street: str
    house_number: str

class Order(BaseModel):
    id: str
    pizza_id: int
    address: Address
    status: OrderStatus

# Mock database
pizzas = [
    {"id": 1, "name": "Margherita"},
    {"id": 2, "name": "Pepperoni"},
    {"id": 3, "name": "Hawaiian"},
    {"id": 4, "name": "Quattro Formaggi"}
]

# Store orders in memory (in a real application, use a proper database)
orders = {}

# Valid cities for delivery
VALID_CITIES = ["Leipzig", "Halle", "Dresden"]

@app.get("/pizza")
async def list_pizzas():
    """List all available pizzas"""
    return pizzas

@app.post("/address/validate")
async def validate_address(address: Address):
    """Validate delivery address"""
    # Check if city is serviceable
    if address.city not in VALID_CITIES:
        raise HTTPException(
            status_code=400,
            detail=f"We don't deliver to {address.city}. Available cities: {', '.join(VALID_CITIES)}"
        )
    
    # Basic validation for street and house number
    if len(address.street) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid street name"
        )
    
    if not address.house_number:
        raise HTTPException(
            status_code=400,
            detail="House number is required"
        )

    return {"message": "Address is valid", "address": address}

@app.post("/order")
async def create_order(order: OrderCreate):
    """Create a neworder"""
    # Validate pizza_id
    if not any(pizza["id"] == order.pizza_id for pizza in pizzas):
        raise HTTPException(
            status_code=404,
            detail="Pizza not found"
        )

    # Validate address
    address = Address(
        city=order.city,
        street=order.street,
        house_number=order.house_number
    )
    await validate_address(address)

    # Create order
    order_id = str(uuid.uuid4())
    new_order = Order(
        id=order_id,
        pizza_id=order.pizza_id,
        address=address,
        status=OrderStatus.RECEIVED
    )
    
    # Save order
    orders[order_id] = new_order

    return {"order_id": order_id, "status": OrderStatus.RECEIVED}

@app.get("/order/{order_id}")
async def get_order_status(order_id: str):
    """Get order status by order ID"""
    if order_id not in orders:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )
    
    return {
        "order_id": order_id,
        "status": orders[order_id].status,
        "pizza_id": orders[order_id].pizza_id,
        "address": orders[order_id].address
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

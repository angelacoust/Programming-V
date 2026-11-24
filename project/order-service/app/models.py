from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OrderStatus = Literal["Pending Payment", "Paid"]


class OrderItem(BaseModel):
    item_id: str | None = None
    itemId: str | None = None
    name: str | None = None
    price: float | None = None
    quantity: int = 1


class OrderCreate(BaseModel):
    """Body of POST /orders (flexible field names)."""

    item_id: str | None = None
    itemId: str | None = None
    clothing_id: str | None = None
    clothes_id: str | None = None
    item: dict | None = None
    items: list | None = None
    item_name: str | None = None
    itemName: str | None = None
    name: str | None = None
    item_price: float | None = None
    itemPrice: float | None = None
    price: float | None = None
    amount: float | None = None
    total: float | None = None
    buyer: str | None = None
    buyerName: str | None = None
    buyer_name: str | None = None
    seller: str | None = None
    sellerName: str | None = None
    seller_name: str | None = None
    quantity: int | None = 1

    model_config = ConfigDict(extra="allow")


class Order(BaseModel):
    """An order as returned by the API."""

    id: str
    orderId: str | None = None
    item_id: str | None = None
    itemId: str | None = None
    item_name: str | None = None
    itemName: str | None = None
    name: str | None = None
    item_price: float | None = None
    itemPrice: float | None = None
    price: float | None = None
    amount: float
    total: float | None = None
    buyer: str
    buyerName: str | None = None
    buyer_name: str | None = None
    seller: str
    sellerName: str | None = None
    seller_name: str | None = None
    status: OrderStatus = "Pending Payment"
    paid: bool = False
    created_at: datetime

    model_config = ConfigDict(extra="allow")


class PayRequest(BaseModel):
    order_ids: list[str] = Field(default_factory=list)
    orderIds: list[str] = Field(default_factory=list)
    table_number: int | None = None

    model_config = ConfigDict(extra="allow")


class PayResult(BaseModel):
    orders_paid: int
    orderIds: list[str] = Field(default_factory=list)

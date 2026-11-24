import os

import httpx
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ReturnDocument

from app.clients import ServiceUnavailable, mark_item_sold, notify_item_sold
from app.db import orders
from app.models import Order, OrderCreate, OrderStatus, PayRequest, PayResult

api = FastAPI(title="Order service")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_order(doc: dict) -> Order:
    item_id = doc.get("item_id")
    item_name = doc.get("item_name")
    item_price = doc.get("item_price")
    amount = doc.get("amount", 0)
    buyer = doc.get("buyer")
    seller = doc.get("seller")
    order_id = str(doc["_id"])
    return Order(
        id=order_id,
        orderId=order_id,
        item_id=item_id,
        itemId=item_id,
        item_name=item_name,
        itemName=item_name,
        name=item_name,
        item_price=item_price,
        itemPrice=item_price,
        price=item_price if item_price is not None else amount,
        amount=amount,
        total=amount,
        buyer=buyer,
        buyerName=buyer,
        buyer_name=buyer,
        seller=seller,
        sellerName=seller,
        seller_name=seller,
        status=doc.get("status", "Pending Payment"),
        paid=doc.get("paid", False),
        created_at=doc.get("created_at"),
    )


def parse_order_id(order_id: str) -> ObjectId:
    try:
        return ObjectId(order_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Order not found")


def normalize_create(body: OrderCreate) -> dict:
    item = body.item if isinstance(body.item, dict) else {}
    # Support reference-style `items: [{item_id, quantity}]` payloads.
    if not item and isinstance(body.items, list) and body.items:
        first = body.items[0]
        if isinstance(first, dict):
            item = first
    item_id = (
        body.item_id or body.itemId or body.clothing_id or body.clothes_id
        or item.get("id") or item.get("item_id") or item.get("itemId") or item.get("_id")
    )
    item_name = (
        body.item_name or body.itemName or body.name
        or item.get("name") or item.get("title")
    )
    item_price = (
        body.item_price or body.itemPrice or body.price
        or item.get("price") or item.get("amount")
    )
    amount = body.amount or body.total or body.price or item_price
    buyer = body.buyer or body.buyerName or body.buyer_name
    seller = body.seller or body.sellerName or body.seller_name
    quantity = body.quantity if body.quantity else 1

    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")
    if not buyer:
        raise HTTPException(status_code=400, detail="buyer is required")
    if not seller:
        raise HTTPException(status_code=400, detail="seller is required")
    if amount is None:
        raise HTTPException(status_code=400, detail="amount is required")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount must be a number")
    if item_price is None:
        item_price = amount
    else:
        try:
            item_price = float(item_price)
        except (TypeError, ValueError):
            item_price = amount

    return {
        "item_id": str(item_id),
        "item_name": item_name,
        "item_price": item_price,
        "quantity": int(quantity) if quantity else 1,
        "buyer": str(buyer),
        "seller": str(seller),
        "amount": round(amount, 2),
    }


async def mark_order_paid(order_id: str) -> Order:
    oid = parse_order_id(order_id)
    doc = await orders.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if not doc.get("paid", False):
        await orders.update_one({"_id": oid}, {"$set": {"status": "Paid", "paid": True}})
        doc = await orders.find_one({"_id": oid})
    order = to_order(doc)

    # Trigger downstream side effects (best effort)
    try:
        await mark_item_sold(order.item_id)
    except Exception:
        pass
    try:
        await notify_item_sold(
            buyer=order.buyer,
            seller=order.seller,
            item_id=order.item_id,
            item_name=order.item_name,
            order_id=order.id,
            amount=order.amount,
        )
    except Exception:
        pass
    return order


@api.post("/orders", response_model=Order, status_code=201)
async def create_order(order: OrderCreate):
    data = normalize_create(order)
    # Best-effort: fetch the item name from the catalog if the client didn't send it
    if not data["item_name"]:
        try:
            async with httpx.AsyncClient(base_url=os.getenv("CATALOG_URL", "http://localhost:8001"), timeout=2) as client:
                response = await client.get(f"/clothes/{data['item_id']}")
            if response.status_code == 200:
                data["item_name"] = response.json().get("name")
        except Exception:
            pass
    now = datetime.now(timezone.utc)
    created_at = now.replace(microsecond=now.microsecond // 1000 * 1000)
    doc = {
        "item_id": data["item_id"],
        "item_name": data["item_name"],
        "item_price": data["item_price"],
        "quantity": data["quantity"],
        "buyer": data["buyer"],
        "seller": data["seller"],
        "amount": data["amount"],
        "status": "Pending Payment",
        "paid": False,
        "created_at": created_at,
    }
    result = await orders.insert_one(doc)
    doc["_id"] = result.inserted_id
    return to_order(doc)


@api.get("/orders/buyer/{buyer_name}", response_model=list[Order])
async def list_orders_by_buyer(buyer_name: str):
    docs = await orders.find({"buyer": buyer_name}).sort([("created_at", -1), ("_id", -1)]).to_list()
    return [to_order(doc) for doc in docs]


@api.get("/orders", response_model=list[Order])
async def list_orders(
    buyer: str | None = None,
    seller: str | None = None,
    paid: bool | None = None,
    status: str | None = None,
):
    query = {}
    if buyer is not None:
        query["buyer"] = buyer
    if seller is not None:
        query["seller"] = seller
    if paid is not None:
        query["paid"] = paid
    if status is not None:
        query["status"] = status
    docs = await orders.find(query).sort([("created_at", -1), ("_id", -1)]).to_list()
    return [to_order(doc) for doc in docs]


@api.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    doc = await orders.find_one({"_id": parse_order_id(order_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return to_order(doc)


@api.post("/orders/{order_id}/pay", response_model=Order)
async def pay_order(order_id: str):
    return await mark_order_paid(order_id)


@api.post("/orders/{order_id}/mark-paid", response_model=Order)
async def mark_paid_order(order_id: str):
    return await mark_order_paid(order_id)


@api.post("/orders/{order_id}/paid", response_model=Order)
async def paid_order(order_id: str):
    return await mark_order_paid(order_id)


@api.patch("/orders/{order_id}", response_model=Order)
async def update_order(order_id: str, body: dict):
    oid = parse_order_id(order_id)
    doc = await orders.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if body.get("paid") is True or body.get("status") in ("Paid", "paid"):
        return await mark_order_paid(order_id)
    if "status" in body:
        await orders.update_one({"_id": oid}, {"$set": {"status": body["status"]}})
    doc = await orders.find_one({"_id": oid})
    return to_order(doc)


@api.post("/orders/pay", response_model=PayResult)
async def pay_orders(body: PayRequest):
    ids = body.order_ids or body.orderIds or []
    paid_count = 0
    for oid in ids:
        try:
            await mark_order_paid(oid)
            paid_count += 1
        except HTTPException:
            continue
    return PayResult(orders_paid=paid_count, orderIds=ids)


# Socket.IO is not hosted here (Notification service handles realtime).
app = api

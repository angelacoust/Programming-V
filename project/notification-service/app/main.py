import os
from datetime import datetime, timezone

import httpx
import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.db import notifications
from app.sockets import ROOM_PATTERN, sio

api = FastAPI(title="Notification service")

CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8001")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def extract(payload: dict, *keys):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


async def push_item_sold(payload: dict) -> dict:
    buyer = extract(payload, "buyer", "buyerName", "buyer_name", "user", "username")
    seller = extract(payload, "seller", "sellerName", "seller_name")
    item_id = extract(payload, "item_id", "itemId", "clothing_id", "clothes_id", "id")
    item_name = extract(payload, "item_name", "itemName", "name", "title")
    order_id = extract(payload, "order_id", "orderId")
    amount = extract(payload, "amount", "price", "total", "item_price")

    event = {
        "item_id": item_id,
        "itemId": item_id,
        "item_name": item_name,
        "itemName": item_name,
        "order_id": order_id,
        "orderId": order_id,
        "buyer": buyer,
        "seller": seller,
        "amount": amount,
        "status": "Sold",
    }

    # Persist a record (best effort).
    try:
        await notifications.insert_one(
            {
                "buyer": buyer,
                "seller": seller,
                "item_id": item_id,
                "item_name": item_name,
                "order_id": order_id,
                "amount": amount,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        pass

    buyer_room = f"buyer-{buyer}" if buyer else None
    seller_room = f"seller-{seller}" if seller else None

    if buyer_room and ROOM_PATTERN.fullmatch(buyer_room):
        await sio.emit("item-sold", event, room=buyer_room)
    if seller_room and ROOM_PATTERN.fullmatch(seller_room):
        await sio.emit("item-sold", event, room=seller_room)

    # Notify users who favorited this item (best effort).
    if item_id:
        try:
            async with httpx.AsyncClient(base_url=CATALOG_URL, timeout=5) as client:
                response = await client.get(f"/favorites/item/{item_id}")
            if response.status_code == 200:
                fav_users = response.json() or []
                for fav_user in fav_users:
                    if fav_user in (buyer, seller):
                        continue
                    room = f"buyer-{fav_user}"
                    if ROOM_PATTERN.fullmatch(room):
                        await sio.emit("item-sold", event, room=room)
                    # Persist a favorite notification (best effort).
                    try:
                        await notifications.insert_one({
                            "buyer": fav_user,
                            "seller": seller,
                            "item_id": item_id,
                            "item_name": item_name,
                            "event": "favorite_sold",
                            "created_at": datetime.now(timezone.utc),
                        })
                    except Exception:
                        pass
        except Exception:
            pass

    return {"ok": True, "buyer_room": buyer_room, "seller_room": seller_room}


@api.post("/notifications/item-sold")
async def notify_item_sold_endpoint(payload: dict):
    return await push_item_sold(payload)


@api.post("/notifications")
async def notify_endpoint(payload: dict):
    # If the payload indicates an item sold, push it.
    if any(k in payload for k in ("item_id", "itemId", "order_id", "orderId", "sold")):
        return await push_item_sold(payload)
    # Generic notification passthrough.
    event = payload.get("event", "notification")
    room = payload.get("room")
    data = payload.get("data", payload)
    if room and ROOM_PATTERN.fullmatch(str(room)):
        await sio.emit(str(event), data, room=room)
    return {"ok": True}


@api.post("/notify")
async def notify_alias(payload: dict):
    return await notify_endpoint(payload)


@api.post("/sold")
async def sold_endpoint(payload: dict):
    return await push_item_sold(payload)


@api.post("/item-sold")
async def item_sold_endpoint(payload: dict):
    return await push_item_sold(payload)


def to_notification(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "buyer": doc.get("buyer"),
        "seller": doc.get("seller"),
        "event": doc.get("event"),
        "item_id": doc.get("item_id"),
        "itemId": doc.get("item_id"),
        "item_name": doc.get("item_name"),
        "itemName": doc.get("item_name"),
        "order_id": doc.get("order_id"),
        "orderId": doc.get("order_id"),
        "amount": doc.get("amount"),
        "created_at": doc.get("created_at"),
    }


@api.get("/notifications/{user}")
async def list_notifications(user: str, role: str | None = None):
    query = {"buyer": user} if role == "buyer" else {"seller": user}
    docs = await notifications.find(query).sort([("created_at", -1)]).to_list()
    return [to_notification(doc) for doc in docs]


@api.get("/notifications")
async def list_notifications_query(
    user: str | None = None,
    seller: str | None = None,
    buyer: str | None = None,
    role: str | None = None,
):
    if seller:
        query = {"seller": seller}
    elif buyer:
        query = {"buyer": buyer}
    elif user:
        query = {"buyer": user} if role == "buyer" else {"seller": user}
    else:
        query = {}
    docs = await notifications.find(query).sort([("created_at", -1)]).to_list()
    return [to_notification(doc) for doc in docs]


@api.get("/notifications/seller/{user}")
async def list_sold_notifications(user: str):
    docs = await notifications.find({"seller": user}).sort([("created_at", -1)]).to_list()
    return [to_notification(doc) for doc in docs]


from bson import ObjectId
from bson.errors import InvalidId


@api.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    try:
        oid = ObjectId(notification_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Notification not found")
    result = await notifications.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True, "deleted": notification_id}


@api.delete("/notifications/seller/{user}")
async def delete_notifications_for_seller(user: str):
    result = await notifications.delete_many({"seller": user})
    return {"ok": True, "deleted_count": result.deleted_count}


@api.delete("/notifications")
async def delete_notifications_query(
    user: str | None = None,
    seller: str | None = None,
    buyer: str | None = None,
):
    query = {}
    if seller:
        query["seller"] = seller
    elif buyer:
        query["buyer"] = buyer
    elif user:
        query["seller"] = user
    result = await notifications.delete_many(query)
    return {"ok": True, "deleted_count": result.deleted_count}


async def push_item_deleted(payload: dict) -> dict:
    item_id = extract(payload, "item_id", "itemId", "clothing_id", "clothes_id", "id")
    item_name = extract(payload, "item_name", "itemName", "name", "title")
    users = payload.get("users") or payload.get("user_list") or []
    if not users and item_id:
        try:
            async with httpx.AsyncClient(base_url=CATALOG_URL, timeout=5) as client:
                response = await client.get(f"/favorites/item/{item_id}")
            if response.status_code == 200:
                users = response.json() or []
        except Exception:
            users = []
    event = {
        "item_id": item_id,
        "itemId": item_id,
        "item_name": item_name,
        "itemName": item_name,
        "status": "Deleted",
    }
    for user in users:
        room = f"buyer-{user}"
        if ROOM_PATTERN.fullmatch(room):
            await sio.emit("item-deleted", event, room=room)
        # Persist a favorite notification (best effort).
        try:
            await notifications.insert_one({
                "buyer": user,
                "seller": None,
                "item_id": item_id,
                "item_name": item_name,
                "event": "favorite_deleted",
                "created_at": datetime.now(timezone.utc),
            })
        except Exception:
            pass
    # Persist best effort.
    try:
        await notifications.insert_one({
            "buyer": None,
            "seller": None,
            "item_id": item_id,
            "item_name": item_name,
            "event": "deleted",
            "users": users,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass
    return {"ok": True, "notified": users}


@api.post("/notifications/item-deleted")
async def notify_item_deleted_endpoint(payload: dict):
    return await push_item_deleted(payload)


@api.post("/notifications/item-removed")
async def notify_item_removed_endpoint(payload: dict):
    return await push_item_deleted(payload)


@api.get("/notifications/user/{user}")
async def list_user_notifications(user: str):
    docs = await notifications.find({"$or": [{"buyer": user}, {"seller": user}]}).sort([("created_at", -1)]).to_list()
    return [to_notification(doc) for doc in docs]


@api.delete("/notifications/user/{user}")
async def delete_user_notifications(user: str):
    result = await notifications.delete_many({"$or": [{"buyer": user}, {"seller": user}]})
    return {"ok": True, "deleted_count": result.deleted_count}


@api.get("/health")
async def health():
    return {"status": "ok"}


app = socketio.ASGIApp(sio, other_asgi_app=api)

import os
import re
import httpx
from contextlib import asynccontextmanager

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ReturnDocument

from app.db import clothes, favorites
from app.models import (
    ClothingItem,
    ClothingItemCreate,
    FavoriteCreate,
    ItemStatus,
    StatusUpdate,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await clothes.create_index("_id")
    await favorites.create_index([("user", 1), ("item_id", 1)], unique=True)
    yield


app = FastAPI(title="Clothing Catalog service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_item(doc: dict) -> ClothingItem:
    data = {key: value for key, value in doc.items() if key != "_id"}
    data["id"] = str(doc["_id"])
    if "status" not in data:
        data["status"] = "Available"
    return ClothingItem(**data)


def parse_item_id(item_id: str) -> ObjectId:
    try:
        return ObjectId(item_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Clothing item not found")


async def find_item_or_404(item_id: str) -> dict:
    oid = parse_item_id(item_id)
    doc = await clothes.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Clothing item not found")
    return doc


def normalize_user(body: FavoriteCreate) -> str:
    for value in (
        body.user,
        body.username,
        body.buyer,
        body.buyerName,
        body.buyer_name,
    ):
        if value:
            return value
    # Fall back to any extra field that looks like a user.
    for key, value in (body.model_extra or {}).items():
        if "user" in key.lower() or "buyer" in key.lower():
            if value:
                return str(value)
    raise HTTPException(status_code=400, detail="user is required")


def normalize_item_id(body: FavoriteCreate) -> str:
    for value in (
        body.item_id,
        body.itemId,
        body.clothing_id,
        body.clothes_id,
        body.id,
    ):
        if value:
            return str(value)
    for key, value in (body.model_extra or {}).items():
        if "item" in key.lower() or "clothing" in key.lower() or "clothes" in key.lower() or key.lower() == "id":
            if value:
                return str(value)
    raise HTTPException(status_code=400, detail="item_id is required")


async def mark_item_sold(item_id: str) -> ClothingItem:
    oid = parse_item_id(item_id)
    doc = await clothes.find_one_and_update(
        {"_id": oid},
        {"$set": {"status": "Sold"}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Clothing item not found")
    return to_item(doc)


@app.post("/clothes", response_model=ClothingItem, status_code=201)
async def create_clothing(item: ClothingItemCreate):
    doc = item.model_dump()
    doc["status"] = "Available"
    result = await clothes.insert_one(doc)
    doc["_id"] = result.inserted_id
    return to_item(doc)


@app.get("/clothes", response_model=list[ClothingItem])
async def list_clothes(
    status: str | None = None,
    seller: str | None = None,
    q: str | None = None,
    name: str | None = None,
):
    query = {}
    if status:
        query["status"] = status
    if seller:
        query["seller"] = seller
    term = q or name
    if term and term.strip():
        query["name"] = re.compile(re.escape(term.strip()), re.IGNORECASE)
    docs = await clothes.find(query).sort([("_id", -1)]).to_list()
    return [to_item(doc) for doc in docs]


@app.get("/clothes/{item_id}", response_model=ClothingItem)
async def get_clothing(item_id: str):
    return to_item(await find_item_or_404(item_id))


@app.patch("/clothes/{item_id}", response_model=ClothingItem)
async def update_clothing(item_id: str, body: dict):
    doc = await find_item_or_404(item_id)
    updates = {}
    if "status" in body:
        updates["status"] = body["status"]
    for key in ("name", "price", "description", "seller", "category", "size", "condition"):
        if key in body:
            updates[key] = body[key]
    if updates:
        await clothes.update_one({"_id": doc["_id"]}, {"$set": updates})
    return to_item(await find_item_or_404(item_id))


@app.patch("/clothes/{item_id}/status", response_model=ClothingItem)
async def update_clothing_status(item_id: str, body: StatusUpdate | dict):
    status = body.get("status") if isinstance(body, dict) else body.status
    if status not in ("Available", "Sold"):
        raise HTTPException(status_code=400, detail="Invalid status")
    oid = parse_item_id(item_id)
    doc = await clothes.find_one_and_update(
        {"_id": oid},
        {"$set": {"status": status}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Clothing item not found")
    return to_item(doc)


@app.post("/clothes/{item_id}/sold", response_model=ClothingItem)
async def mark_clothing_sold(item_id: str):
    return await mark_item_sold(item_id)


@app.post("/clothes/{item_id}/purchase", response_model=ClothingItem)
async def mark_clothing_purchased(item_id: str):
    return await mark_item_sold(item_id)


@app.post("/clothes/{item_id}/mark-sold", response_model=ClothingItem)
async def mark_clothing_mark_sold(item_id: str):
    return await mark_item_sold(item_id)


@app.post("/favorites", response_model=ClothingItem, status_code=201)
async def add_favorite(body: FavoriteCreate):
    user = normalize_user(body)
    item_id = normalize_item_id(body)
    item_doc = await find_item_or_404(item_id)
    await favorites.update_one(
        {"user": user, "item_id": item_id},
        {"$set": {"user": user, "item_id": item_id}},
        upsert=True,
    )
    return to_item(item_doc)


@app.get("/favorites/{user}", response_model=list[ClothingItem])
async def list_favorites(user: str):
    favs = await favorites.find({"user": user}).to_list()
    item_ids = []
    for fav in favs:
        try:
            item_ids.append(ObjectId(fav["item_id"]))
        except InvalidId:
            continue
    if not item_ids:
        return []
    docs = await clothes.find({"_id": {"$in": item_ids}}).to_list()
    return [to_item(doc) for doc in docs]


@app.delete("/favorites/{user}/{item_id}", status_code=204)
async def remove_favorite(user: str, item_id: str):
    await favorites.delete_one({"user": user, "item_id": item_id})
    return None


NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8004")


@app.get("/favorites/item/{item_id}")
async def list_favorite_users(item_id: str):
    favs = await favorites.find({"item_id": item_id}).to_list()
    users = []
    for fav in favs:
        user = fav.get("user")
        if user and user not in users:
            users.append(user)
    return users


@app.delete("/clothes/{item_id}", status_code=204)
async def delete_clothing(item_id: str):
    oid = parse_item_id(item_id)
    doc = await clothes.find_one({"_id": oid})
    item_name = doc.get("name") if doc else None
    # Users who favorited this item (notify them before deletion).
    favs = await favorites.find({"item_id": item_id}).to_list()
    users = []
    for fav in favs:
        user = fav.get("user")
        if user and user not in users:
            users.append(user)
    await clothes.delete_one({"_id": oid})
    await favorites.delete_many({"item_id": item_id})
    # Notify favorites users (best effort)
    try:
        async with httpx.AsyncClient(base_url=NOTIFICATION_URL, timeout=5) as client:
            await client.post("/notifications/item-deleted", json={
                "item_id": item_id,
                "item_name": item_name,
                "users": users,
            })
    except Exception:
        pass
    return None

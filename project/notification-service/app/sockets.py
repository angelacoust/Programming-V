import re

import socketio

# Allowed rooms: "buyer-<user>", "seller-<user>" or "user-<user>".
ROOM_PATTERN = re.compile(r"(buyer|seller|user)-[A-Za-z0-9_.-]+")


# Socket.IO server for live updates. Each client joins its own room:
#   "buyer-<name>"   - the buyer's connection
#   "seller-<name>"  - the seller's connection
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


@sio.event
async def connect(sid, environ):
    # Allow identifying the user at connection time via query parameters.
    query = environ.get("QUERY_STRING", "")
    params = {}
    for part in query.split("&"):
        if "=" in part:
            key, value = part.split("=", 1)
            params[key] = value
    user = params.get("user") or params.get("username") or params.get("name")
    role = params.get("role", "buyer")
    if user:
        room = f"{role}-{user}" if role in ("buyer", "seller", "user") else f"user-{user}"
        if ROOM_PATTERN.fullmatch(room):
            await sio.enter_room(sid, room)
            print(f"Socket {sid} auto-joined {room}")
    print(f"Socket connected: {sid}")


@sio.event
async def join(sid, data):
    """Client sends {"room": "buyer-alice"} or {"room": "seller-bob"}."""
    room = data.get("room") if isinstance(data, dict) else None
    if not isinstance(room, str) or not ROOM_PATTERN.fullmatch(room):
        return {"ok": False, "error": "room must be 'buyer-<user>', 'seller-<user>' or 'user-<user>'"}
    await sio.enter_room(sid, room)
    print(f"Socket {sid} joined {room}")
    return {"ok": True, "room": room}


@sio.event
async def register(sid, data):
    """Client sends {"user": "alice", "role": "buyer"}."""
    if not isinstance(data, dict):
        return {"ok": False, "error": "data must be an object"}
    user = data.get("user") or data.get("username") or data.get("name")
    role = data.get("role", "buyer")
    if not user:
        return {"ok": False, "error": "user is required"}
    if role not in ("buyer", "seller", "user"):
        role = "user"
    room = f"{role}-{user}"
    if not ROOM_PATTERN.fullmatch(room):
        return {"ok": False, "error": "invalid room"}
    await sio.enter_room(sid, room)
    print(f"Socket {sid} registered as {room}")
    return {"ok": True, "room": room}


@sio.event
async def disconnect(sid):
    print(f"Socket disconnected: {sid}")

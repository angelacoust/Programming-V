import asyncio

from app.sockets import join, sio


def test_join_rooms():
    entered = []

    async def fake_enter_room(sid, room):
        entered.append(room)

    import unittest.mock as mock
    with mock.patch.object(sio, "enter_room", fake_enter_room):
        assert asyncio.run(join("sid", {"room": "buyer-alice"}))["ok"] is True
        assert asyncio.run(join("sid", {"room": "seller-bob"}))["ok"] is True
        assert asyncio.run(join("sid", {"room": "admin"}))["ok"] is False
    assert entered == ["buyer-alice", "seller-bob"]


def test_push_item_sold(client, emitted):
    payload = {"buyer": "carol", "seller": "bob", "item_id": "abc", "order_id": "ord1", "amount": 50}
    response = client.post("/notifications/item-sold", json=payload)
    assert response.status_code == 200
    # At least buyer and seller rooms received item-sold.
    rooms = [e[2] for e in emitted]
    assert "buyer-carol" in rooms
    assert "seller-bob" in rooms
    assert all(e[0] == "item-sold" for e in emitted)

def test_create_order(client):
    body = {"item_id": "abc", "buyer": "carol", "seller": "bob", "amount": 50}
    response = client.post("/orders", json=body)
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "Pending Payment"
    assert order["paid"] is False
    assert order["amount"] == 50
    assert client.get(f"/orders/{order['id']}").json()["id"] == order["id"]


def test_list_by_buyer(client):
    client.post("/orders", json={"item_id": "abc", "buyer": "carol", "seller": "bob", "amount": 50})
    client.post("/orders", json={"item_id": "def", "buyer": "dave", "seller": "bob", "amount": 10})
    carol = client.get("/orders/buyer/carol").json()
    assert len(carol) == 1
    assert carol[0]["buyer"] == "carol"


def test_mark_paid(client, downstream):
    order = client.post("/orders", json={"item_id": "abc", "buyer": "carol", "seller": "bob", "amount": 50}).json()
    response = client.post(f"/orders/{order['id']}/pay")
    assert response.status_code == 200
    assert response.json()["status"] == "Paid"
    assert response.json()["paid"] is True

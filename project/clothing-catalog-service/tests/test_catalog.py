def test_create_and_get_item(client):
    response = client.post("/clothes", json={"name": "Jeans", "price": 20, "seller": "alice"})
    assert response.status_code == 201
    item = response.json()
    assert item["status"] == "Available"
    assert client.get(f"/clothes/{item['id']}").json()["name"] == "Jeans"
    assert len(client.get("/clothes").json()) == 1


def test_favorites(client):
    item = client.post("/clothes", json={"name": "Dress", "price": 30, "seller": "bob"}).json()
    assert client.post("/favorites", json={"user": "carol", "item_id": item["id"]}).status_code == 201
    favs = client.get("/favorites/carol").json()
    assert len(favs) == 1
    assert favs[0]["id"] == item["id"]


def test_mark_sold(client):
    item = client.post("/clothes", json={"name": "Hat", "price": 15, "seller": "bob"}).json()
    response = client.post(f"/clothes/{item['id']}/sold")
    assert response.status_code == 200
    assert response.json()["status"] == "Sold"

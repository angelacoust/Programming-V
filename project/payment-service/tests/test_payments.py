def test_approved_payment(client, order_service):
    response = client.post("/payments", json={"orderId": "abc", "amount": 50, "cardNumber": "4111111111111111"})
    assert response.status_code == 200
    payment = response.json()
    assert payment["status"] == "Approved"
    assert payment["paid"] is True
    assert client.get(f"/payments/{payment['id']}").status_code == 200


def test_declined_payment(client, order_service):
    response = client.post("/payments", json={"orderId": "abc", "amount": 50, "cardNumber": "4000000000000000"})
    assert response.status_code == 200
    assert response.json()["status"] == "Declined"

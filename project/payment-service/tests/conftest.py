import os

import pytest
import respx
from pymongo import MongoClient

os.environ["PAYMENT_DB_NAME"] = "payment_db_test"

from fastapi.testclient import TestClient  # noqa: E402

from app.clients import ORDER_URL  # noqa: E402
from app.db import MONGO_URL  # noqa: E402
from app.main import app  # noqa: E402

mongo = MongoClient(MONGO_URL)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    mongo.drop_database("payment_db_test")


@pytest.fixture(autouse=True)
def clean_payments():
    mongo["payment_db_test"]["payments"].delete_many({})


@pytest.fixture
def order_service():
    with respx.mock(base_url=ORDER_URL, assert_all_called=False) as mock:
        mock.get(path__startswith="/orders/").respond(200, json={"id": "abc", "amount": 50, "buyer": "carol", "seller": "bob"})
        mock.post(path__startswith="/orders/").respond(200, json={"paid": True})
        mock.patch(path__startswith="/orders/").respond(200, json={"paid": True})
        yield mock

import os

import pytest
import respx
from pymongo import MongoClient

os.environ["ORDER_DB_NAME"] = "order_db_test"

from fastapi.testclient import TestClient  # noqa: E402

from app.clients import CATALOG_URL, NOTIFICATION_URL  # noqa: E402
from app.db import MONGO_URL  # noqa: E402
from app.main import app  # noqa: E402

mongo = MongoClient(MONGO_URL)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    mongo.drop_database("order_db_test")


@pytest.fixture(autouse=True)
def clean_orders():
    mongo["order_db_test"]["orders"].delete_many({})


@pytest.fixture
def downstream():
    with respx.mock(assert_all_called=False) as mock:
        mock.post(url__startswith=CATALOG_URL).respond(200, json={"status": "Sold"})
        mock.post(url__startswith=NOTIFICATION_URL).respond(200, json={"ok": True})
        yield mock

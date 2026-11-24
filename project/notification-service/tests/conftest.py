import os

import pytest
from pymongo import MongoClient

os.environ["NOTIFICATION_DB_NAME"] = "notification_db_test"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import MONGO_URL  # noqa: E402
from app.main import app  # noqa: E402
from app.sockets import sio  # noqa: E402

mongo = MongoClient(MONGO_URL)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    mongo.drop_database("notification_db_test")


@pytest.fixture(autouse=True)
def clean():
    mongo["notification_db_test"]["notifications"].delete_many({})


@pytest.fixture
def emitted(monkeypatch):
    events = []

    async def fake_emit(event, data, room=None):
        events.append((event, data, room))

    monkeypatch.setattr(sio, "emit", fake_emit)
    return events

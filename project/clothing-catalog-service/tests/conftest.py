import os

import pytest
from pymongo import MongoClient

os.environ["CATALOG_DB_NAME"] = "catalog_db_test"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import MONGO_URL  # noqa: E402
from app.main import app  # noqa: E402

mongo = MongoClient(MONGO_URL)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    mongo.drop_database("catalog_db_test")


@pytest.fixture(autouse=True)
def clean():
    mongo["catalog_db_test"]["clothes"].delete_many({})
    mongo["catalog_db_test"]["favorites"].delete_many({})

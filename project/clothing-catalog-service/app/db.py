import os

from pymongo import AsyncMongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("CATALOG_DB_NAME", "catalog_db")

client = AsyncMongoClient(MONGO_URL)
db = client[DB_NAME]
clothes = db["clothes"]
favorites = db["favorites"]

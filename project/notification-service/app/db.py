import os

from pymongo import AsyncMongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("NOTIFICATION_DB_NAME", "notification_db")

client = AsyncMongoClient(MONGO_URL)
db = client[DB_NAME]
notifications = db["notifications"]

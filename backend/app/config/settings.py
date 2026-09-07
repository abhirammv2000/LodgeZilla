"""Application settings, resolved from environment variables.

Nothing here carries a usable default for a secret: `MONGO_URI` falls back to a
local mongod and `JWT_SECRET_KEY` to a development-only string, so a real
deployment must set both explicitly.
"""
import json
import logging
import os

_CONFIG_DIR = os.path.dirname(__file__)

# Collection/database names live in mongo_config.json so the ingest script and
# the API cannot drift apart.
with open(os.path.join(_CONFIG_DIR, "mongo_config.json")) as _f:
    _mongo_config = json.load(_f)

DATABASE_NAME = _mongo_config["database_name"]
LISTING_COLLECTION_NAME = _mongo_config["listing_collection_name"]
USER_COLLECTION_NAME = _mongo_config["user_collection_name"]

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_KEY = os.getenv("REDIS_KEY", "toWorkers")

# Comma-separated list of origins allowed to call the API from a browser.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost,http://localhost:3000,http://lodgezilla.com"
    ).split(",")
    if origin.strip()
]

LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
# Unset LOG_FILE to log to stdout, which is what you want under Kubernetes.
LOG_FILE = os.getenv("LOG_FILE") or None

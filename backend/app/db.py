"""Shared MongoDB and Redis clients.

Both drivers pool connections internally, so the module-level clients here are
created once per process and imported by the routes rather than reopened in
each one.
"""
import logging

import pymongo
import redis

from .config import settings

mongo_client = pymongo.MongoClient(settings.MONGO_URI)
_database = mongo_client[settings.DATABASE_NAME]

listing_collection = _database[settings.LISTING_COLLECTION_NAME]
user_collection = _database[settings.USER_COLLECTION_NAME]

listing_collection.create_index([("property_id", pymongo.ASCENDING)])
user_collection.create_index([("user_id", pymongo.ASCENDING)])

redis_client = redis.StrictRedis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0
)


def push_to_redis(msg, key=settings.REDIS_KEY):
    """Publish an activity message onto the worker queue.

    The queue is a side channel for activity logging, so an unreachable Redis
    must not fail the request that triggered it.
    """
    try:
        redis_client.lpush(key, str(msg))
    except redis.RedisError:
        logging.getLogger(__name__).warning("could not publish to Redis", exc_info=True)


def read_from_redis(key=settings.REDIS_KEY):
    """Block on the worker queue, logging each message. Runs until interrupted."""
    logger = logging.getLogger(__name__)
    while True:
        message = redis_client.blpop(key)
        logger.info(message)

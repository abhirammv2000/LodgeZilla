"""Worker that drains the activity queue.

Run from the `backend/` directory:  python -m app.util.consume_redis
"""
from ..db import read_from_redis
from .utils import configure_logging

if __name__ == "__main__":
    configure_logging()
    read_from_redis()

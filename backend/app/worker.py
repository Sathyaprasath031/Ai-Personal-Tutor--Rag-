"""RQ worker entry point.

Run with: python -m app.worker
"""
import logging

from redis import Redis
from rq import Worker, Queue

from .config import settings
from .db import pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_worker():
    logger.info("Starting RQ worker for 'ingest' queue")
    pool.open()
    conn = Redis.from_url(settings.redis_url)
    queues = [Queue("ingest", connection=conn)]
    worker = Worker(queues, connection=conn)
    worker.work()


if __name__ == "__main__":
    run_worker()

"""
Start with: python -m app.worker.run_worker
(Or via Docker Compose 'worker' service — see docker-compose.yml)
"""
import logging

from redis import Redis
from rq import SimpleWorker, Queue

from app.config import get_settings

logging.basicConfig(level=logging.INFO)
settings = get_settings()

if __name__ == "__main__":
    redis_conn = Redis.from_url(settings.REDIS_URL)
    queue = Queue("adpilot", connection=redis_conn)
    worker = SimpleWorker([queue], connection=redis_conn)
    worker.work()

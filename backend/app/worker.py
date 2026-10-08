import logging
import os
import signal
import socket
import time

from app.classification.predictor import Predictor
from app.config import settings
from app.domain.models import Event
from app.ingestion.queue import GROUPS, Queue
from app.storage.repository import Repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
running = True


def stop(*_):
    global running
    running = False


def knowledge_ready(repository, queue, entry_id, event):
    if repository.event(event.id) is not None:
        return True
    if queue.status(event.id).get("classification") == "failed":
        queue.finish("knowledge", entry_id, event.id, "failed")
    # Leave pending for reclaim; waiting for classification is not a processing failure.
    return False


def main():
    group = os.getenv("WORKER_GROUP", "classification")
    if group not in GROUPS:
        raise ValueError("Unknown worker group")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    repository = Repository(settings)
    queue = Queue(settings.redis_uri)
    queue.initialize()
    predictor = (
        Predictor(settings.model_path, settings.review_threshold)
        if group == "classification"
        else None
    )
    try:
        while running:
            try:
                queue.redis.set("logsense:worker:" + group, "alive", ex=90)
                entries = queue.next(group, socket.gethostname())
                for entry_id, fields in entries:
                    event = Event.model_validate_json(fields["event"])
                    try:
                        if group == "classification":
                            repository.save_event(event, predictor.predict(event))
                        else:
                            if not knowledge_ready(repository, queue, entry_id, event):
                                continue
                            repository.observe(event)
                        queue.finish(group, entry_id, event.id)
                    except Exception:
                        logging.getLogger(__name__).exception(
                            "%s failed for event %s", group, event.id
                        )
                        queue.fail(group, entry_id, event.id, fields["event"])
            except Exception:
                logging.getLogger(__name__).exception("Worker connection or envelope failure")
                time.sleep(3)
    finally:
        repository.close()


if __name__ == "__main__":
    main()

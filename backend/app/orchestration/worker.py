import fcntl
import logging
import threading
from sqlalchemy import select
from app.database.models import Run

log = logging.getLogger("forgeops.worker")


class Worker:
    def __init__(self, engine):
        self.engine = engine
        self.stop_event = threading.Event()
        self.thread = None
        self.lock_file = None

    def start(self):
        lock_path = self.engine.settings.runtime_dir / "worker.lock"
        self.lock_file = lock_path.open("w")
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock_file.close()
            raise RuntimeError("A worker already owns this runtime directory; use one API process")
        self.engine.recover()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="forgeops-worker")
        self.thread.start()

    def loop(self):
        while not self.stop_event.is_set():
            try:
                with self.engine.sessions() as db:
                    next_id = db.scalar(
                        select(Run.id).where(Run.status == "CREATED").order_by(Run.created_at).limit(1)
                    )
                if next_id:
                    self.engine.execute(next_id)
                    continue
            except Exception:
                log.exception("Worker iteration failed")
            self.stop_event.wait(self.engine.settings.worker_poll_seconds)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        if self.lock_file and (not self.thread or not self.thread.is_alive()):
            self.lock_file.close()

"""Single-instance background worker for scheduled ECOSHIELD campaigns.

Run as a separate process alongside the Flask web service:
    python scheduler_worker.py

The worker shares the application's SQLite database and activates due
campaigns without requiring an administrator to open the dashboard.
"""
import logging
import os
import signal
import time

from web_dashboard import get_db_connection, initialize_database, ensure_seed_data
from assessment_engine import activate_due_campaigns

POLL_SECONDS = max(5, int(os.environ.get("ECOSHIELD_SCHEDULER_INTERVAL", "15")))
LOCK_PATH = os.environ.get("ECOSHIELD_SCHEDULER_LOCK", "/tmp/ecoshield-scheduler.lock")
running = True


def stop_worker(_signum, _frame):
    global running
    running = False


def main():
    global running
    logging.basicConfig(
        level=os.environ.get("ECOSHIELD_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)

    lock_file = open(LOCK_PATH, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            lock_file.seek(0)
            if not lock_file.read(1):
                lock_file.write("0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        logging.error("Another ECOSHIELD scheduler worker already holds the lock.")
        return 2

    initialize_database()
    ensure_seed_data()
    logging.info("ECOSHIELD campaign scheduler started; polling every %s seconds.", POLL_SECONDS)

    while running:
        conn = get_db_connection()
        try:
            activated = activate_due_campaigns(conn)
            if activated:
                logging.info("Activated %s due campaign(s).", activated)
        except Exception:
            conn.rollback()
            logging.exception("Campaign activation failed; it will be retried on the next poll.")
        finally:
            conn.close()
        for _ in range(POLL_SECONDS):
            if not running:
                break
            time.sleep(1)

    logging.info("ECOSHIELD campaign scheduler stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

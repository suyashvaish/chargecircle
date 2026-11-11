"""Sends upcoming-booking reminder emails. Safe to run repeatedly (de-duplicated per booking and user).
Run from the backend directory, e.g. every 15 minutes via cron:
    cd backend && python ../scripts/run_reminders.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.services.marketplace_service import expire_stale_holds  # noqa: E402
from app.services.notification_service import send_due_reminders  # noqa: E402

if __name__ == "__main__":
    with SessionLocal() as db:
        released = expire_stale_holds(db)
        sent = send_due_reminders(db)
    print(f"released {released} expired payment holds; sent {sent} reminder emails")

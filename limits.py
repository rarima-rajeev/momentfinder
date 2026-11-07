"""Site-wide daily search cap, kept in a small file so it survives restarts."""
import datetime
import json
import threading
from pathlib import Path

USAGE_FILE = Path(__file__).parent / ".usage.json"
_lock = threading.Lock()


def take_daily_slot(limit, path=USAGE_FILE):
    """Count one search against today's budget. False when the day's limit is used up."""
    today = datetime.date.today().isoformat()
    with _lock:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        if data.get("date") != today:
            data = {"date": today, "count": 0}
        if data["count"] >= limit:
            return False
        data["count"] += 1
        path.write_text(json.dumps(data))
        return True

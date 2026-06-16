"""
求助事件存储 — 许小熊检测到负面情绪或回答困难时保存事件
"""
import json
import os
import uuid
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))  # 北京时间

def _now():
    return datetime.now(CST)

ALERTS_FILE = "alerts.json"


def _load():
    if not os.path.exists(ALERTS_FILE):
        return {"alerts": []}
    with open(ALERTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_alert(alert_type, trigger_message, bot_reply, context=None):
    data = _load()
    alert = {
        "id": uuid.uuid4().hex[:8],
        "type": alert_type,
        "timestamp": _now().strftime("%Y-%m-%d %H:%M:%S"),
        "trigger_message": trigger_message,
        "bot_reply": bot_reply,
        "context": context or {},
        "read": False,
    }
    data["alerts"].insert(0, alert)
    if len(data["alerts"]) > 50:
        data["alerts"] = data["alerts"][:50]
    _save(data)
    return alert


def get_alerts(limit=20, unread_only=False):
    data = _load()
    alerts = data["alerts"]
    if unread_only:
        alerts = [a for a in alerts if not a["read"]]
    return alerts[:limit]


def mark_read(alert_id):
    data = _load()
    for a in data["alerts"]:
        if a["id"] == alert_id:
            a["read"] = True
    _save(data)


def mark_all_read():
    data = _load()
    for a in data["alerts"]:
        a["read"] = True
    _save(data)


def get_unread_count():
    data = _load()
    return sum(1 for a in data["alerts"] if not a["read"])

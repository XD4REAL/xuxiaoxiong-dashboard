import json
import os
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

def _now_str():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M")

MEMORY_DIR = "chat_histories"

def _ensure_dir():
    if not os.path.exists(MEMORY_DIR):
        os.makedirs(MEMORY_DIR)

def _file_path(user_id):
    return os.path.join(MEMORY_DIR, f"{user_id}.json")

def load_history(user_id):
    """加载指定用户的对话历史"""
    path = _file_path(user_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

MAX_HISTORY = 200


def add_message(user_id, role, content):
    """添加一条消息，超过上限自动裁剪旧消息"""
    history = load_history(user_id)
    history.append({"role": role, "content": content, "time": _now_str()})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    _ensure_dir()
    with open(_file_path(user_id), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def clear_history(user_id):
    """清空指定用户的对话历史"""
    path = _file_path(user_id)
    if os.path.exists(path):
        os.remove(path)


def cleanup_old_histories(days: int = 30):
    """删除超过指定天数未修改的聊天记录文件"""
    import time
    if not os.path.exists(MEMORY_DIR):
        return
    cutoff = time.time() - days * 86400
    for filename in os.listdir(MEMORY_DIR):
        filepath = os.path.join(MEMORY_DIR, filename)
        if os.path.isfile(filepath) and filename.endswith(".json"):
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)


def get_dates_with_history(user_id: str) -> list[str]:
    """返回有聊天记录的日期列表（倒序）"""
    history = load_history(user_id)
    dates = set()
    for msg in history:
        t = msg.get("time", "")
        if t and len(t) >= 10:
            dates.add(t[:10])
    return sorted(dates, reverse=True)


def get_messages_by_date(user_id: str, date_str: str) -> list[dict]:
    """返回指定日期的所有消息"""
    history = load_history(user_id)
    return [msg for msg in history if msg.get("time", "").startswith(date_str)]
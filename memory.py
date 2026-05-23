import json
import os

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
    history.append({"role": role, "content": content})
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
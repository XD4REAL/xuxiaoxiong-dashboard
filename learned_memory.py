"""
持久化记忆系统 — 让许小熊能跨对话记住东西 OvO
"""

import json
import os
import re

MEMORY_FILE = "learned_memory.json"
MAX_FACTS = 50


def _load() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return {"facts": []}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"facts": []}


def _save(data: dict):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_fact(fact: str, value: str, source: str = "auto"):
    """添加或更新一条事实记忆"""
    data = _load()
    for existing in data["facts"]:
        if existing["fact"] == fact:
            existing["value"] = value
            existing["source"] = source
            _save(data)
            return
    data["facts"].append({
        "fact": fact,
        "value": value,
        "source": source,
    })
    if len(data["facts"]) > MAX_FACTS:
        data["facts"] = data["facts"][-MAX_FACTS:]
    _save(data)


def get_all_facts() -> list[dict]:
    """获取所有记住的事实"""
    data = _load()
    return data["facts"]


def detect_and_save_corrections(user_message: str) -> bool:
    """
    从用户消息中检测纠正/教导行为，自动保存记忆

    匹配模式：
    - "不对，xxx是yyy"
    - "不是xxx，是yyy"
    - "你记错了，xxx是yyy"
    - "记住：xxx是yyy"
    """
    msg = user_message.strip()

    # 模式1：显示记住指令 — "记住：xxx是yyy"
    remember_match = re.search(r"记住[：:]\s*(\S+?)是(\S+)", msg)
    if remember_match:
        add_fact(remember_match.group(1), remember_match.group(2), source="user_command")
        return True

    # 模式2：纠正 — "不对/不是/记错了/记混了，xxx是yyy"
    correction_match = re.search(
        r"(不对|不是|错了|记错了|记混了)[，,。.\s](.?)(?:是|为)(\S+)",
        msg
    )
    if correction_match:
        fact = correction_match.group(2).strip()
        value = correction_match.group(3).strip()
        if fact and value and len(fact) < 30 and len(value) < 50:
            add_fact(fact, value, source="correction")
            return True

    return False


def build_memory_context() -> str:
    """生成记忆上下文，注入到系统提示词"""
    facts = get_all_facts()
    if not facts:
        return ""

    lines = ["\n【我记住的事情（用户纠正过/教过我的）】"]
    for f in facts:
        lines.append(f"- {f['fact']}：{f['value']}")
    lines.append("（以上是用户纠正过我的内容，回答时以这些为准）")
    return "\n".join(lines)
"""
持久化记忆系统 — 让许小熊能跨对话记住东西 OvO
"""

import json
import os
import re

MEMORY_FILE = "learned_memory.json"
MAX_FACTS = 200


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
        if existing["value"] == value:
            # 值相同但事实名不同 → 跳过，避免重复
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


# fact 名不能是这些分类标签（太泛，不是具体事实）
_GENERIC_FACT_PATTERNS = [
    "共同回忆", "共同喜好", "共同爱好",
    "纠正错误", "记错了", "记混了",
    "许小熊的设定", "小豆纠正", "小多的", "小豆的",
    "日常习惯", "性格特点", "功能说明",
    "注意事项", "规则说明",
]


def _is_generic_fact_name(fact: str) -> bool:
    """检查 fact 名是否是分类标签而非具体事实"""
    for pattern in _GENERIC_FACT_PATTERNS:
        if pattern in fact:
            return True
    # 太短的通常是标签
    if len(fact) <= 2:
        return True
    # 以"的"结尾的通常是分类（如"小豆的喜好"）
    if fact.endswith("的") and len(fact) <= 5:
        return True
    return False


def _is_near_duplicate(value: str, existing_facts: list[dict]) -> bool:
    """检查 value 是否与已有记忆高度重合（避免换说法绕过去重）"""
    for f in existing_facts:
        ev = f.get("value", "")
        # 子串包含
        if len(value) >= 4 and len(ev) >= 4:
            if value in ev or ev in value:
                return True
        # 字符重叠率 > 70%
        if len(value) > 4 and len(ev) > 4:
            common = len(set(value) & set(ev))
            overlap = common / max(len(value), len(ev))
            if overlap > 0.7:
                return True
    return False


def save_llm_memories(memories: list[dict]):
    """保存 LLM 从对话中提取的记忆（自然语言触发，无需口令）

    过滤规则：
    - fact 名不能是通用分类标签
    - value 不能与已有记忆高度重复
    - 长度限制
    """
    if not memories:
        return
    existing = get_all_facts()
    for m in memories:
        fact = m.get("f", "").strip()
        value = m.get("v", "").strip()
        # 基本长度检查
        if not fact or not value:
            continue
        if len(fact) < 3 or len(fact) > 20:
            continue
        if len(value) < 4 or len(value) > 60:
            continue
        # 拒绝分类标签
        if _is_generic_fact_name(fact):
            continue
        # 拒绝近重复
        if _is_near_duplicate(value, existing):
            continue
        add_fact(fact, value, source="llm_extract")
        existing.append({"fact": fact, "value": value})


def detect_and_save_corrections(user_message: str) -> bool:
    """
    从用户消息中检测纠正/教导行为，自动保存记忆（正则兜底）

    匹配模式：
    - "记住：xxx是yyy"
    - "记住，xxx是yyy"
    - "不对，xxx是yyy"
    - "不是xxx，是yyy"
    - "你记错了，xxx是yyy"
    """
    msg = user_message.strip()

    # 模式1：显示记住指令 — "记住：xxx是yyy" 或 "记住，xxx是yyy"
    remember_match = re.search(r"记住[：:，,]\s*(\S+?)是(\S+)", msg)
    if remember_match:
        add_fact(remember_match.group(1), remember_match.group(2), source="user_command")
        return True

    # 模式2：纠正 — "不对/不是/记错了/记混了，xxx是yyy"
    correction_match = re.search(
        r"(不对|不是|错了|记错了|记混了)[，,。.\s](.+?)(?:是|为)(\S+)",
        msg
    )
    if correction_match:
        fact = correction_match.group(2).strip()
        value = correction_match.group(3).strip()
        if fact and value and len(fact) < 30 and len(value) < 50:
            add_fact(fact, value, source="correction")
            return True

    return False


def build_memory_context(user_message: str = "", max_facts: int = 8) -> str:
    """生成记忆上下文，注入到系统提示词。有 user_message 时只返回相关的记忆。"""
    facts = get_all_facts()
    if not facts:
        return ""

    if not user_message:
        # 无用户消息时返回最近 max_facts 条
        selected = facts[-max_facts:]
    else:
        # 关键词匹配：从用户消息中提取有效关键词
        stop_words = {
            "你", "我", "他", "她", "它", "们", "是", "的", "了", "吗", "呢", "吧",
            "啊", "哦", "嗯", "哈", "呀", "啦", "嘛", "不", "就", "也", "都", "还",
            "要", "有", "会", "能", "什么", "怎么", "为什么", "哪里", "哪", "谁",
            "在", "和", "与", "跟", "对", "把", "被", "让", "给", "到", "去", "来",
            "说", "想", "知道", "觉得", "记得", "告诉", "这个", "那个", "可以",
            "一个", "一些", "一下", "今天", "现在", "真的", "好", "很", "太",
        }
        # 简单分词：按常见分隔符拆
        import re
        words = re.split(r"[，,。\.！!？?\s]+", user_message)
        keywords = [w.strip() for w in words if len(w.strip()) >= 2 and w.strip() not in stop_words]

        if not keywords:
            selected = facts[-max_facts:]
        else:
            # 对每条事实打分
            scored = []
            for f in facts:
                text = f["fact"] + f["value"]
                score = 0
                for kw in keywords:
                    if kw in text:
                        score += 1
                    # 部分匹配（>=2字的子串）
                    if len(kw) >= 2:
                        for i in range(len(kw) - 1):
                            sub = kw[i:i+2]
                            if sub in text:
                                score += 0.3
                if score > 0:
                    scored.append((score, f))
            scored.sort(key=lambda x: x[0], reverse=True)
            selected = [f for _, f in scored[:max_facts]]
            if not selected:
                selected = facts[-3:]

    lines = ["\n【我记住的事情（与小豆的当前话题相关）】"]
    for f in selected:
        lines.append(f"- {f['fact']}：{f['value']}")
    if not user_message:
        lines.append("（以上是小豆纠正/教过我的内容。如果和系统提示词有矛盾以这里为准，内部有矛盾以排后面的为准。）")
    return "\n".join(lines)
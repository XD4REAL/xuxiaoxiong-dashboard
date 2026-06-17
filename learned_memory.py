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
        "activation": 0,
        "last_accessed": None,
    })
    if len(data["facts"]) > MAX_FACTS:
        data["facts"] = data["facts"][-MAX_FACTS:]
    _save(data)


def get_all_facts() -> list[dict]:
    """获取所有记住的事实"""
    data = _load()
    return data["facts"]


# fact 名中不能出现这些泛化词（说明 LLM 在用分类标签而非具体事实名）
_GENERIC_KEYWORDS = [
    "共同", "纠正", "记错", "记混", "喜好", "爱好", "习惯",
    "性格", "特点", "功能", "说明", "规则", "设定",
    "日常", "备忘", "注意", "最爱", "最喜欢",
    "回忆", "记录", "记忆",
]


def _is_generic_fact_name(fact: str) -> bool:
    """检查 fact 名是否是分类标签/描述性短语，而非具体事实名

    好例子：哈尔滨雪翅膀、棋士节谐音、许小熊日
    坏例子：小豆喜欢的颜色、小豆和小多共同回忆、小豆纠正错误
    """
    # 1. 包含泛化关键词 → 是分类标签
    for kw in _GENERIC_KEYWORDS:
        if kw in fact:
            return True
    # 2. "XX的XX" 结构 → 描述性短语，不是事实名
    #    但允许 "的" 在开头/结尾的少量情况
    de_pos = fact.find("的")
    if de_pos > 0 and de_pos < len(fact) - 1:
        # "的"在中间 → 描述性短语（"小豆喜欢的颜色"）
        return True
    if fact.endswith("的"):
        return True
    # 3. 太短
    if len(fact) <= 2:
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
        if len(fact) < 3 or len(fact) > 12:
            continue
        if len(value) < 2 or len(value) > 60:
            continue
        # LLM 偷懒：直接复制 value 作为 fact
        if fact == value:
            continue
        # fact 中包含 value → 说明是描述性短语而非命名实体
        if len(value) >= 4 and value in fact:
            continue
        # 拒绝分类标签/描述性短语
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

    # 模式1：显示记住指令 — "记住...xxx是yyy"（允许中间有任意文字）
    remember_match = re.search(r"记住.*?[：:，,]\s*(\S+?)是(\S+)", msg)
    if remember_match:
        add_fact(remember_match.group(1), remember_match.group(2), source="user_command")
        return True

    # 模式2：纠正 — "不对/不是/记错了/记混了...xxx是yyy"（允许中间有语气词）
    correction_match = re.search(
        r"(不对|不是|错了|记错了|记混了).*?[，,。.\s](.+?)(?:是|为)(\S+)",
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
            # 对每条事实打分（关键词 + activation - 时间衰减）
            from datetime import date as _date
            today_str = _date.today().isoformat()
            scored = []
            for f in facts:
                text = f["fact"] + f["value"]
                kw_score = 0
                for kw in keywords:
                    if kw in text:
                        kw_score += 1
                    if len(kw) >= 2:
                        for i in range(len(kw) - 1):
                            sub = kw[i:i+2]
                            if sub in text:
                                kw_score += 0.3

                # activation 加成
                act = f.get("activation", 0) or 0
                act_bonus = act * 0.3

                # 时间衰减
                last = f.get("last_accessed")
                days_since = 0
                if last:
                    try:
                        delta = _date.today() - _date.fromisoformat(last)
                        days_since = delta.days
                    except (ValueError, TypeError):
                        pass
                decay = days_since * 0.01

                total = kw_score + act_bonus - decay
                if total > 0:
                    scored.append((total, f, kw_score > 0))

            scored.sort(key=lambda x: x[0], reverse=True)
            selected = []
            accessed_ids = []
            for _, f, was_matched in scored[:max_facts]:
                selected.append(f)
                if was_matched:
                    accessed_ids.append(f["fact"])

            # 回写 activation：匹配到的 +1，更新 last_accessed
            if accessed_ids:
                for f in facts:
                    if f["fact"] in accessed_ids:
                        f["activation"] = min((f.get("activation", 0) or 0) + 1, 50)
                        f["last_accessed"] = today_str
                data = _load()
                for existing in data["facts"]:
                    for updated in facts:
                        if existing["fact"] == updated["fact"]:
                            existing["activation"] = updated.get("activation", 0)
                            existing["last_accessed"] = updated.get("last_accessed")
                _save(data)

            if not selected:
                selected = facts[-3:]

            # === 分层注入：L0 热记忆（固定） + L1 话题记忆（按需） ===
            L0_MAX = 3
            L1_MAX = 5

            # L0：activation >= 3 的热记忆，按 activation 降序
            hot = [f for f in facts if (f.get("activation", 0) or 0) >= 3]
            hot.sort(key=lambda f: f.get("activation", 0), reverse=True)
            l0_facts = hot[:L0_MAX]

            # L1：关键词匹配到的，排除已在 L0 中的
            l0_names = {f["fact"] for f in l0_facts}
            l1_facts = [f for f in selected if f["fact"] not in l0_names][:L1_MAX]

            lines = []
            if l0_facts:
                lines.append("\n【核心记忆（始终记住）】")
                for f in l0_facts:
                    lines.append(f"- {f['fact']}：{f['value']}")
            if l1_facts:
                lines.append("\n【相关记忆（当前话题）】")
                for f in l1_facts:
                    lines.append(f"- {f['fact']}：{f['value']}")
            if not lines:
                lines.append("\n【相关记忆】")

    # 无 user_message 时用旧格式
    if not user_message:
        lines = ["\n【我记住的事情（与小豆的当前话题相关）】"]
        for f in selected:
            lines.append(f"- {f['fact']}：{f['value']}")
        lines.append("（以上是小豆纠正/教过我的内容。如果和系统提示词有矛盾以这里为准，内部有矛盾以排后面的为准。）")
    return "\n".join(lines)
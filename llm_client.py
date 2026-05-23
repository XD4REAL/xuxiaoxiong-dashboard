
"""DeepSeek API 调用模块"""

import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL
from persona import SYSTEM_PROMPT, EXTENDED_KNOWLEDGE, get_today_info


def build_messages(history: list[dict], user_message: str) -> list[dict]:
    """构建发送给 DeepSeek 的消息列表"""

    today_info = get_today_info()

    # 构建包含日期和纪念日的上下文
    date_context = f"【当前日期】{today_info['today_cn']}\n"

    if today_info["today_events"]:
        date_context += "【今天的特殊日子】\n"
        for ev in today_info["today_events"]:
            date_context += f"- {ev['name']}（已过去{ev['days_since']}天）"
            if ev.get("event"):
                date_context += f"：{ev['event']}"
            if ev.get("phrase"):
                date_context += f" 相关句子：{ev['phrase']}"
            date_context += "\n"

    if today_info["upcoming_events"]:
        date_context += "【即将到来的纪念日】\n"
        for ev in today_info["upcoming_events"]:
            date_context += f"- {ev['date']}是{ev['name']}（还有{ev['days_until']}天）"
            if ev.get("event"):
                date_context += f"：{ev['event']}"
            date_context += "\n"

    # 构建系统消息（注入日期上下文 + 持久化记忆）
    from learned_memory import build_memory_context
    memory_context = build_memory_context()
    system_content = SYSTEM_PROMPT + "\n\n" + date_context
    if memory_context:
        system_content += "\n\n" + memory_context

    # 如果用户消息包含"纪念日"、"记得"等关键词，额外注入知识
    if any(kw in user_message for kw in ["纪念日", "还记得", "还记得吗", "我们", "记不记得"]):
        knowledge_section = "\n\n【你的专属记忆库】\n"
        from persona import ANNIVERSARIES
        for ann in ANNIVERSARIES:
            knowledge_section += f"- {ann['name']}: {ann['date']}"
            if ann.get("event"):
                knowledge_section += f"（{ann['event']}）"
            knowledge_section += "\n"
        system_content += knowledge_section

    # 构建消息列表
    messages = [{"role": "system", "content": system_content}]

    # 添加历史消息（最多保留最近10轮对话）
    for h in history[-10:]:
        messages.append(h)

    # 添加当前用户消息
    messages.append({"role": "user", "content": user_message})

    return messages


def chat(history: list[dict], user_message: str) -> str:
    """调用 DeepSeek API 生成回复"""
    messages = build_messages(history, user_message)

    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 512,
            "top_p": 0.95,
        },
        timeout=30,
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"]


UNCERTAIN_KEYWORDS = [
    "不太清楚", "不确定", "不知道", "问小多吧", "问问小多",
    "我不太懂", "没太明白", "这个我不太会", "我也不清楚",
    "说不准", "不太好说", "我不好说", "这个我回答不了",
    "换个话题", "不太明白", "没听懂", "还没有教", "还没学",
    "没学过", "还不懂", "不太会", "没教过", "没学会",
    "我不了解", "我不太了解", "不太知道",
]


def _keyword_check(reply: str) -> bool:
    """True 表示检测到不确定"""
    for kw in UNCERTAIN_KEYWORDS:
        if kw in reply:
            return True
    return False


def _llm_confidence_check(reply: str, user_message: str) -> bool:
    """让 LLM 自评回答是否有把握。True 表示没把握"""
    try:
        prompt = (
            "评估下面这个回复是否真的\"有把握\"回答了用户的问题。\n\n"
            f"用户消息：{user_message}\n"
            f"回复：{reply}\n\n"
            "如果回复表现出不确定、回避问题、或建议问别人，回答\"没把握\"。"
            "如果回复清晰明确地回答了问题，回答\"有把握\"。"
            "只回答这两个词之一。"
        )
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 16,
            },
            timeout=15,
        )
        data = resp.json()
        result = data["choices"][0]["message"]["content"].strip()
        return "没把握" in result
    except Exception as e:
        print(f"[confidence check] LLM 自评失败: {e}")
        return False


def assess_confidence(reply: str, user_message: str) -> bool:
    """检测回复是否缺乏信心。True 表示不确定/没把握"""
    if _keyword_check(reply):
        return True
    return _llm_confidence_check(reply, user_message)
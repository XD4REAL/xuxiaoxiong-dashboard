
"""DeepSeek API 调用模块"""

import json
import re
import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL
from persona import SYSTEM_PROMPT, EXTENDED_KNOWLEDGE, get_today_info


def build_messages(history: list[dict], user_message: str) -> list[dict]:
    """构建发送给 DeepSeek 的消息列表"""

    today_info = get_today_info()

    # 构建包含日期和纪念日的上下文
    date_context = f"【当前日期和时间（北京时间）】{today_info['today_cn']}\n"

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

    # 附加分析任务指令（模型会在回复末尾输出结构化分析，程序自动移除）
    analysis_instruction = (
        "\n\n【分析任务】每条回复结尾附加一行JSON："
        '{"_a":{"e":"positive/neutral/negative","c":"high/low","t":["话题1","话题2"]}}'
        "\nemotion分析用户情绪，confidence评估你的回答把握度，topics提取2-4个话题关键词。"
    )
    system_content += analysis_instruction

    # 构建消息列表
    messages = [{"role": "system", "content": system_content}]

    # 添加历史消息（最多保留最近10轮对话）
    for h in history[-10:]:
        messages.append(h)

    # 添加当前用户消息
    messages.append({"role": "user", "content": user_message})

    return messages


def _post_with_retry(url, headers, json, timeout, max_retries=1):
    """带重试的 POST 请求，超时/5xx/连接错误时重试一次"""
    for attempt in range(max_retries + 1):
        resp = requests.post(url, headers=headers, json=json, timeout=timeout)
        if resp.status_code < 500:
            return resp
        if attempt < max_retries:
            import time
            time.sleep(1)
    return resp


def _parse_analysis(raw: str) -> tuple[str, dict | None, list | None]:
    """从回复文本中提取分析数据和记忆，返回 (纯净回复, 分析dict或None, 记忆list或None)"""
    start = raw.rfind('{"_a":')
    if start < 0:
        return raw, None, None

    brace_count = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == '{':
            brace_count += 1
        elif raw[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i
                break

    if end < 0:
        return raw, None, None

    json_str = raw[start:end + 1]
    full_reply = (raw[:start] + raw[end + 1:]).strip()

    try:
        data = json.loads(json_str)
        inner = data["_a"]
        analysis = {
            "emotion": inner.get("e", "neutral"),
            "confidence": inner.get("c", "high"),
            "topics": inner.get("t", ["日常"]),
        }
        if analysis["emotion"] not in ("positive", "neutral", "negative"):
            analysis["emotion"] = "neutral"
        if analysis["confidence"] not in ("high", "low"):
            analysis["confidence"] = "high"
        if not isinstance(analysis["topics"], list):
            analysis["topics"] = ["日常"]

        memories = data.get("_m", None)
        if memories and isinstance(memories, list):
            memories = [m for m in memories if isinstance(m, dict) and m.get("f") and m.get("v")]
            if not memories:
                memories = None

        return full_reply, analysis, memories
    except Exception:
        pass
    return raw, None, None


def chat_stream(history: list[dict], user_message: str):
    """流式生成回复，逐块 yield (chunk_text, is_done, analysis_dict_or_none)"""
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
            "stream": True,
        },
        timeout=30,
        stream=True,
    )

    full_text = ""
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]
        if data_str.strip() == "[DONE]":
            break
        try:
            data = json.loads(data_str)
            delta = data["choices"][0]["delta"]
            content = delta.get("content", "")
            if content:
                full_text += content
                yield content, False, None, None
        except Exception:
            continue

    reply, analysis, memories = _parse_analysis(full_text)
    yield "", True, analysis, memories


def chat(history: list[dict], user_message: str) -> tuple[str, dict | None, list | None]:
    """调用 DeepSeek API 生成回复，返回 (回复文本, 分析数据或None, 记忆列表或None)"""
    messages = build_messages(history, user_message)

    resp = _post_with_retry(
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
    raw = data["choices"][0]["message"]["content"]
    return _parse_analysis(raw)


UNCERTAIN_KEYWORDS = [
    "不太清楚", "不确定", "不知道", "问小多吧", "问问小多",
    "我不太懂", "没太明白", "这个我不太会", "我也不清楚",
    "说不准", "不太好说", "我不好说", "这个我回答不了",
    "换个话题", "不太明白", "没听懂", "还没有教", "还没学",
    "没学过", "还不懂", "不太会", "没教过", "没学会",
    "我不了解", "我不太了解", "不太知道",
]

# 机器人主动说"要问小多"时触发求助邮件的关键词
ALERT_KEYWORDS = [
    "问问小多", "问小多吧", "我去问问", "我帮你问问",
    "让我问问", "我去问一下", "我问问小多",
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
        resp = _post_with_retry(
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


def extract_memories(user_message: str, reply: str) -> list[dict]:
    """独立 API 调用，专门从对话中提取记忆（比嵌入分析JSON更可靠）"""
    prompt = (
        "从对话中提取值得记住的信息。只提取以下三类：\n"
        "①许小熊的设定/规则 ②小多和小豆的共同回忆（具体事件：去哪、做什么、约定）③小豆纠正你的错误。\n\n"
        "规则：\n"
        "- f是具体唯一标识（如\"哈尔滨雪翅膀\"），不是分类标签（不要用\"共同回忆\"\"约定内容\"）\n"
        "- v是具体细节描述\n"
        "- 禁止记录：当前日期、许小熊自己的情绪变化、元信息（如\"记录日期\"）\n"
        "- 同一话题只提取最重要的一条，不重复\n"
        "- f≤15字，v≤25字\n\n"
        f"用户：{user_message}\n"
        f"许小熊：{reply}\n\n"
        '返回JSON：{"m":[{"f":"事实","v":"值"},...]} 无则{"m":[]}。只返回JSON。'
    )
    try:
        resp = _post_with_retry(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 200,
            },
            timeout=15,
        )
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        parsed = json.loads(raw)
        items = parsed.get("m", [])
        return [{"f": m["f"].strip(), "v": m["v"].strip()} for m in items if m.get("f") and m.get("v")]
    except Exception:
        return []
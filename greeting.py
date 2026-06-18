"""
问候引擎 — 主动打招呼，让小熊更暖 OvO
"""
import random
import json
import os
from datetime import datetime, timezone, timedelta

import requests
from persona import ANNIVERSARIES

CST = timezone(timedelta(hours=8))

# ==================== 模板池 ====================
TEMPLATES = {
    "morning": [
        "早安呀 ☀️ 新的一天开始啦",
        "早！今天也要元气满满哦 OvO",
        "早上好呀~昨晚睡得好吗？",
        "嘿嘿 早上好！吃早餐了吗~",
    ],
    "forenoon": [
        "上午好呀~今天忙不忙 OvO",
        "上午好！我来啦~",
        "嘻嘻 上午好呀 ✨",
    ],
    "afternoon": [
        "下午好啦！要不要来杯抹茶~",
        "下午好呀~今天过得怎么样？",
        "下午好！想我了吗嘿嘿",
    ],
    "evening": [
        "晚上好呀！吃晚饭了吗 OvO",
        "嘿嘿 晚上好啦~今天开心吗？",
        "晚上好！我一直在等你呢~",
    ],
    "night": [
        "这么晚还不睡！睡啦宝宝~",
        "夜深啦~还不休息嘛？",
        "嘿嘿 半夜来找我啦？",
    ],
    "default": [
        "想你啦！",
        "嘿嘿 你来啦 ✨",
        "在呢在呢~随时都在 OvO",
    ],
}

# ==================== LLM 路径依赖 ====================
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

LLM_SYSTEM_PROMPT = (
    "你是许小熊，小多的数字分身，用来陪女朋友小豆聊天。"
    "现在你正在主动给小豆发一条问候消息。"
    "用你的风格（阳光、可爱、温暖）说1-2句话。自然亲切，不要括号动作描写。"
)


def _llm_greet(context):
    """调用 DeepSeek 生成个性化问候，失败返回 None"""
    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{context}\n请直接输出问候语，不要加引号或其他修饰。"},
                ],
                "temperature": 0.9,
                "max_tokens": 80,
            },
            timeout=10,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        if text and len(text) <= 100:
            return text
    except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError):
        pass
    return None


# ==================== 场景检测 ====================

def _last_chat_date(user_id: str) -> str | None:
    """从 chat_histories 读取最后一条消息的日期，无记录返回 None"""
    path = os.path.join("chat_histories", f"{user_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            history = json.load(f)
        if history:
            last_msg = history[-1]
            t = last_msg.get("time", "")
            if len(t) >= 10:
                return t[:10]
    except Exception:
        pass
    return None


def _detect_scene(user_id):
    """检测场景，返回 (scene_type, context_dict_or_none)

    scene_type: 'anniversary' | 'reunion' | 'time_period' | 'default'
    """
    now = datetime.now(CST)
    today = now.date()
    hour = now.hour

    # 1. 纪念日检测
    for ann in ANNIVERSARIES:
        ann_date = datetime.strptime(ann["date"], "%Y-%m-%d").date()
        if ann_date.month == today.month and ann_date.day == today.day:
            return "anniversary", {
                "name": ann["name"],
                "event": ann.get("event", ""),
            }

    # 2. 久别重逢检测
    last_date = _last_chat_date(user_id)
    if last_date:
        try:
            last = datetime.strptime(last_date, "%Y-%m-%d").date()
            gap = (today - last).days
            if gap > 3:
                return "reunion", {"date": last_date, "days": gap}
        except ValueError:
            pass

    # 3. 时段检测
    if 5 <= hour < 9:
        period = "morning"
    elif 9 <= hour < 12:
        period = "forenoon"
    elif 12 <= hour < 18:
        period = "afternoon"
    elif 18 <= hour < 21:
        period = "evening"
    else:
        period = "night"
    return "time_period", {"period": period}


# ==================== 主接口 ====================

def get_greeting(user_id: str = "xiaodou") -> str:
    """返回一条问候语。先检测场景，再决定走模板还是 LLM。"""
    scene, ctx = _detect_scene(user_id)

    if scene == "anniversary" and ctx:
        prompt = f"今天是{ctx['name']}。"
        if ctx.get("event"):
            prompt += f"（{ctx['event']}）"
        prompt += "给女朋友发一条关于这个日子的问候，表达开心和纪念。"
        llm_result = _llm_greet(prompt)
        if llm_result:
            return llm_result

    if scene == "reunion" and ctx:
        prompt = f"小豆上次跟你聊天是{ctx['date']}，已经{ctx['days']}天没见了。表达想念。"
        llm_result = _llm_greet(prompt)
        if llm_result:
            return llm_result

    # 模板路径（scene 必定是 time_period，兜底用 default）
    pool = TEMPLATES.get(ctx["period"], TEMPLATES["default"]) if ctx else TEMPLATES["default"]

    return random.choice(pool)

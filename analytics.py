"""
使用统计 & 情绪分析模块
不记录具体对话内容，只记录统计数据 OvO
"""

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))  # 北京时间

def _now():
    return datetime.now(CST)

def _today():
    return datetime.now(CST).date()

ANALYTICS_FILE = "analytics_data.json"

# ==================== 情绪词典 ====================
POSITIVE_WORDS = {
    "开心", "哈哈", "嘻嘻", "好棒", "喜欢", "爱", "谢谢", "感恩",
    "幸福", "快乐", "美好", "棒", "赞", "可爱", "好玩", "感动",
    "满意", "期待", "想你", "真好", "嘻嘻", "嘿嘿", "加油"
}

NEGATIVE_WORDS = {
    "难过", "伤心", "哭", "烦", "累", "讨厌", "生气", "焦虑",
    "害怕", "孤独", "无聊", "压力", "紧张", "不安", "委屈",
    "失望", "郁闷", "暴躁", "痛苦", "崩溃", "迷茫", "没用"
}

# ==================== 话题标签 ====================
TOPIC_KEYWORDS = {
    "邓紫棋": ["邓紫棋", "GEM", "IAG", "演唱", "句号", "天空没有极限", "歌手"],
    "抹茶": ["抹茶", "蛋糕", "甜品", "奶茶"],
    "游戏": ["明日方舟", "终末地", "模拟飞行", "双人成行", "双影奇境", "游戏"],
    "美剧": ["闪电侠", "美剧", "剧", "电影", "追剧"],
    "音乐": ["合唱", "唱歌", "歌", "音乐", "弹唱"],
    "旅行": ["旅行", "旅游", "上海", "南京", "深圳", "广州", "散步", "拍照"],
    "纪念日": ["纪念日", "在一起", "生日", "第一次"],
    "日常": ["吃饭", "睡觉", "早餐", "午餐", "晚餐", "上班", "下班", "作业", "学习", "考试"],
    "情感": ["想你", "爱", "喜欢", "陪伴", "结婚", "未来", "永远"],
    "健康": ["熬夜", "睡", "生病", "医院", "药", "运动", "减肥"],
}


def _load() -> dict:
    """加载分析数据"""
    if not os.path.exists(ANALYTICS_FILE):
        return {"users": {}}
    try:
        with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"users": {}}


def _save(data: dict):
    """保存分析数据"""
    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cleanup_old_sessions(days: int = 30):
    """删除超过指定天数的旧会话数据"""
    data = _load()
    cutoff = (_today() - timedelta(days=days)).isoformat()
    changed = False
    for user_id in list(data.get("users", {}).keys()):
        sessions = data["users"][user_id].get("sessions", [])
        new_sessions = [s for s in sessions if s["date"] >= cutoff]
        if len(new_sessions) != len(sessions):
            data["users"][user_id]["sessions"] = new_sessions
            changed = True
    if changed:
        _save(data)


NEGATION_PREFIXES = {"不", "没", "别", "无", "非", "未", "莫", "不太", "不怎么", "没那么"}


def _is_negated(text: str, pos: int) -> bool:
    """检查 pos 位置的关键词是否被否定前缀修饰"""
    for prefix in NEGATION_PREFIXES:
        start = pos - len(prefix)
        if start >= 0 and text[start:pos] == prefix:
            return True
    return False


def _count_matches(text: str, words: set) -> int:
    """统计文本中关键词命中次数，排除被否定前缀修饰的匹配"""
    count = 0
    for w in words:
        idx = 0
        while True:
            idx = text.find(w, idx)
            if idx == -1:
                break
            if not _is_negated(text, idx):
                count += 1
            idx += len(w)
    return count


def _analyze_emotion(text: str) -> str:
    """分析单条消息的情绪（关键词兜底，含否定处理）"""
    text_lower = text.lower()
    pos_score = _count_matches(text_lower, POSITIVE_WORDS)
    neg_score = _count_matches(text_lower, NEGATIVE_WORDS)

    if pos_score > neg_score:
        return "positive"
    elif neg_score > pos_score:
        return "negative"
    else:
        return "neutral"


def _extract_topics(text: str) -> list[str]:
    """从消息中提取话题标签（关键词兜底）"""
    topics = []
    text_lower = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                topics.append(topic)
                break
    if not topics:
        topics.append("日常")
    return topics


def _analyze_with_deepseek(text: str) -> dict:
    """用 DeepSeek 做语义级情绪+话题分析，失败时回退关键词"""
    try:
        import requests
        from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

        prompt = (
            "你是一个情感分析助手。分析下面这条消息，返回纯JSON（不要markdown，不要额外文字）：\n"
            '{"emotion": "positive/neutral/negative", "topics": ["话题1", "话题2"]}\n\n'
            "话题请用2-4个中文字概括，从消息的具体内容中提炼（不要笼统地说\"日常\"），"
            "例如：情感表白、游戏娱乐、美食甜品、音乐唱歌、旅行出游、学习考试、熬夜作息、工作压力、纪念日回忆、朋友社交等\n\n"
            f"消息：{text}"
        )

        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 128,
            },
            timeout=15,
        )
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]

        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            emotion = data.get("emotion", "neutral")
            topics = data.get("topics", ["日常"])
            if emotion not in ("positive", "neutral", "negative"):
                emotion = "neutral"
            return {"emotion": emotion, "topics": topics if topics else ["日常"]}

    except Exception as e:
        print(f"[DeepSeek分析] 回退关键词: {e}")

    return {
        "emotion": _analyze_emotion(text),
        "topics": _extract_topics(text),
    }


def record_message(user_id: str, role: str, content: str, analysis: dict | None = None):
    """
    记录一条消息的统计数据（不保存原文）
    只在记录用户消息时统计情绪和话题。如果提供了 analysis 则直接使用，省去 API 调用。
    """
    if role != "user":
        return

    data = _load()
    today_str = _today().isoformat()
    now_str = _now().strftime("%H:%M")

    # 确保用户存在
    if user_id not in data["users"]:
        data["users"][user_id] = {"sessions": []}

    user_data = data["users"][user_id]

    # 找到今天的会话，没有则创建
    today_session = None
    for s in user_data["sessions"]:
        if s["date"] == today_str:
            today_session = s
            break

    if today_session is None:
        today_session = {"date": today_str, "count": 0, "messages": []}
        user_data["sessions"].append(today_session)

    # 记录（优先使用内联分析，否则调用 DeepSeek）
    if analysis:
        result = {
            "emotion": analysis["emotion"],
            "topics": analysis["topics"],
        }
    else:
        result = _analyze_with_deepseek(content)

    today_session["count"] += 1
    today_session["messages"].append({
        "time": now_str,
        "emotion": result["emotion"],
        "topics": result["topics"],
    })

    _save(data)


def get_daily_frequency(user_id: str, days: int = 14) -> list[dict]:
    """获取最近N天的每日使用频率"""
    data = _load()
    if user_id not in data["users"]:
        return []
    
    sessions = data["users"][user_id]["sessions"]
    # 只返回最近N天
    cutoff = _today().isoformat()
    # 按日期倒序取
    result = []
    for s in sorted(sessions, key=lambda x: x["date"], reverse=True)[:days]:
        result.append({"date": s["date"], "count": s["count"]})
    return list(reversed(result))


def get_emotion_stats(user_id: str, days: int = 14) -> dict:
    """获取情绪统计比例"""
    data = _load()
    if user_id not in data["users"]:
        return {"positive": 0, "neutral": 0, "negative": 0}
    
    emotions = Counter()
    for s in data["users"][user_id]["sessions"]:
        for msg in s["messages"]:
            emotions[msg["emotion"]] += 1
    
    total = sum(emotions.values())
    if total == 0:
        return {"positive": 0, "neutral": 0, "negative": 0}
    
    return {
        "positive": round(emotions["positive"] / total * 100),
        "neutral": round(emotions["neutral"] / total * 100),
        "negative": round(emotions["negative"] / total * 100),
    }


def get_topic_stats(user_id: str, days: int = 7) -> list[dict]:
    """获取话题统计（词云数据），仅统计最近 N 天"""
    data = _load()
    if user_id not in data["users"]:
        return []

    cutoff = (_today() - timedelta(days=days)).isoformat()
    topics = Counter()
    for s in data["users"][user_id]["sessions"]:
        if s["date"] < cutoff:
            continue
        for msg in s["messages"]:
            for t in msg["topics"]:
                topics[t] += 1

    result = [{"name": k, "count": v} for k, v in topics.most_common()]
    return result


def consolidate_topics(user_id: str, days: int = 7) -> list[dict]:
    """用 DeepSeek 将相近话题合并归类，返回精简后的话题列表"""
    raw_topics = get_topic_stats(user_id, days=days)
    if len(raw_topics) <= 5:
        return raw_topics

    topic_names = [t["name"] for t in raw_topics]
    topic_list = "\n".join(f"- {name}" for name in topic_names)

    try:
        import requests
        from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

        prompt = (
            "你是一个话题整理助手。下面是一堆从聊天中提取的话题标签，很多意思相近但名称不同。\n"
            "请把它们合并归类成5-8个大类，每个大类用一个2-4字的标签概括。\n"
            "返回纯JSON数组（不要markdown，不要额外文字）：\n"
            '[{"name": "大类名", "count": 合并后总数, "includes": ["原始话题1", "原始话题2"]}, ...]\n\n'
            f"原始话题列表：\n{topic_list}"
        )

        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 512,
            },
            timeout=20,
        )
        result = resp.json()
        raw = result["choices"][0]["message"]["content"]

        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            consolidated = json.loads(m.group())
            return sorted(consolidated, key=lambda x: x["count"], reverse=True)
    except Exception as e:
        print(f"[consolidate_topics] 失败: {e}")

    return raw_topics


def get_recent_emotions(user_id: str, n: int = 2) -> list[str]:
    """获取用户最近 n 条消息的情绪列表（按时间倒序）"""
    data = _load()
    if user_id not in data["users"]:
        return []
    sessions = sorted(data["users"][user_id]["sessions"], key=lambda s: s["date"], reverse=True)
    emotions = []
    for s in sessions:
        for msg in reversed(s["messages"]):
            emotions.append(msg.get("emotion", "neutral"))
            if len(emotions) >= n:
                return emotions
    return emotions


def get_user_summary(user_id: str) -> dict:
    """获取用户使用概况"""
    data = _load()
    if user_id not in data["users"]:
        return {"total_sessions": 0, "total_messages": 0, "last_active": None}
    
    sessions = data["users"][user_id]["sessions"]
    total_messages = sum(s["count"] for s in sessions)
    
    last_date = None
    if sessions:
        last_date = max(s["date"] for s in sessions)
    
    return {
        "total_sessions": len(sessions),
        "total_messages": total_messages,
        "last_active": last_date,
    }

# ==================== Supabase 上报 ====================

import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_daily_stats(user_id: str) -> dict:
    """获取今日统计数据"""
    data = _load()
    if user_id not in data["users"]:
        return {
            "total_messages": 0,
            "session_count": 0,
            "sentiment_positive": 0,
            "sentiment_neutral": 0,
            "sentiment_negative": 0,
            "topics": {},
        }
    today_str = _today().isoformat()
    today_session = None
    for s in data["users"][user_id]["sessions"]:
        if s["date"] == today_str:
            today_session = s
            break
    if today_session is None:
        return {
            "total_messages": 0,
            "session_count": 0,
            "sentiment_positive": 0,
            "sentiment_neutral": 0,
            "sentiment_negative": 0,
            "topics": {},
        }
    emotions = Counter()
    topics = Counter()
    for msg in today_session["messages"]:
        emotions[msg["emotion"]] += 1
        for t in msg["topics"]:
            topics[t] += 1
    return {
        "total_messages": today_session["count"],
        "session_count": 1,
        "sentiment_positive": emotions.get("positive", 0),
        "sentiment_neutral": emotions.get("neutral", 0),
        "sentiment_negative": emotions.get("negative", 0),
        "topics": dict(topics.most_common()),
    }


def upload_stats(stats: dict):
    """把当天统计数据上传到 Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[upload_stats] Supabase 未配置，跳过上传")
        return False

    payload = {
        "date": _today().isoformat(),
        "total_messages": stats.get("total_messages", 0),
        "session_count": stats.get("session_count", 0),
        "sentiment_positive": stats.get("sentiment_positive", 0),
        "sentiment_neutral": stats.get("sentiment_neutral", 0),
        "sentiment_negative": stats.get("sentiment_negative", 0),
        "topics": stats.get("topics", {})
    }

    url = f"{SUPABASE_URL}/rest/v1/analytics?on_conflict=date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            print(f"[upload_stats] [OK] {payload['date']} 数据已上传")
            return True
        else:
            print(f"[upload_stats] [FAIL] {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[upload_stats] [FAIL] 上传失败: {e}")
        return False
    
def fetch_supabase_history(days: int | None = 30) -> list[dict]:
    """从 Supabase 拉取历史统计数据。days=None 表示不限制条数。"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[fetch_supabase] Supabase 未配置")
        return []
    url = f"{SUPABASE_URL}/rest/v1/analytics?order=date.desc"
    if days is not None:
        url += f"&limit={days}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    try:
        import requests
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[fetch_supabase] fail: {resp.status_code}")
            return []
    except Exception as e:
        print(f"[fetch_supabase] fail: {e}")
        return []
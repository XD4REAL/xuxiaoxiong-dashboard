#!/usr/bin/env python3
"""
许小熊网页版 — 小多的数字分身
双击打开就能聊 OvO
"""

import json
import logging
import uuid
import sys
import os
import webbrowser
import threading
import time
from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
from config import SECRET_KEY
from llm_client import chat, chat_stream, _parse_analysis, ALERT_KEYWORDS, extract_memories
from alerts import save_alert, get_alerts, mark_read, mark_all_read, get_unread_count
from email_notifier import send_alert
from memory import load_history, add_message, cleanup_old_histories, get_dates_with_history, get_messages_by_date
from greeting import get_greeting
from analytics import record_message, get_daily_frequency, get_emotion_stats, get_topic_stats, get_user_summary, get_daily_stats, upload_stats, fetch_supabase_history, cleanup_old_sessions, get_recent_emotions, consolidate_topics

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_base_path():
    """兼容 PyInstaller 打包后的路径"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


template_dir = os.path.join(get_base_path(), "templates")
static_dir = os.path.join(get_base_path(), "static")
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = SECRET_KEY

# 启动时清理过期数据
cleanup_old_histories(days=30)
cleanup_old_sessions(days=30)

# 求助冷却计时器，避免重复发送（秒）
ALERT_COOLDOWN = 300
_last_alert_time = {}

# 限流：每 IP 每分钟最多 20 条消息
RATE_LIMIT = 20
_rate_records = {}


def _rate_limit_check(ip: str) -> bool:
    """检查 IP 是否超限。返回 True 表示被限流。"""
    now = time.time()
    if ip not in _rate_records:
        _rate_records[ip] = []
    timestamps = _rate_records[ip]
    # 清除 60 秒前的记录
    cutoff = now - 60
    _rate_records[ip] = [t for t in timestamps if t > cutoff]
    if len(_rate_records[ip]) >= RATE_LIMIT:
        return True
    _rate_records[ip].append(now)

    # 定期清理过期 IP
    if len(_rate_records) > 500:
        _rate_records.clear()
    return False


@app.route("/")
def index():
    return render_template("chat.html")


@app.route("/sw.js")
def service_worker():
    """Service Worker — 从 root 路径提供，确保全站 scope"""
    return app.send_static_file("sw.js")


@app.route("/chat", methods=["POST"])
def chat_api():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "嗯？你说什么呀 OvO"})

    if _rate_limit_check(request.remote_addr):
        return jsonify({"reply": "小熊聊累了，休息一下嘛~ OvO"}), 429

    session["user_id"] = "xiaodou"
    user_id = session["user_id"]

    try:
        # 自动检测并保存用户教给熊的记忆（"记住：xxx是yyy"）
        from learned_memory import detect_and_save_corrections
        detect_and_save_corrections(user_message)

        history = load_history(user_id)
        reply, analysis, memories = chat(history, user_message)
        add_message(user_id, "user", user_message)
        add_message(user_id, "assistant", reply)
        record_message(user_id, "user", user_message, analysis=analysis)

        # 保存 LLM 提取的记忆（主请求内联 + 独立提取双保险）
        from learned_memory import save_llm_memories
        if memories:
            save_llm_memories(memories)
        save_llm_memories(extract_memories(user_message, reply))

        # 求助检测（必须在 upload_stats 之前，避免编码异常阻断）
        _check_and_alert(user_id, user_message, reply, analysis=analysis)

        # 上传统计数据到 Supabase
        stats = get_daily_stats(user_id)
        upload_stats(stats)

        return jsonify({"reply": reply})
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"reply": "抱歉呀，小熊刚才卡住了 OvO\n可能是网不好，你再说一遍好不好？"})


@app.route("/chat/stream", methods=["POST"])
def chat_stream_api():
    """流式聊天端点（SSE）"""
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "empty message"}), 400

    if _rate_limit_check(request.remote_addr):
        return jsonify({"reply": "小熊聊累了，休息一下嘛~ OvO"}), 429

    session["user_id"] = "xiaodou"
    user_id = session["user_id"]

    def generate():
        try:
            from learned_memory import detect_and_save_corrections
            detect_and_save_corrections(user_message)

            history = load_history(user_id)
            add_message(user_id, "user", user_message)

            reply_parts = []
            for chunk, is_done, _analysis_unused, _memories_unused in chat_stream(history, user_message):
                if chunk:
                    reply_parts.append(chunk)
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                if is_done:
                    full_reply = "".join(reply_parts)
                    clean_reply, analysis, memories = _parse_analysis(full_reply)
                    if not clean_reply:
                        clean_reply = full_reply
                    if clean_reply != full_reply:
                        yield f"data: {json.dumps({'replace': clean_reply})}\n\n"
                    add_message(user_id, "assistant", clean_reply)
                    record_message(user_id, "user", user_message, analysis=analysis)
                    from learned_memory import save_llm_memories
                    if memories:
                        save_llm_memories(memories)
                    save_llm_memories(extract_memories(user_message, clean_reply))
                    _check_and_alert(user_id, user_message, clean_reply, analysis=analysis)
                    stats = get_daily_stats(user_id)
                    upload_stats(stats)
                    yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': '小熊卡住了，再试试吧 OvO'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/remember", methods=["POST"])
def remember():
    """手动让许小熊记住一条知识"""
    data = request.get_json()
    fact = data.get("fact", "").strip()
    value = data.get("value", "").strip()
    if fact and value:
        from learned_memory import add_fact
        add_fact(fact, value, source="manual")
        return jsonify({"status": "ok", "message": f"记住啦：{fact}是{value} OvO"})
    return jsonify({"status": "error", "message": "格式不对呢，要传 fact 和 value"}), 400

@app.route("/memories")
def memories_page():
    """记忆管理页面"""
    return render_template("memories.html")


@app.route("/api/memories")
def api_memories():
    """获取所有 learned_memory"""
    from learned_memory import get_all_facts
    facts = get_all_facts()
    return jsonify(facts)


@app.route("/api/memories/<int:index>", methods=["DELETE"])
def api_delete_memory(index):
    """删除某条记忆"""
    from learned_memory import _load, _save
    data = _load()
    if 0 <= index < len(data["facts"]):
        data["facts"].pop(index)
        _save(data)
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "索引不存在"}), 404


@app.route("/dashboard")
def dashboard():
    """主用户仪表盘页面"""
    return render_template("dashboard.html")


@app.route("/api/dashboard/<user_id>")
def dashboard_api(user_id):
    """仪表盘数据API"""
    return jsonify({
        "summary": get_user_summary(user_id),
        "frequency": get_daily_frequency(user_id),
        "emotion": get_emotion_stats(user_id),
        "topics": get_topic_stats(user_id),
    })


@app.route("/api/greeting")
def greeting_api():
    """返回场景匹配的主动问候"""
    user_id = session.get("user_id", "xiaodou")
    try:
        greeting = get_greeting(user_id)
        return jsonify({"greeting": greeting})
    except Exception as e:
        logger.warning(f"Greeting failed: {e}")
        return jsonify({"greeting": "想你啦！"})


@app.route("/history")
def history_page():
    """聊天历史页面"""
    return render_template("history.html")


@app.route("/api/history/dates")
def history_dates_api():
    """返回有聊天记录的日期列表"""
    user_id = session.get("user_id", "xiaodou")
    dates = get_dates_with_history(user_id)
    return jsonify(dates)


@app.route("/api/history")
def history_api():
    """返回指定日期的聊天消息"""
    date = request.args.get("date", "")
    if not date:
        return jsonify({"error": "缺少 date 参数"}), 400
    user_id = session.get("user_id", "xiaodou")
    messages = get_messages_by_date(user_id, date)
    return jsonify(messages)


@app.route("/api/stats")
def stats_api():
    """仪表盘数据接口 — 返回 {summary, rows}，优先 Supabase，回退本地"""
    import json, os
    from collections import Counter

    days = request.args.get("days", 30, type=int)

    # 优先从 Supabase 拉取（部署环境）
    chart_rows = fetch_supabase_history(days=days)
    if chart_rows:
        # 获取真实全量统计数据（不受 days 限制）
        all_rows = fetch_supabase_history(days=None)
        summary = {
            "total_sessions": len(all_rows),
            "total_messages": sum(r.get("total_messages", 0) for r in all_rows),
            "last_active": all_rows[0]["date"] if all_rows else None,
        }
        return jsonify({"summary": summary, "rows": chart_rows})

    # 回退：本地 analytics_data.json（开发环境）
    analytics_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics_data.json")

    if not os.path.exists(analytics_file):
        return jsonify({"summary": {"total_sessions": 0, "total_messages": 0, "last_active": None}, "rows": []})

    with open(analytics_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    users = data.get("users", {})
    if not users:
        return jsonify({"summary": {"total_sessions": 0, "total_messages": 0, "last_active": None}, "rows": []})

    user_data = list(users.values())[0]
    all_sessions = user_data.get("sessions", [])
    all_sessions = sorted(all_sessions, key=lambda s: s["date"], reverse=True)
    sessions = all_sessions[:days]

    total_messages = sum(s.get("count", 0) for s in all_sessions)
    summary = {
        "total_sessions": len(all_sessions),
        "total_messages": total_messages,
        "last_active": all_sessions[0]["date"] if all_sessions else None,
    }

    result = []
    for s in sessions:
        emotions = Counter(m.get("emotion", "neutral") for m in s.get("messages", []))
        topics = Counter()
        for m in s.get("messages", []):
            for t in m.get("topics", ["日常"]):
                topics[t] += 1
        result.append({
            "date": s["date"],
            "total_messages": s.get("count", 0),
            "sentiment_positive": emotions.get("positive", 0),
            "sentiment_neutral": emotions.get("neutral", 0),
            "sentiment_negative": emotions.get("negative", 0),
            "topics": dict(topics),
        })

    return jsonify({"summary": summary, "rows": result})


@app.route("/api/dashboard/supabase")
def dashboard_supabase_api():
    """从 Supabase 拉取历史数据"""
    rows = fetch_supabase_history(days=30)
    return jsonify(rows)


@app.route("/api/topics/consolidate")
def topics_consolidate_api():
    """用 AI 整合相近话题，返回精简后的话题列表"""
    days = request.args.get("days", 7, type=int)
    user_id = session.get("user_id", "xiaodou")
    topics = consolidate_topics(user_id, days=days)
    return jsonify(topics)


@app.route("/api/alerts")
def alerts_api():
    """获取求助事件列表"""
    unread_only = request.args.get("unread", "0") == "1"
    limit = request.args.get("limit", 20, type=int)
    return jsonify(get_alerts(limit=limit, unread_only=unread_only))


@app.route("/api/alerts/read", methods=["POST"])
def alerts_read_api():
    """标记求助事件为已读"""
    data = request.get_json()
    alert_id = data.get("id", "") if data else ""
    if alert_id == "all":
        mark_all_read()
        return jsonify({"status": "ok"})
    if alert_id:
        mark_read(alert_id)
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "缺少 id"}), 400


@app.route("/api/alerts/count")
def alerts_count_api():
    """获取未读求助数量"""
    return jsonify({"unread": get_unread_count()})


def _is_substantive_query(text: str) -> bool:
    """检查用户消息是否在提问/求助（而非纯社交问候）。"""
    if len(text) <= 2:
        return False
    # 纯社交/问候/语气词，不触发求助
    social_only = {
        "你好", "你好呀", "嗨", "哈喽", "嗨喽", "早", "早上好", "中午好", "晚上好",
        "晚安", "拜拜", "再见", "谢谢", "谢谢你", "多谢", "好的", "好滴", "嗯", "哦",
        "哈哈", "嘻嘻", "嘿嘿", "呵呵", "呜呜", "emm", "emo", "哎", "唉",
        "在吗", "在不在", "在不在呀", "在干嘛", "在做什么",
        "想你", "想你了", "爱你", "抱抱", "贴贴", "mua",
    }
    if text.strip() in social_only:
        return False
    # 有问号 → 在提问
    if "？" in text or "?" in text:
        return True
    # 包含疑问/请求关键词
    question_words = [
        "什么", "怎么", "为什么", "如何", "哪里", "哪儿", "谁", "哪一",
        "何时", "能不能", "可以吗", "行不行", "好不好", "对不对", "是吗",
        "怎么办", "怎样", "多少个", "多久", "几点",
        "帮我", "教我", "告诉我", "解释", "说说", "介绍", "推荐",
        "查一下", "查一查", "搜一下", "找一下",
        "是什么意思", "什么是",
    ]
    for w in question_words:
        if w in text:
            return True
    return False


def _check_and_alert(user_id, user_message, reply, analysis=None):
    """检测是否需要触发求助"""
    triggered = False
    alert_type = None

    # 1. 连续负面情绪检测
    recent = get_recent_emotions(user_id, n=2)
    if len(recent) >= 2 and all(e == "negative" for e in recent):
        alert_type = "negative_emotion"
        triggered = True

    # 2. 机器人主动求助检测（机器人说"问问小多"等关键词 → 发邮件通知小多）
    if not triggered and _is_substantive_query(user_message):
        if any(kw in reply for kw in ALERT_KEYWORDS):
            alert_type = "low_confidence"
            triggered = True

    if not triggered:
        return

    # 冷却检查
    now = time.time()
    last = _last_alert_time.get(alert_type, 0)
    if now - last < ALERT_COOLDOWN:
        return
    _last_alert_time[alert_type] = now

    # 保存求助事件
    alert = save_alert(alert_type, user_message, reply)
    logger.info(f"[求助] {alert_type}: {user_message[:50]}...")

    # 发送通知
    send_alert(alert_type, user_message, reply)


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()

    print("""
    ╔══════════════════════════════════╗
    ║                                  ║
    ║        许小熊 上线啦！           ║
    ║                                  ║
    ║    浏览器会自动打开 ~            ║
    ║    如果没有弹出，手动访问：       ║
    ║    http://127.0.0.1:5000         ║
    ║                                  ║
    ║    仪表盘: http://127.0.0.1:5000/dashboard ║
    ║    关闭这个窗口 = 关闭小熊       ║
    ║                                  ║
    ╚══════════════════════════════════╝
    """)

    app.run(host="0.0.0.0", port=5000, debug=False)
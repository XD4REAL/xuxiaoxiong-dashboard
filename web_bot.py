#!/usr/bin/env python3
"""
许小熊网页版 — 小多的数字分身
双击打开就能聊 OvO
"""

import logging
import uuid
import sys
import os
import webbrowser
import threading
import time
from flask import Flask, render_template, request, jsonify, session
from config import SECRET_KEY
from llm_client import chat, assess_confidence
from alerts import save_alert, get_alerts, mark_read, mark_all_read, get_unread_count
from email_notifier import send_alert_email
from memory import load_history, add_message, cleanup_old_histories
from analytics import record_message, get_daily_frequency, get_emotion_stats, get_topic_stats, get_user_summary, get_daily_stats, upload_stats, fetch_supabase_history, cleanup_old_sessions, get_recent_emotions

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


@app.route("/")
def index():
    return render_template("chat.html")


@app.route("/chat", methods=["POST"])
def chat_api():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "嗯？你说什么呀 OvO"})

    session["user_id"] = "xiaodou"
    user_id = session["user_id"]

    try:
        # 自动检测并保存用户教给熊的记忆（"记住：xxx是yyy"）
        from learned_memory import detect_and_save_corrections
        detect_and_save_corrections(user_message)

        history = load_history(user_id)
        reply = chat(history, user_message)
        add_message(user_id, "user", user_message)
        add_message(user_id, "assistant", reply)
        record_message(user_id, "user", user_message)

        # 求助检测（必须在 upload_stats 之前，避免编码异常阻断）
        _check_and_alert(user_id, user_message, reply)

        # 上传统计数据到 Supabase
        stats = get_daily_stats(user_id)
        upload_stats(stats)

        return jsonify({"reply": reply})
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"reply": "抱歉呀，小熊刚才卡住了 OvO\n可能是网不好，你再说一遍好不好？"})

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


@app.route("/api/stats")
def stats_api():
    """仪表盘数据接口 — 优先从 Supabase 拉取，回退到本地文件"""
    import json, os
    from collections import Counter
    from datetime import date, timedelta

    days = request.args.get("days", 30, type=int)

    # 优先从 Supabase 拉取（部署环境）
    rows = fetch_supabase_history(days=days)
    if rows:
        return jsonify(rows)

    # 回退：本地 analytics_data.json（开发环境）
    analytics_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics_data.json")

    if not os.path.exists(analytics_file):
        return jsonify([])

    with open(analytics_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    users = data.get("users", {})
    if not users:
        return jsonify([])

    user_data = list(users.values())[0]
    sessions = user_data.get("sessions", [])
    sessions = sorted(sessions, key=lambda s: s["date"], reverse=True)[:days]

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

    return jsonify(result)


@app.route("/api/dashboard/supabase")
def dashboard_supabase_api():
    """从 Supabase 拉取历史数据"""
    rows = fetch_supabase_history(days=30)
    return jsonify(rows)


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


import time as _time_module


def _check_and_alert(user_id, user_message, reply):
    """检测是否需要触发求助"""
    triggered = False
    alert_type = None

    # 1. 连续负面情绪检测
    recent = get_recent_emotions(user_id, n=2)
    if len(recent) >= 2 and all(e == "negative" for e in recent):
        alert_type = "negative_emotion"
        triggered = True

    # 2. 回答信心检测（仅当未触发负面情绪时）
    if not triggered:
        if assess_confidence(reply, user_message):
            alert_type = "low_confidence"
            triggered = True

    if not triggered:
        return

    # 冷却检查
    now = _time_module.time()
    last = _last_alert_time.get(alert_type, 0)
    if now - last < ALERT_COOLDOWN:
        return
    _last_alert_time[alert_type] = now

    # 保存求助事件
    alert = save_alert(alert_type, user_message, reply)
    logger.info(f"[求助] {alert_type}: {user_message[:50]}...")

    # 发送邮件
    send_alert_email(alert_type, user_message, reply)


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
"""通知模块 — 许小熊求助时通过 Resend API 邮件通知小多"""
import requests
from config import RESEND_API_KEY, RESEND_SENDER, EMAIL_RECEIVER

TYPE_NAMES = {
    "negative_emotion": "小豆情绪低落",
    "low_confidence": "小熊不知道该怎么回",
}


def is_configured():
    return bool(RESEND_API_KEY and EMAIL_RECEIVER)


def send_alert(alert_type, trigger_message, bot_reply):
    """通过 Resend HTTP API 发送求助邮件"""
    if not (RESEND_API_KEY and EMAIL_RECEIVER):
        print("[email] 邮件未配置，跳过发送")
        return False

    subject = f"[许小熊求助] {TYPE_NAMES.get(alert_type, alert_type)}"
    body = f"""小多你好，

许小熊检测到了需要你关注的情况：

类型：{TYPE_NAMES.get(alert_type, alert_type)}
小豆的消息：{trigger_message}
小熊的回复：{bot_reply}

快去仪表盘看看：https://xd4real.pythonanywhere.com/dashboard

—— 许小熊自动通知
"""

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"许小熊通知 <{RESEND_SENDER}>",
                "to": [EMAIL_RECEIVER],
                "subject": subject,
                "text": body,
            },
            timeout=10,
        )
        if r.status_code == 200:
            print("[email] 邮件发送成功 (Resend API)")
            return True
        print(f"[email] 发送失败 ({r.status_code}): {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[email] 发送失败 ({type(e).__name__}): {e}")
        return False

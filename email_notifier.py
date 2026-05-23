"""邮件通知模块 — 许小熊求助时发邮件给小多"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_CONFIG


def is_configured():
    return bool(
        EMAIL_CONFIG.get("smtp_server")
        and EMAIL_CONFIG.get("sender")
        and EMAIL_CONFIG.get("password")
        and EMAIL_CONFIG.get("receiver")
    )


def send_alert_email(alert_type, trigger_message, bot_reply):
    if not is_configured():
        print("[email] 邮件未配置，跳过发送")
        return False

    type_names = {
        "negative_emotion": "小豆情绪低落",
        "low_confidence": "小熊不知道该怎么回",
    }
    subject = f"[许小熊求助] {type_names.get(alert_type, alert_type)}"

    body = f"""小多你好，

许小熊检测到了需要你关注的情况：

类型：{type_names.get(alert_type, alert_type)}
小豆的消息：{trigger_message}
小熊的回复：{bot_reply}

快去仪表盘看看：https://xd4real.pythonanywhere.com/dashboard

—— 许小熊自动通知
"""

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_CONFIG["sender"]
        msg["To"] = EMAIL_CONFIG["receiver"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP(
            EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"], timeout=10
        )
        server.starttls()
        server.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
        server.sendmail(
            EMAIL_CONFIG["sender"], EMAIL_CONFIG["receiver"], msg.as_string()
        )
        server.quit()
        print("[email] 邮件发送成功")
        return True
    except Exception as e:
        print(f"[email] 发送失败: {e}")
        return False

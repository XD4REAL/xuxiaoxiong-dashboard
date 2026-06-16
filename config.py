import os
import secrets
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Flask 密钥，用于 session
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Resend HTTP API 发邮件（替代 SMTP，绕过 PythonAnywhere 端口封锁）
# 免费版用 onboarding@resend.dev 发信，只能发给注册 Resend 时的邮箱
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_SENDER = os.getenv("RESEND_SENDER", "onboarding@resend.dev")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")

if not DEEPSEEK_API_KEY:
    raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量（在 .env 文件里）")
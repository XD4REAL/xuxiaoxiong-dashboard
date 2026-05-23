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

EMAIL_CONFIG = {
    "smtp_server": os.getenv("EMAIL_SMTP_SERVER", ""),
    "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
    "sender": os.getenv("EMAIL_SENDER", ""),
    "password": os.getenv("EMAIL_PASSWORD", ""),
    "receiver": os.getenv("EMAIL_RECEIVER", ""),
}

if not DEEPSEEK_API_KEY:
    raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量（在 .env 文件里）")
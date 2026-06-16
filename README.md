# 许小熊 Bot v1.3

小多的数字分身 — 一个用 DeepSeek 驱动的陪伴型聊天机器人，为小豆而生 OvO

## 项目简介

小多即将去法国留学，为了解决时差、维系感情，许小熊被创造出来陪伴小豆。它模拟小多的性格和说话习惯，能记住纪念日、专属回忆，还能在检测到小豆情绪低落或自己回答不了时向小多发邮件求助。

## 功能特性

- **智能聊天** — 基于 DeepSeek API，以预设人设（阳光、可爱、可靠）和专属记忆与小豆对话
- **纪念日感知** — 自动识别当天是否为纪念日，并在对话中自然融入回忆
- **持久化记忆** — 支持"记住：xxx是yyy"指令，跨对话保存用户教给熊的知识
- **情绪分析** — DeepSeek 语义级情绪+话题分析，自动追踪聊天数据
- **求助检测** — 连续负面情绪或回答不确定时触发求助，发邮件通知小多
- **数据仪表盘** — 可视化查看每日消息量、情绪比例、话题分布
- **云端同步** — 统计数据自动上报 Supabase，支持部署环境远程查看历史
- **独立运行** — 使用 PyInstaller 打包为 `.exe`，双击即可启动

## 项目结构

```
许小熊.bot 1.2/
├── web_bot.py          # 主入口，Flask Web 服务 + 聊天 API
├── llm_client.py       # DeepSeek API 调用 + 信心评估
├── persona.py          # 人设定义、纪念日、拓展知识库
├── config.py           # 环境变量配置读取
├── analytics.py        # 使用统计、情绪/话题分析、Supabase 同步
├── alerts.py           # 求助事件存储与管理
├── email_notifier.py   # 邮件通知（求助时发邮件给小多）
├── memory.py           # 对话历史本地持久化
├── learned_memory.py   # 跨对话长期记忆（用户教给熊的知识）


├── templates/
│   └── chat.html       # 聊天界面（仿微信风格）
├── static/
│   └── avatar.jpg      # 许小熊头像
├── chat_histories/     # 对话历史 JSON 文件
├── requirements.txt    # Python 依赖
└── 许小熊.spec         # PyInstaller 打包配置
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- DeepSeek API Key

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

编辑 `.env` 文件：

```env
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
DEEPSEEK_MODEL=deepseek-chat

# Supabase（可选，用于云端统计）
SUPABASE_URL=你的Supabase_URL
SUPABASE_ANON_KEY=你的Supabase_Anon_Key
SUPABASE_SERVICE_KEY=你的Supabase_Service_Key

# 邮件通知（可选，用于求助告警）
EMAIL_SMTP_SERVER=smtp.qq.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=你的邮箱@qq.com
EMAIL_PASSWORD=你的邮箱授权码
EMAIL_RECEIVER=接收通知的邮箱@qq.com
```

### 4. 启动

```bash
python web_bot.py
```

浏览器会自动打开 `http://127.0.0.1:5000`，仪表盘在 `/dashboard`。

### 5. 打包为独立程序

```bash
pyinstaller 许小熊.spec
```

打包后 `dist/许小熊/` 目录下会生成可独立运行的 `.exe`。

## 云端部署

许小熊运行在 **PythonAnywhere** 免费账户上，域名 `xd4realpython.pythonanywhere.com`。免费账户每月需手动续期一次。

### 部署架构

```
本地开发 → GitHub (git push) → PythonAnywhere (git pull + 重载)
```

### 部署更新步骤

1. 本地提交并推送到 GitHub：
   ```bash
   git add -A
   git commit -m "描述改动"
   git push origin main
   ```

2. 登录 [PythonAnywhere](https://www.pythonanywhere.com)，打开 Web App 对应的 Bash Console：
   ```bash
   cd ~/xuxiaoxiong-bot
   git pull origin main
   ```

3. 在 PythonAnywhere "Web" 标签页点击 **Reload** 按钮使更新生效。

### 环境变量

云端 `.env` 配置与本地一致（DeepSeek API Key、Supabase、邮件通知），需在 PythonAnywhere 服务器上单独创建，不纳入 git 版本控制。

### 注意事项

- 免费账户有每日 API 调用配额和 CPU 时间限制
- 每 30 天需登录 PythonAnywhere 续期一次，否则 Web App 会被暂停
- 日志文件（`chat_histories/`、`analytics_data.json` 等）存储在服务器本地，不会随 git 同步

## API 接口

| 路由 | 说明 |
|------|------|
| `GET /` | 聊天页面 |
| `POST /chat` | 发送消息，返回机器人回复 |
| `POST /chat/stream` | 流式发送消息（SSE），逐字返回回复 |
| `POST /remember` | 手动教许小熊记住一条知识 |
| `GET /dashboard` | 数据仪表盘页面 |
| `GET /api/dashboard/<user_id>` | 仪表盘数据 JSON |
| `GET /api/stats?days=30` | 统计数据（优先 Supabase） |
| `GET /api/alerts` | 求助事件列表 |
| `POST /api/alerts/read` | 标记求助为已读 |
| `GET /api/alerts/count` | 未读求助数量 |

## 技术栈

- **语言**: Python 3.13
- **Web 框架**: Flask 3.x
- **LLM**: DeepSeek Chat API
- **数据库**: Supabase (PostgreSQL) + 本地 JSON
- **打包**: PyInstaller

## 更新日志

### v1.3 (2026-05-23)

- **流式回复** — 新增 `/chat/stream` SSE 端点，前端改为逐字渲染，体验接近真实聊天打字效果
- **API 调用合并** — 分析任务改为内嵌到回复 prompt 中一次完成，每条消息从 3 次 API 调用降为 1 次（成本降低约 67%）
- **请求失败重试** — DeepSeek API 遇到 5xx 自动重试一次（1s 间隔），提升可用性
- **IP 限流** — 新增基于 IP 的滑动窗口限流（20 条/分钟），防止滥用
- **服务合并** — 废弃 `dashboard_server.py`，所有路由统一到 `web_bot.py`
- **项目清理** — 删除 PyInstaller 构建产物、空文件、已合并的补丁脚本，释放约 87MB

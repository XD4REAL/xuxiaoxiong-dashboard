# 许小熊 Bot v1.5

小多的数字分身 — 一个用 DeepSeek 驱动的陪伴型聊天机器人，为小豆而生 OvO

## 项目简介

小多即将去法国留学，为了解决时差、维系感情，许小熊被创造出来陪伴小豆。它模拟小多的说话风格，能记住纪念日和专属回忆，会在小豆情绪低落时通知小多。

## 功能特性

- **智能聊天** — DeepSeek V4 Flash 驱动，短句自然风格，像真人发微信一样
- **PWA 支持** — 手机浏览器打开后添加到桌面，全屏像原生 App
- **纪念日感知** — 16 个纪念日自动识别 + 30 天内临近提醒
- **记忆系统** — LLM 自动从对话中提取事实 + 正则检测「记住：xxx是yyy」指令，跨对话持久化
- **记忆质量过滤** — 拒绝分类标签、近重复检测、只取用户消息不碰 AI 回复
- **情绪分析** — DeepSeek 语义级情绪 + 话题分析，自动追踪聊天数据
- **求助检测** — 连续负面情绪或低置信度时触发，Resend API 邮件通知小多
- **数据仪表盘** — 可视化每日消息量、情绪比例、话题分布
- **云端同步** — 统计数据自动上报 Supabase，支持部署环境远程查看历史
- **独立运行** — 使用 PyInstaller 打包为 `.exe`，双击启动

## 项目结构

```
许小熊.bot/
├── web_bot.py          # Flask Web 服务 + 聊天 API + 所有路由
├── llm_client.py       # DeepSeek API 调用 + 信心评估 + 记忆提取
├── persona.py          # 人设定义、纪念日、拓展知识库
├── config.py           # 环境变量配置读取
├── analytics.py        # 使用统计、情绪/话题分析、Supabase 同步
├── alerts.py           # 求助事件存储与管理
├── email_notifier.py   # Resend API 邮件通知
├── memory.py           # 对话历史本地持久化
├── learned_memory.py   # 长期记忆系统（自动提取 + 质量过滤）
│
├── templates/
│   ├── chat.html       # 聊天界面（微信风格 + PWA）
│   ├── dashboard.html  # 数据仪表盘
│   └── memories.html   # 记忆管理页面
├── static/
│   ├── avatar.jpg      # 许小熊头像
│   ├── manifest.json   # PWA 清单
│   └── sw.js           # Service Worker（离线缓存）
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
DEEPSEEK_MODEL=deepseek-v4-flash

# Resend 邮件通知（可选）
RESEND_API_KEY=你的Resend_API_Key
RESEND_SENDER=onboarding@resend.dev
EMAIL_RECEIVER=接收通知的邮箱

# Supabase（可选，用于云端统计）
SUPABASE_URL=你的Supabase_URL
SUPABASE_ANON_KEY=你的Supabase_Anon_Key
SUPABASE_SERVICE_KEY=你的Supabase_Service_Key
```

### 4. 启动

```bash
python web_bot.py
```

浏览器自动打开 `http://127.0.0.1:5000`，仪表盘在 `/dashboard`，记忆管理在 `/memories`。

### 5. 打包为独立程序

```bash
pyinstaller 许小熊.spec
```

## 云端部署

部署在 **PythonAnywhere** 免费账户：`https://xd4real.pythonanywhere.com/`

免费账户每 30 天需手动续期一次。

## API 接口

| 路由 | 说明 |
|------|------|
| `GET /` | 聊天页面 |
| `POST /chat` | 发送消息 |
| `POST /chat/stream` | 流式发送消息（SSE） |
| `GET /memories` | 记忆管理页面 |
| `GET /api/memories` | 获取所有记忆 |
| `DELETE /api/memories/<id>` | 删除某条记忆 |
| `POST /remember` | 手动教许小熊记住知识 |
| `GET /dashboard` | 数据仪表盘 |
| `GET /api/dashboard/<user_id>` | 仪表盘 JSON |
| `GET /api/stats` | 统计数据（优先 Supabase） |
| `GET /api/topics/consolidate` | AI 整合相近话题 |
| `GET /api/alerts` | 求助事件列表 |
| `POST /api/alerts/read` | 标记求助已读 |
| `GET /api/alerts/count` | 未读求助数量 |
| `GET /history` | 聊天历史页面 |
| `GET /api/history/dates` | 有记录的日期列表 |
| `GET /api/history?date=YYYY-MM-DD` | 某天聊天记录 |

## 技术栈

- **语言**: Python 3.12
- **Web 框架**: Flask 3.x
- **LLM**: DeepSeek V4 Flash
- **数据库**: Supabase + 本地 JSON
- **打包**: PyInstaller

## 更新日志

### v1.5 (2026-06-17)

- **聊天历史回看** — 新增 `/history` 页面，按日期浏览历史对话，聊天气泡样式一致
- 消息新增时间戳字段，支持按日期 API 查询

### v1.4.5 (2026-06-16)

- **记忆质量修复** — 三层防线：LLM 提取 + 质量过滤（拒绝分类标签、近重复、f===v）+ 只取用户消息不碰 AI 回复
- **风格调整** — 短句为主、去括号动作描写、每次请求加强制提醒
- **括号自动过滤** — 代码级 `（...）` 清洗，保底方案
- **PWA 支持** — 新增 manifest + Service Worker，手机可添加到桌面
- **模型升级** — deepseek-chat → deepseek-v4-flash
- **Bug 修复** — 记忆重复存储、LLM 瞎编污染、email_notifier 导入错误

### v1.4 (2026-05-27)

- 新增 `extract_memories()` LLM 自动提取记忆，无需固定口令
- 关键词匹配按需检索记忆（最多8条），节省 token
- 记忆管理页面 `/memories`
- 去重 & 质量优化

### v1.3 (2026-05-23)

- 流式回复（SSE）逐字渲染
- API 调用合并（3次→1次，成本降67%）
- IP 限流（20条/分钟）
- 服务合并，项目清理

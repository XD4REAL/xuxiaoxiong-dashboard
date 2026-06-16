# 许小熊 更新日志

## v1.4 — 2026-05-27 · 记忆系统

### 自然语言自动记记忆
- 新增 `extract_memories()`（`llm_client.py`）：每次对话后独立调用 DeepSeek，自动提取值得记住的信息，无需固定口令（"记住：xxx是yyy"）
- 三类记忆：许小熊设定/规则、小多和小豆的共同回忆、小豆纠正错误
- `learned_memory.json` 容量：50 → 200

### 按需检索
- `build_memory_context()` 改为关键词匹配：只注入与当前话题相关的记忆（最多8条），不再把全部记忆塞进每次对话，节省 token

### 记忆管理页面
- 新增 `/memories` 页面：浏览、删除 learned_memory，手机适配

### 去重 & 质量优化
- `add_fact()` 增加 value 级去重，相同值不重复写入
- 提取 Prompt 优化：禁止记录当前日期、自身情绪、元信息，事实名要求具体唯一标识

## v1.4.1 — 2026-06-16 · Bug 修复

- **P0**: `.env` 中 Supabase 变量名前导空格移除，修复云端同步静默失败
- **P1**: `chat_stream()` 增加 5xx 重试逻辑，与非流式 `chat()` 行为一致
- **P2**: `_analyze_emotion()` 增加否定前缀识别（不/没/别/无/非/未/莫/不太/不怎么/没那么），不再把"不开心"误判为正面
- **P3**: 清理死代码 — `persona.py` 无用函数、`learned_memory.py` 无效行、`web_bot.py` 重复 import

## v1.3 — 2026-05-23 · 稳定性

- API 超时自动重试一次
- 流式输出（SSE）：回复逐字显示
- 限流：每 IP 每分钟最多 20 条
- 求助冷却：同类求助 5 分钟内不重复发送
- 仪表盘数据优先读 Supabase，回退本地
- `/chat` 和 `/chat/stream` 共用逻辑，清理重复代码

## v1.2 — 2026-05-23 · 初始发布

- Flask 网页聊天机器人，DeepSeek 驱动
- 纪念日系统（persona.py + get_today_info）
- 仪表盘（/dashboard）：情绪、话题、活跃度
- 求助邮件通知（低置信度/负面情绪 → Resend API）
- PyInstaller 打包为 Windows EXE

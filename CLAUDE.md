# China Social Media Tools - Claude Code 开发指南

## 项目概述
中国社交媒体自动化工具，支持今日头条、小红书等平台的内容自动发布。

## 现有代码结构
- `tools/advanced.py` - 核心模块 (3225行)：AutoLogin, ImageGenerator, ContentGenerator, XiaohongshuPublisher, TaskScheduler
- `tools/social_publisher.py` - 头条号发布器
- `tools/__init__.py` - 模块导入
- `app.py` - Streamlit Web 界面
- `requirements.txt` - 依赖包含 apscheduler>=6.10.0

## 已完成任务 (2026-04-18)

### ✅ 1. 集成 APScheduler 实现定时任务
- TaskScheduler 已集成 APScheduler
- 添加了 start() / stop() 方法
- 支持持久化任务状态

### ✅ 2. 编写单元测试
- tests/test_task_scheduler.py - 29个测试全部通过
- tests/test_autologin.py - 已创建
- tests/test_image_generator.py - 已创建
- tests/test_content_generator.py - 已创建

### ✅ 3. 模块导入修复
- 添加 tools/__init__.py 支持 `from tools import *`

## 需要完成的任务

### 1. 添加视频发布功能 (参考 social-auto-upload 9384 stars)
- 抖音视频上传
- 小红书视频上传

### 2. 增加更多平台支持
- 微信公众号文章发布
- 快手视频上传

### 3. AI Agent 集成
- 添加 skill 模块支持 OpenClaw/Codex

### 4. 完善文档
- 添加中文使用教程
- 添加 API 文档

## 开发规范
- 使用 Python 类型注解
- 完整的 docstring
- 错误处理和日志记录
- 保持与现有代码风格一致

## 验证步骤
完成后运行：
```bash
python -m pytest tests/ -v
```
确保所有测试通过。

# China Social Media Tools - Claude Code 开发指南

## 项目概述
中国社交媒体自动化工具，支持今日头条、小红书等平台的内容自动发布。

## 现有代码结构
- `tools/advanced.py` - 核心模块 (3225行)：AutoLogin, ImageGenerator, ContentGenerator, XiaohongshuPublisher, TaskScheduler
- `tools/social_publisher.py` - 头条号发布器
- `app.py` - Streamlit Web 界面
- `requirements.txt` - 依赖包含 apscheduler>=6.10.0

## 需要完成的任务

### 1. 集成 APScheduler 实现定时任务实际执行 (高优先级)
当前 TaskScheduler 类只存储任务配置，需要添加 APScheduler 集成让任务真正定时执行。

目标：
- 在 TaskScheduler.__init__ 中初始化 APScheduler
- 添加 start() / stop() 方法控制调度器
- 任务到期时自动调用对应的 task handler
- 支持持久化任务状态（重启后恢复）

### 2. 编写单元测试 (高优先级)
为以下模块编写 pytest 测试：

tests/test_autologin.py - 测试 AutoLogin
- test_login_success (模拟成功)
- test_cookie_refresh
- test_session_persistence

tests/test_image_generator.py - 测试 ImageGenerator
- test_generate_with_openai
- test_generate_with_anthropic
- test_cache_mechanism

tests/test_content_generator.py - 测试 ContentGenerator
- test_generate_basic
- test_quality_evaluation
- test_history_tracking

tests/test_task_scheduler.py - 测试 TaskScheduler
- test_add_task
- test_enable_disable_task
- test_run_task

### 3. 创建测试框架
- 使用 pytest
- Mock 外部依赖（浏览器、API 调用）
- 确保测试独立、可重复

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

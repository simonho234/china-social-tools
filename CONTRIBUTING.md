# 贡献指南

感谢您对中国社交媒体自动化工具项目的兴趣！本指南将帮助您了解如何为项目做出贡献。

## 如何贡献

### 报告问题

如果您发现Bug或有功能请求，请先查看 [Issues](https://github.com/simonho234/china-social-tools/issues) 确保问题未被报告。

报告问题时，请包含：
- 清晰的标题和描述
- 复现问题的步骤
- 期望的行为 vs 实际行为
- 您的环境信息 (OS, Python版本等)

### 提交代码

1. **Fork 仓库**
   ```
   gh repo fork simonho234/china-social-tools
   ```

2. **克隆到本地**
   ```
   git clone https://github.com/YOUR_USERNAME/china-social-tools.git
   cd china-social-tools
   ```

3. **创建功能分支**
   ```
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/issue-description
   ```

4. **进行开发**
   - 遵循现有的代码风格
   - 添加测试用例
   - 更新文档

5. **提交更改**
   ```
   git add .
   git commit -m 'Add: 添加新功能描述'
   ```

6. **推送分支**
   ```
   git push origin feature/your-feature-name
   ```

7. **创建 Pull Request**
   ```
   gh pr create --title "Add: 新功能描述" --body "详细描述..."
   ```

## 代码规范

### Python 代码风格

- 使用 [PEP 8](https://www.python.org/dev/peps/pep-0008/) 规范
- 最大行长度: 120 字符
- 使用类型注解 (type hints)
- 添加 docstring 文档

### 类型注解示例

```python
from typing import Optional, List, Dict

def publish_content(
    platform: str,
    title: str,
    content: str,
    images: Optional[List[str]] = None
) -> Dict[str, any]:
    """
    发布内容到指定平台
    
    Args:
        platform: 目标平台 (toutiao/xiaohongshu/douyin)
        title: 内容标题
        content: 正文内容
        images: 可选的图片列表
        
    Returns:
        包含发布结果的字典
        
    Raises:
        ValueError: 当平台不支持时
    """
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支持的平台: {platform}")
    # ... 实现代码
```

### 测试规范

- 所有新功能必须包含测试
- 保持测试简洁和可读
- 使用描述性的测试函数名

```python
def test_autologin_with_valid_credentials():
    """测试有效凭证登录"""
    # Arrange
    login = AutoLogin(phone="valid_phone", password="valid_pass")
    
    # Act
    result = login.login()
    
    # Assert
    assert result is True
    assert login.is_logged_in() is True
```

## 项目结构

```
china-social-tools/
├── tools/              # 核心功能模块
│   ├── advanced.py    # AutoLogin, ContentGenerator, ImageGenerator
│   ├── social_publisher.py  # 基础发布器
│   └── video_uploader.py  # 视频上传器
├── app.py            # Streamlit Web界面
├── tests/           # 测试文件
└── data/           # 数据存储
```

## 提交消息规范

使用conventional commits格式：

```
<type>(<scope>): <description>

[可选的详细描述]

[可选的关闭issue]
```

类型 (type):
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 维护

示例:
```
feat(socialPublisher): 添加定时发布功能

添加APScheduler支持，实现定时任务调度功能。
支持cron表达式和固定间隔设置。

Closes #123
```

## 审阅标准

PR 会被基于以下标准审阅：
- [ ] 代码符合项目风格
- [ ] 包含���试用例
- [ ] 文档已更新
- [ ] 无合并冲突

## 获取帮助

- GitHub Issues: 提问和报告问题
- 项目README: 基础使用文档

感谢您的贡献！ 🎉
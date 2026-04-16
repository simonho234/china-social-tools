# 🇨🇳 China Social Media Automation Toolkit

<p align="center">
  <img src="https://img.shields.io/github/stars/wingzero234/china-social-tools" alt="stars">
  <img src="https://img.shields.io/github/forks/wingzero234/china-social-tools" alt="forks">
  <img src="https://img.shields.io/github/license/wingzero234/china-social-tools" alt="license">
</p>

> 一个开源的中国社交媒体自动化工具集，支持今日头条、小红书、抖音等平台的自动化运营。

## ✨ 特性

- 🤖 **自动化发布**: 支持多个平台的内容自动发布
- 🖼️ **AI 配图**: 集成为内容生成匹配的封面图
- 📊 **数据分析**: 分析内容表现，优化发布策略
- ⏰ **定时任务**: 支持定时自动发布
- 🌐 **Web 界面**: 友好的 Streamlit 管理界面

## 📱 支持的平台

| 平台 | 状态 | 功能 |
|------|------|------|
| 今日头条 | ✅ | 自动发布微头条/图文 |
| 小红书 | 🔄 开发中 | 自动发布图文 |
| 抖音 | 📋 计划中 | 视频发布 |
| 微信公众号 | 📋 计划中 | 文章发布 |

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/wingzero234/china-social-tools.git
cd china-social-tools

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置

1. 复制配置示例文件:
```bash
cp config.example.yaml config.yaml
```

2. 编辑 `config.yaml` 添加你的凭证:
```yaml
toutiao:
  phone: "your_phone"
  password: "your_password"

openai:
  api_key: "your-openai-api-key"
```

### 运行

```bash
# 启动 Web 界面
streamlit run app.py

# 或使用命令行
python cli.py post --platform toutiao --content "Hello World"
```

## 📖 使用文档

详细文档查看 [Wiki](https://github.com/wingzero234/china-social-tools/wiki)

## 🛠 技术栈

- **Python 3.9+**
- **Streamlit** - Web 界面
- **Selenium** - 浏览器自动化
- **OpenAI API** - AI 生成
- **APScheduler** - 定时任务
- **Hyperliquid SDK** - 加密货币交易（可选）

## 📝 示例

### Python API 使用

```python
from toutiao import ToutiaoPublisher

# 初始化
publisher = ToutiaoPublisher(phone="...", password="...")

# 发布内容
result = publisher.publish(
    title="你的标题",
    content="正文内容...",
    image_path="cover.jpg"
)
print(result)
```

### 命令行使用

```bash
# 发布到头条号
python -m tools.toutiao publish --content "测试内容" --image photo.jpg

# 查看状态
python -m tools.toutiao status
```

## 🤝 贡献

欢迎提交 Pull Request！请先阅读 [贡献指南](CONTRIBUTING.md)。

## 📄 许可证

MIT License - 查看 [LICENSE](LICENSE)

## 🏆 支持

如果这个项目对你有帮助，请 ⭐ star 支持！

---

Built with ❤️ by [wingzero234](https://github.com/wingzero234)
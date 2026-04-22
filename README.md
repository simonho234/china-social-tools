# 🇨🇳 China Social Media Automation Toolkit

<p align="center">
  <a href="https://github.com/simonho234/china-social-tools/stargazers">
    <img src="https://img.shields.io/github/stars/simonho234/china-social-tools" alt="stars">
  </a>
  <a href="https://github.com/simonho234/china-social-tools/network">
    <img src="https://img.shields.io/github/forks/simonho234/china-social-tools" alt="forks">
  </a>
  <img src="https://img.shields.io/github/license/simonho234/china-social-tools" alt="license">
  <img src="https://img.shields.io/python-version/pyversion/china-social-tools" alt="py-version">
</p>

> 🇺🇸 An open-source Chinese social media automation toolkit, supporting Toutiao (今日头条), Xiaohongshu (小红书), and more.
>
> 🇨🇳 一个开源的中国社交媒体自动化工具集，支持今日头条、小红书、抖音等平台的自动化运营。

## ✨ 特性

- 🤖 **自动化发布** - 支持多个平台的内容自动发布
- 🖼️ **AI 配图** - 集成为内容生成匹配的封面图
- 📊 **数据分析** - 分析内容表现，优化发布策略
- ⏰ **定时任务** - 支持定时自动发布
- 🌐 **Web 界面** - 友好的 Streamlit 管理界面
- 📰 **热榜数据** - 自动收集热门话题数据
- ✍️ **内容生成** - AI 辅助生成高质量内容

## 📱 支持的平台

| 平台 | 状态 | 功能 |
|------|------|------|
| 今日头条 | ✅ 可用 | 自动发布微头条/图文 |
| 抖音 | ✅ 可用 | 视频上传发布 |
| 小红书 | ✅ 可用 | 图文笔记发布 |
| 快手 | ✅ 可用 | 视频上传发布 |
| B站 | ✅ 可用 | 视频上传发布 |
| 微信公众号 | 📋 计划中 | 文章发布 |

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Chrome 浏览器 (用于自动化)
- OpenAI API Key (可选，用于AI功能)

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/simonho234/china-social-tools.git
cd china-social-tools

# 2. 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt
```

### 配置

1. 复制配置示例文件:
```bash
cp config.example.yaml config.yaml
```

2. 编辑 config.yaml 添加凭证:
```yaml
toutiao:
  phone: "your_phone_number"
  password: "your_password"

openai:
  api_key: "your-openai-api-key"

# 可选: 添加代理
proxy:
  enabled: false
  http: "http://127.0.0.1:7890"
  https: "http://127.0.0.1:7890"
```

或者使用环境变量:
```bash
export TOUTIAO_PHONE="your_phone"
export TOUTIAO_PASSWORD="your_password"
export OPENAI_API_KEY="your-openai-api-key"
```

### 运行

```bash
# 方式1: 启动 Web 界面 (推荐)
streamlit run app.py

# 方式2: 命令行使用
python -m tools.social_publisher --platform toutiao --content "Hello World"

# 方式3: Python API
python -c "
from tools.advanced import AutoLogin, ContentGenerator, ImageGenerator

# 生成内容
gen = ContentGenerator()
content = gen.generate('AI技术发展', 400)
print(content)
"
```

## 📖 详细使用文档

### 1. 头条号自动发布

#### 功能特点
- ✅ 自动登录 (保存Cookie无需重复登录)
- ✅ 支持图片上传和AI配图
- ✅ 支持400+字深度内容
- ✅ 自动收集热榜数据

#### 使用示例

```python
from tools.advanced import AutoLogin, ContentGenerator, ImageGenerator, ContentCollector

# 1. 自动登录
login = AutoLogin(phone="your_phone", password="your_password")
if login.login():
    print("登录成功!")

# 2. 收��热榜数据
collector = ContentCollector()
trending = collector.get_trending()
for item in trending[:5]:
    print(f"- {item['title']} ({item['source']})")

# 3. 生成内容
gen = ContentGenerator()
content = gen.generate("AI技术热门话题", min_words=400)
print(content)

# 4. 生成配图
img_gen = ImageGenerator()
image_url = img_gen.generate(content, style="自然风格")
print(f"配图: {image_url}")
```

### 2. AI 配图

支持 OpenAI DALL-E 生成配图:
```python
from tools.advanced import ImageGenerator

generator = ImageGenerator(api_key="your-openai-key")
# 生成图片
url = generator.generate("科技新闻", "简洁风格")
# 下载图片
local_path = generator.download(url, "my_image.png")
```

### 3. 内容生成

使用AI生成400+字深度内容:
```python
from tools.advanced import ContentGenerator

gen = ContentGenerator(api_key="your-openai-key")
content = gen.generate("如何提升工作效率", min_words=400)
print(content)
```

### 4. 热榜数据收集

自动收集今日头条热榜:
```python
from tools.advanced import ContentCollector

collector = ContentCollector()
trending = collector.get_trending("hot")
for item in trending:
    print(f"{item['title']} - {item['source']} ({item['comments']}评论)")
```

### 5. Web 界面使用

启动后访问 http://localhost:8501

功能包括:
- 📝 发布内容 (支持AI生成配图)
- 📊 查看统计数据
- ⏰ 设置定时任务
- ⚙️ 配置管理

### 6. 抖音视频上传

支持自动上传视频到抖音:
```python
from tools import DouyinUploader, VideoMetadata

# 准备视频元数据
metadata = VideoMetadata(
    file_path="/path/to/video.mp4",
    title="我的第一个视频",
    description="这是测试视频内容",
    tags=["测试", "教程", "科技"]
)

# 上传视频
uploader = DouyinUploader()
uploader.set_driver(driver)  # 设置已登录的WebDriver
result = uploader.upload(metadata)

print(f"上传结果: {result.success}")
if result.success:
    print(f"视频ID: {result.video_id}")
```

批量上传:
```python
videos = [
    VideoMetadata(file_path="video1.mp4", title="视频1"),
    VideoMetadata(file_path="video2.mp4", title="视频2"),
]
results = uploader.upload_batch(videos, delay=5)
```

### 7. 快手视频上传

支持自动上传视频到快手:
```python
from tools import KuaishouUploader, KuaishouVideoMetadata

# 准备视频元数据
metadata = KuaishouVideoMetadata(
    file_path="/path/to/video.mp4",
    title="我的视频",
    description="这是测试视频内容",
    tags=["测试", "教程", "科技"]
)

# 上传视频
uploader = KuaishouUploader(phone="xxx", password="xxx")
uploader.set_driver(driver)
result = uploader.upload(metadata)

print(f"上传结果: {result.success}")
if result.success:
    print(f"视频链接: {result.video_url}")
```

批量上传:
```python
videos = [
    KuaishouVideoMetadata(file_path="video1.mp4", title="视频1"),
    KuaishouVideoMetadata(file_path="video2.mp4", title="视频2"),
]
results = uploader.upload_batch(videos, delay=5)
```

### 8. B站(Bilibili)视频上传

支持自动上传视频到B站:
```python
from tools import BilibiliUploader, BilibiliVideoMetadata

# 准备视频元数据
metadata = BilibiliVideoMetadata(
    file_path="/path/to/video.mp4",
    title="我的视频",
    description="这是测试视频内容",
    tags=["测试", "教程", "科技"],
    category="科技",
    sub_category="计算机"
)

# 上传视频
uploader = BilibiliUploader()
uploader.set_driver(driver)  # 设置已登录的WebDriver
result = uploader.upload(metadata)

print(f"上传结果: {result.success}")
if result.success:
    print(f"BVID: {result.bvid}")
    print(f"视频链接: {result.video_url}")
```

批量上传:
```python
videos = [
    BilibiliVideoMetadata(file_path="video1.mp4", title="视频1"),
    BilibiliVideoMetadata(file_path="video2.mp4", title="视频2"),
]
results = uploader.upload_batch(videos, delay=10)
```

## 🛠 技术栈

- **Python 3.9+** - 编程语言
- **Streamlit** - Web 界面
- **Selenium** - 浏览器自动化
- **OpenAI API** - AI 生成
- **Playwright** - 浏览器自动化
- **APScheduler** - 定时任务
- **Requests** - HTTP 请求

## 📁 项目结构

```
china-social-tools/
├── README.md              # 项目说明
├── app.py                 # Streamlit Web界面
├── requirements.txt       # 依赖列表
├── config.example.yaml    # 配置模板
├── tools
│   ├── social_publisher.py  # 基础发布器
│   ├── video_uploader.py   # 抖音视频上传器
│   ├── kuaishou_uploader.py # 快手视频上传器
│   └── advanced.py          # 高级功能
│       ├── AutoLogin         # 自动登录
│       ├── ImageGenerator   # AI配图
│       ├── ContentGenerator # 内容生成
│       └── ContentCollector # 热榜收集
├── data/
│   ├── cookies.json        # Cookie存储
│   ├── videos/            # 视频存储
│   └── images/            # 图片存储
└── PROJECT.md             # 项目维护手册
```

## 🤝 贡献

欢迎提交 Pull Request！请先阅读贡献流程:

1. Fork 本仓库
2. 创建功能分支 (git checkout -b feature/xxx)
3. 提交更改 (git commit -m 'Add xxx')
4. 推送分支 (git push origin feature/xxx)
5. 创建 Pull Request

## 📄 许可证

MIT License - 详见 LICENSE

## 🏆 支持

如果这个项目对你有帮助，请 ⭐ star 支持！

---
 Built with ❤️ by simonho234(https://github.com/simonho234)

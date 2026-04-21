# API Reference

## 核心模块

### tools.advanced

#### AutoLogin

自动登录类，支持头条号等平台的自动登录。

```python
from tools.advanced import AutoLogin

login = AutoLogin(phone="your_phone", password="your_password")
```

**方法:**

##### `login() -> bool`

执行登录操作。

```python
result = login.login()
# True if successful
```

##### `is_logged_in() -> bool`

检查当前登录状态。

```python
if login.is_logged_in():
    print("已登录")
```

##### `logout() -> None`

登出并清除登录状态。

##### `get_driver() -> WebDriver`

获取WebDriver实例。

---

#### ContentGenerator

AI内容生成器。

```python
from tools.advanced import ContentGenerator

gen = ContentGenerator(api_key="your-openai-key")
```

**方法:**

##### `generate(topic: str, min_words: int = 400) -> str`

生成指定主题的内容。

```python
content = gen.generate("AI技术发展", min_words=500)
print(content)  # 返回生成的内容
```

##### `generate_title(keywords: List[str]) -> str`

生成标题。

```python
title = gen.generate_title(["AI", "科技"])
```

---

#### ImageGenerator

AI图像生成器。

```python
from tools.advanced import ImageGenerator

img_gen = ImageGenerator(api_key="your-dalle-key")
```

**方法:**

##### `generate(content: str, style: str = "自然风格") -> str`

生成配图。

```python
url = img_gen.generate("科技新闻", style="简洁风格")
# 返回图片URL
```

##### `download(url: str, filename: str) -> str`

下载生成的图片。

```python
local_path = img_gen.download(url, "cover.png")
```

---

#### ContentCollector

热榜内容收集器。

```python
from tools.advanced import ContentCollector

collector = ContentCollector()
```

**方法:**

##### `get_trending(category: str = "hot") -> List[Dict]`

获取热榜数据。

```python
trending = collector.get_trending()
for item in trending[:10]:
    print(f"{item['title']} - {item['source']}")
```

---

### tools.social_publisher

#### ToutiaoPublisher

头条号发布器。

```python
from tools.social_publisher import ToutiaoPublisher

publisher = ToutiaoPublisher()
```

**方法:**

##### `publish(title: str, content: str, images: List[str] = None) -> PublishResult`

发布内容。

```python
result = publisher.publish(
    title="我的标题",
    content="正文内容...",
    images=["image1.jpg", "image2.jpg"]
)
print(f"发布成功: {result.success}")
```

---

### tools.video_uploader

#### DouyinUploader

抖音视频上传器。

```python
from tools.video_uploader import DouyinUploader, VideoMetadata

uploader = DouyinUploader()
```

**方法:**

##### `upload(metadata: VideoMetadata) -> UploadResult`

上传单个视频。

```python
metadata = VideoMetadata(
    file_path="video.mp4",
    title="视频标题",
    description="视频描述",
    tags=["科技", "AI"]
)
result = uploader.upload(metadata)
```

##### `upload_batch(videos: List[VideoMetadata], delay: int = 5) -> List[UploadResult]`

批量上传视频。

```python
videos = [
    VideoMetadata(file_path="v1.mp4", title="标题1"),
    VideoMetadata(file_path="v2.mp4", title="标题2")
]
results = uploader.upload_batch(videos, delay=10)
```

---

### tools.kuaishou_uploader

#### KuaishouUploader

快手视频上传器。

```python
from tools.kuaishou_uploader import KuaishouUploader, KuaishouVideoMetadata

uploader = KuaishouUploader(phone="xxx", password="xxx")
```

**方法:**

与 DouyinUploader 类似。

---

## 数据类型

### PublishResult

```python
@dataclass
class PublishResult:
    success: bool
    url: str = ""
    article_id: str = ""
    error: str = ""
```

### UploadResult

```python
@dataclass
class UploadResult:
    success: bool
    video_id: str = ""
    video_url: str = ""
    error: str = ""
```

### VideoMetadata

```python
@dataclass
class VideoMetadata:
    file_path: str
    title: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    location: Optional[str] = None
```

---

## 异常处理

```python
from tools.advanced import LoginError, ContentError

try:
    publisher.publish(title="Test", content="Content")
except LoginError as e:
    print(f"登录失败: {e}")
except ContentError as e:
    print(f"内容生成失败: {e}")
```

---

## 完整示例

```python
from tools.advanced import AutoLogin, ContentGenerator, ImageGenerator
from tools.social_publisher import ToutiaoPublisher

# 1. 登录
login = AutoLogin(phone="your_phone", password="your_password")
if login.login():
    print("登录成功")
    
# 2. 生成内容
gen = ContentGenerator(api_key="your-key")
content = gen.generate("AI技术热门话题", min_words=400)
title = gen.generate_title(["AI", "科技"])

# 3. 生成配图
img_gen = ImageGenerator(api_key="your-key")
image_url = img_gen.generate(content)
image_path = img_gen.download(image_url, "cover.png")

# 4. 发布
publisher = ToutiaoPublisher()
result = publisher.publish(title=title, content=content, images=[image_path])

print(f"发布结果: {result.success}")
if result.success:
    print(f"文章链接: {result.url}")
```
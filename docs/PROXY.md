# 代理配置指南

本文档说明如何配置代理以访问国内社交媒体平台。

## 为什么需要代理

国内平台（如今日头条、抖音、小红书等）可能需要代理才能从海外访问。本项目支持通过配置代理来访问这些平台。

## 配置方法

### 1. 环境变量配置

```bash
# HTTP 代理
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"

# SOCKS 代理
export SOCKS_PROXY="socks5://127.0.0.1:1080"
```

### 2. 配置文件配置

在 `config.yaml` 中配置:

```yaml
proxy:
  enabled: true
  http: "http://127.0.0.1:7890"
  https: "http://127.0.0.1:7890"
  socks5: "socks5://127.0.0.1:1080"
```

### 3. 代码中配置

```python
from tools.advanced import AutoLogin

# 使用代理
login = AutoLogin(
    phone="your_phone",
    password="your_password",
    proxy={
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890",
    }
)
login.login()
```

### 4. Selenium WebDriver 代理配置

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--proxy-server=http://127.0.0.1:7890')

driver = webdriver.Chrome(options=options)
```

### 5. Requests Session 代理配置

```python
import requests

session = requests.Session()
session.proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}

response = session.get('https://www.toutiao.com')
```

## 常用代理软件

### 1. V2Ray / V2RayN

- 下载地址: https://github.com/2dust/v2rayN
- 支持 HTTP、SOCKS5、Shadowsocks 协议

### 2. Clash

- 下载地址: https://github.com/Dreamacro/clash
- 支持 HTTP、SOCKS5、Shadowsocks、VMess 协议

### 3. Surge (macOS)

- 下载地址: https://nssurge.com
- 支持 HTTP、SOCKS5、Shadowsocks 协议

### 4. 小火箭 (iOS)

- App Store: Shadowrocket
- 支持 HTTP、SOCKS5、Shadowsocks、VMess 协议

## 注意事项

1. **代理协议兼容性**: 确保代理软件支持项目所需的协议
2. **代理速度**: 选择延迟低、带宽高的代理节点
3. **Cookie 存储**: 使用代理登录后，Cookie 会保存在本地，后续使用无需代理
4. **本地代理**: 如果代理软件运行在本机，通常使用 `127.0.0.1:7890`

## 故障排除

### 问题: 代理连接失败

**解决方案**:
- 检查代理软件是否正在运行
- 确认代理端口是否正确
- 尝试更换代理节点

### 问题: 证书错误

**解决方案**:
- 安装代理软件的 CA 证书
- 或使用 HTTPS 代理

### 问题: 平台检测到自动化

**解决方案**:
- 降低请求频率
- 使用 Selenium/Playwright 配合代理
- 考虑使用真实的移动端模拟

## Docker 环境代理

如果使用 Docker 运行:

```bash
docker run -e HTTP_PROXY=http://host.docker.internal:7890 \
           -e HTTPS_PROXY=http://host.docker.internal:7890 \
           china-social-tools
```
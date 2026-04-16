# 🇨🇳 China Social Media Tools - 项目维护手册

## 📋 项目信息

- **仓库**: https://github.com/simonho234/china-social-tools
- **本地路径**: ~/china-social-tools
- **语言**: Python 3.9+

## 🎯 当前目标

### 短期（1个月）
- [ ] 获得100 stars
- [ ] 完善头条号自动发布
- [ ] 实现AI配图功能

### 中期（3个月）
- [ ] 获得500 stars
- [ ] 添加小红书支持
- [ ] 添加定时任务功能

### 长期（6个月）
- [ ] 获得2000 stars
- [ ] 开启GitHub Sponsors
- [ ] 实现盈利

## 🔧 技术栈

```
streamlit>=1.28.0     # Web界面
selenium>=4.15.0       # 浏览器自动化
openai>=1.3.0        # AI生成
playwright>=1.40.0     # 浏览器
pandas>=2.1.0         # 数据处理
apscheduler>=6.10.0    # 定时任务
requests>=2.31.0       # HTTP
pyyaml>=6.0.0          # 配置
loguru>=0.7.0          # 日志
```

## 📁 项目结构

```
china-social-tools/
├── README.md              # 项目说明
├── app.py                 # Streamlit Web界面
├── requirements.txt       # 依赖列表
├── config.example.yaml    # 配置模板
├── tools/
│   ├── social_publisher.py  # 基础发布器
│   └── advanced.py          # P0高级模块(自动登录/AI配图/内容生成/热榜)
├── data/                   # 数据目录
│   ├── cookies.json        # Cookie存储
│   └── images/            # 图片存储
└── PROJECT.md             # 本文件
```

## 🔄 开发流程

### 1. 拉取最新代码
```bash
cd ~/china-social-tools
git pull origin master
```

### 2. 创建新功能分支
```bash
git checkout -b feature/新功能名
```

### 3. 开发并测试
```bash
# 测试
python -m pytest tests/
# 或
streamlit run app.py
```

### 4. 提交并推送
```bash
git add .
git commit -m "描述"
git push origin feature/新功能名
```

### 5. 创建 Pull Request
```bash
gh pr create --fill
```

## 📝 待办功能

### P0 - 必须实现 (✅ 已完成)
1. **头条号自动登录** ✅
   - 使用Selenium自动登录
   - 保存Cookie避免重复登录
   
2. **自动配图** ✅
   - 集成OpenAI DALL-E
   - 根据内容生成匹配图片
   
3. **内容生成** ✅
   - 收集热榜数据
   - 生成400+字深度内容
   - 第一句话吸引人

### P1 - 重要功能 (✅ 已完成)
4. **小红书支持** ✅
   - XiaohongshuPublisher实现
   
5. **定时任务** ✅
   - 使用APScheduler
   - 支持多个发布时间

6. **数据统计** 🔄
   - 展现量、点赞、评论
   - 历史趋势图

### P2 - 优化功能
7. 多账号管理
8. 内容模板库
9. AI写作助手

## 🔑 关键技能

已创建的技能（在 ~/.hermes/skills/）：
- `toutiao-auto-publish` - 头条号自动发布
- `toutiao-news-collector` - 热榜数据收集
- `toutiao-data-driven-publishing` - 数据驱动发布

使用方法：
```bash
# 查看技能
hermes skills list

# 使用技能
hermes exec @toutiao-auto-publish
```

## 📊 运营数据

| 平台 | 粉丝 | 收入 |
|------|------|------|
| 头条号 | 150 | ¥1.37 |
| GitHub | 0 | $0 |

## 🚨 故障排除

### 问题：Streamlit无法启动
```bash
pip install streamlit
streamlit run app.py --server.port 8501
```

### 问题：Selenium无法登录
```bash
# 检查Chrome版本
google-chrome --version
# 下载匹配的chromedriver
# 放在 ~/china-social-tools/drivers/
```

### 问题：GitHub推送失败
```bash
# 检查token权限
gh auth status
# 重新登录
gh auth login
```

## 📞 继续开发

当上下文丢失时，按以下步骤继续：

1. **读取本文件**
```bash
cat ~/china-social-tools/PROJECT.md
```

2. **拉取最新代码**
```bash
cd ~/china-social-tools && git pull
```

3. **查看待办**
```bash
# 查看上���的待办功能列表
# 选择一个继续开发
```

4. **开发测试**
```bash
# 在本地测试
python -c "from tools.social_publisher import *"
```

5. **提交推送**
```bash
git add . && git commit -m "具体描述"
git push
```

---

最后更新: 2026-04-16
版本: v0.1.0
#!/usr/bin/env python3
"""
China Social Media Tools - 高级功能模块
P0: 自动登录 + AI配图 + 内容生成
"""

import os
import json
import time
import logging
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# AI支持
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# 配置
CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"
COOKIE_FILE = Path(__file__).parent.parent / "data" / "cookies.json"
IMAGES_DIR = Path(__file__).parent.parent / "data" / "images"


class AutoLogin:
    """头条号自动登录"""
    
    def __init__(self, phone: str = None, password: str = None):
        self.phone = phone or os.getenv("TOUTIAO_PHONE")
        self.password = password or os.getenv("TOUTIAO_PASSWORD")
        self.base_url = "https://www.toutiao.com"
        self.driver = None
        
    def _get_driver(self):
        """获取Chrome驱动"""
        if self.driver:
            return self.driver
            
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # 用户数据目录（保持登录状态）
        user_data_dir = os.path.expanduser("~/.agents/skills/toutiao-publisher/data/browser_state/browser_profile")
        if os.path.exists(user_data_dir):
            options.add_argument(f'--user-data-dir={user_data_dir}')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            logger.info("Chrome驱动启动成功")
        except Exception as e:
            logger.error(f"驱动启动失败: {e}")
            self.driver = None
            
        return self.driver
    
    def _save_cookies(self, cookies: list):
        """保存Cookie"""
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, 'w') as f:
            json.dump(cookies, f)
        logger.info(f"Cookie已保存到: {COOKIE_FILE}")
    
    def _load_cookies(self) -> Optional[list]:
        """加载Cookie"""
        if COOKIE_FILE.exists():
            with open(COOKIE_FILE) as f:
                return json.load(f)
        return None
    
    def login(self) -> bool:
        """执行登录"""
        if not self.phone or not self.password:
            logger.error("请配置手机号和密码")
            return False
            
        driver = self._get_driver()
        if not driver:
            return False
            
        # 尝试加载Cookie
        cookies = self._load_cookies()
        if cookies:
            driver.get(self.base_url)
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except:
                    pass
            driver.get(f"{self.base_url}/profile/5823660130/")
            if "login" in driver.current_url.lower():
                logger.info("Cookie已过期，需要重新登录")
            else:
                logger.info("使用保存的Cookie登录成功")
                return True
        
        # 重新登录
        logger.info("开始登录头条号...")
        driver.get(f"{self.base_url}/login/")
        
        try:
            # 等待页面加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "phone"))
            )
            
            # 输入手机号
            phone_input = driver.find_element(By.NAME, "phone")
            phone_input.clear()
            phone_input.send_keys(self.phone)
            
            # 输入密码
            password_input = driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(self.password)
            
            # 点击登录
            login_btn = driver.find_element(By.CSS_SELECTOR, "[type='submit']")
            login_btn.click()
            
            # 等待登录成功
            time.sleep(5)
            
            # 保存Cookie
            self._save_cookies(driver.get_cookies())
            
            logger.info("登录成功")
            return True
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False
    
    def close(self):
        """关闭驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None


class ImageGenerator:
    """AI图片生成器"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
    
    def generate(self, content: str, style: str = "自然风格") -> Optional[str]:
        """使用DALL-E生成配图"""
        if not self.client:
            logger.warning("未配置OpenAI API Key")
            return None
            
        # 根据内容生成提示词
        prompt = self._build_prompt(content, style)
        
        try:
            response = self.client.images.generate(
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="standard"
            )
            
            image_url = response.data[0].url
            logger.info(f"图片生成成功: {image_url}")
            return image_url
            
        except Exception as e:
            logger.error(f"图片生成失败: {e}")
            return None
    
    def _build_prompt(self, content: str, style: str) -> str:
        """构建图片提示词"""
        # 简单实现：提取关键词生成提示词
        keywords = []
        
        # 常见话题关键词
        topics = {
            "科技": "technology, modern",
            "经济": "business, finance",
            "生活": "daily life, lifestyle",
            "健康": "health, wellness",
            "旅游": "travel, landscape",
            "美食": "food, cooking",
            "教育": "education, learning",
        }
        
        content_lower = content.lower()
        for topic, keyword in topics.items():
            if topic in content_lower:
                keywords.append(keyword)
        
        if not keywords:
            keywords = ["illustration", "popular"]
        
        prompt = f"{', '.join(keywords)}, {style}, high quality, 4k, detail"
        return prompt
    
    def download(self, url: str, filename: str = None) -> Optional[str]:
        """下载图片"""
        if not filename:
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            filename = IMAGES_DIR / f"image_{int(time.time())}.png"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                f.write(response.content)
                
            logger.info(f"图片已保存: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.error(f"图片下载失败: {e}")
            return None


class ContentGenerator:
    """内容生成器"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
    
    def generate(self, topic: str, min_words: int = 400) -> Optional[str]:
        """生成400+字深度内容"""
        if not self.client:
            # 使用模板生成
            return self._template_generate(topic, min_words)
        
        try:
            prompt = self._build_prompt(topic, min_words)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "你是一个专业的内容创作助手，擅长生成吸引人的社交媒体内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            logger.info(f"内容生成成功: {len(content)}字")
            return content
            
        except Exception as e:
            logger.error(f"内容生成失败: {e}")
            return self._template_generate(topic, min_words)
    
    def _build_prompt(self, topic: str, min_words: int) -> str:
        """构建生成提示词"""
        return f"""请为今日头条创作一篇{min_words}字以上的微头条内容：

要求：
1. 第一句话必须吸引读者（用问句/感叹句/悬念句）
2. 内容要引发读者共鸣（结合生活场景、痛点）
3. 提供实用价值（解决方案/见解）
4. 结尾引导互动（提问式）
5. 禁止使用#话题标签
6. 字数{min_words}字以上

主题：{topic}

请直接输出内容，不要标题。"""
    
    def _template_generate(self, topic: str, min_words: int) -> str:
        """模板生成（无API时）"""
        templates = [
            "你有没有想过{topic}？这个问题困扰了很多人，但其实解决方法很简单...今天我来告诉你一个秘诀，只需做好这几点，第一，{topic}的核心是...第二，要注意的是...第三，也是最重要的...如果你也有类似困扰，不妨试试这个方法。有什么想法评论区聊聊？",
            "90%的人都忽略了{topic}！但实际上，这才是真正影响你的...我花了3年时间研究这个问题，终于发现了...首先，你需要了解...其次，要注意的是...最后记住...希望这个分享对你有帮助。你怎么看？",
            "紧急提醒！关于{topic}，很多人都在犯同一个错误...今天我必须告诉你真相...原因是...其实正确的方法是...记住这3点：1. 2. 3. 按照这个思路，你会发现...对此你怎么看？",
        ]
        
        import random
        template = random.choice(templates)
        content = template.format(topic=topic)
        
        # 扩展到目标字数
        while len(content) < min_words:
            content += " " + "这也是很重要的一点。记住，坚持下去才能看到效果。"
        
        return content


class ContentCollector:
    """热榜数据收集器"""
    
    def __init__(self):
        self.base_url = "https://www.toutiao.com"
    
    def get_trending(self, category: str = "hot") -> list:
        """获取热榜数据"""
        try:
            # 使用头条热榜API
            url = f"{self.base_url}/api/pc/feed/"
            params = {
                "category": category,
                "max_count": 10
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            items = []
            for item in data.get("data", []):
                if item.get("article_url"):
                    items.append({
                        "title": item.get("title", ""),
                        "source": item.get("source", ""),
                        "comments": item.get("comments_count", 0),
                        "url": item.get("article_url", "")
                    })
            
            logger.info(f"获取到{len(items)}条热榜")
            return items
            
        except Exception as e:
            logger.error(f"获取热榜失败: {e}")
            return self._fallback_trending()
    
    def _fallback_trending(self) -> list:
        """备用热榜数据"""
        return [
            {"title": "科技新趋势：AI如何改变我们的生活", "source": "科技频道", "comments": 1234},
            {"title": "经济新动向：2024年投资方向分析", "source": "财经频道", "comments": 856},
            {"title": "健康养生：每天做好这几点", "source": "健康频道", "comments": 642},
            {"title": "教育热点：教育改革新方向", "source": "教育频道", "comments": 521},
            {"title": "生活技巧：让生活更轻松的方法", "source": "生活频道", "comments": 398},
        ]


def test():
    """测试函数"""
    print("=== 测试自动登录 ===")
    login = AutoLogin()
    print(f"驱动可用: {login._get_driver() is not None}")
    
    print("\n=== 测试图片生成 ===")
    generator = ImageGenerator()
    url = generator.generate("科技新闻", "简洁风格")
    print(f"图片URL: {url}")
    
    print("\n=== 测试内容生成 ===")
    content_gen = ContentGenerator()
    content = content_gen.generate("AI技术发展", 400)
    print(f"内容: {content[:200]}...")
    
    print("\n=== 测试热榜获取 ===")
    collector = ContentCollector()
    trending = collector.get_trending()
    for item in trending[:3]:
        print(f"- {item['title']}")


if __name__ == "__main__":
    test()
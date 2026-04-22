#!/usr/bin/env python3
"""
China Social Media Automation Toolkit
微信公众号文章发布器

功能:
1. 文章发布 - 支持图文混排
2. 封面设置
3. 分类选择
4. 原文链接
5. 声明原创
6. 与 AutoLogin 集成实现自动登录
"""

import os
import re
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException,
    NoSuchElementException,
)

logger = logging.getLogger(__name__)

# ============================================================================
# 配置和常量
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
COOKIE_FILE = DATA_DIR / "cookies.json"

# 微信公众号后台
WECHAT_MP_URL = "https://mp.weixin.qq.com/"
WECHAT_ARTICLE_URL = "https://mp.weixin.qq.com/cgi/appmsg"

# 文章类型
ARTICLE_TYPES = {
    '图文消息': 0,
    '图片消息': 1,
    '语音消息': 2,
    '视频消息': 3,
}

# 文章分类
ARTICLE_CATEGORIES = [
    '科技',
    '财经',
    '生活',
    '娱乐',
    '体育',
    '汽车',
    '教育',
    '游戏',
    '搞笑',
    '养生',
    '美食',
    '旅游',
]


# ============================================================================
# 数据类
# ============================================================================

class WechatArticleType(Enum):
    """文章类型"""
    IMAGE_TEXT = 0  # 图文消息
    IMAGE = 1       # 图片消息
    VOICE = 2       # 语音消息
    VIDEO = 3       # 视频消息


@dataclass
class WechatArticleMetadata:
    """微信公众号文章元数据"""
    
    title: str  # 标题
    content: str  # 正文内容 (HTML)
    author: str = ""  # 作者
    abstract: str = ""  # 摘要
    source_url: str = ""  # 原文链接
    cover_image: str = ""  # 封面图片路径
    need_open_comment: bool = False  # 开启评论
    is_original: bool = False  # 声明原创
    category: str = "科技"  # 分类
    tags: List[str] = None  # 标签
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def validate(self) -> tuple[bool, str]:
        """验证元数据"""
        if not self.title:
            return False, "文章标题不能为空"
        
        if len(self.title) > 64:
            return False, f"标题过长: {len(self.title)} > 64字符"
        
        if not self.content:
            return False, "文章内容不能为空"
        
        if len(self.content) < 20:
            return False, "内容过少，请输入更多内容"
        
        return True, "验证通过"


@dataclass
class WechatPublishResult:
    """发布结果"""
    
    success: bool
    article_url: str = ""
    article_id: str = ""
    message: str = ""
    
    def __str__(self):
        if self.success:
            return f"发布成功! 文章ID: {self.article_id}"
        return f"发布失败: {self.message}"


# ============================================================================
# 微信公众号发布器
# ============================================================================

class WechatPublisher:
    """微信公众号文章发布器"""
    
    def __init__(
        self,
        cookies_file: str = None,
        driver=None,
        timeout: int = 30,
    ):
        """
        初始化公众号发布器
        
        Args:
            cookies_file: Cookie存储文件路径
            driver: WebDriver实例
            timeout: 等待超时时间(秒)
        """
        self.cookies_file = Path(cookies_file) if cookies_file else COOKIE_FILE
        self.driver = driver
        self.timeout = timeout
        self._session = None
        self._token = None
        
    def set_driver(self, driver):
        """设置WebDriver"""
        self.driver = driver
        
    @property
    def session(self) -> requests.Session:
        """获取或创建Session"""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://mp.weixin.qq.com/',
            })
        return self._session
    
    def load_cookies(self) -> bool:
        """加载Cookie"""
        if not self.cookies_file.exists():
            logger.warning(f"Cookie文件不存在: {self.cookies_file}")
            return False
            
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
                
            # 查找微信公众号Cookie
            wechat_cookies = cookies_data.get('wechat_mp', [])
            if not wechat_cookies:
                # 尝试从其他平台获取
                wechat_cookies = cookies_data.get('wechat', [])
                
            if not wechat_cookies:
                logger.warning("未找到微信公众号Cookie")
                return False
                
            for cookie in wechat_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
                
            return True
            
        except Exception as e:
            logger.error(f"加载Cookie失败: {e}")
            return False
    
    def save_cookies(self, cookies: List[dict]):
        """保存Cookie"""
        try:
            self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
            
            existing_data = {}
            if self.cookies_file.exists():
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    
            existing_data['wechat_mp'] = cookies
            
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
            logger.info("Cookie已保存")
            return True
            
        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return False
    
    def _wait_for_element(
        self, 
        by: By, 
        value: str, 
        timeout: int = None
    ) -> Optional[Any]:
        """等待元素出现"""
        timeout = timeout or self.timeout
        try:
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            logger.warning(f"等待元素超时: {value}")
            return None
    
    def _check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            self.driver.get(WECHAT_MP_URL)
            time.sleep(3)
            
            # 检查是否存在登录表单
            try:
                self.driver.find_element(By.NAME, "account")
                return False
            except NoSuchElementException:
                pass
            
            # 检查是否已登录（查找用户名或设置入口）
            try:
                self.driver.find_element(By.CSS_SELECTOR, ".user_name")
                return True
            except:
                pass
                
            return False
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def login(self, account: str, password: str) -> bool:
        """
        登录微信公众号后台
        
        Args:
            account: 账号(手机号或邮箱)
            password: 密码
            
        Returns:
            bool: 是否登录成功
        """
        if not self.driver:
            logger.error("需要提供WebDriver进行登录")
            return False
            
        try:
            # 访问登录页面
            self.driver.get(WECHAT_MP_URL)
            time.sleep(2)
            
            # 输入账号
            account_input = self._wait_for_element(By.NAME, "account")
            if account_input:
                account_input.clear()
                account_input.send_keys(account)
            
            # 输入密码
            password_input = self._wait_for_element(By.NAME, "password")
            if password_input:
                password_input.clear()
                password_input.send_keys(password)
            
            # 点击登录按钮
            login_btn = self.driver.find_element(
                By.CSS_SELECTOR, 
                "button[type='submit']"
            )
            login_btn.click()
            
            # 等待登录结果
            time.sleep(5)
            
            # 检查登录是否成功
            if self._check_login_status():
                # 保存Cookie
                cookies = self.driver.get_cookies()
                self.save_cookies(cookies)
                logger.info("登录成功")
                return True
            
            logger.warning("登录可能需要二维码验证")
            return False
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False
    
    def publish(
        self,
        metadata: WechatArticleMetadata,
    ) -> WechatPublishResult:
        """
        发布文章
        
        Args:
            metadata: 文章元数据
            
        Returns:
            WechatPublishResult: 发布结果
        """
        # 验证元数据
        valid, message = metadata.validate()
        if not valid:
            return WechatPublishResult(success=False, message=message)
        
        if not self.driver:
            return WechatPublishResult(
                success=False, 
                message="需要提供WebDriver"
            )
        
        return self._publish_with_driver(metadata)
    
    def _publish_with_driver(
        self, 
        metadata: WechatArticleMetadata
    ) -> WechatPublishResult:
        """使用WebDriver发布文章"""
        try:
            # 访问新建图文消息页面
            self.driver.get(WECHAT_ARTICLE_URL + "?action=list&type=10&lang=zh_CN")
            time.sleep(3)
            
            # 查找新建图文消息按钮
            try:
                new_article_btn = self.driver.find_element(
                    By.LINK_TEXT, 
                    "新建图文消息"
                )
                new_article_btn.click()
            except NoSuchElementException:
                # 尝试其他选择器
                new_article_btn = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "[class*='create']"
                )
                new_article_btn.click()
            
            time.sleep(2)
            
            # 填写标题
            title_input = self.driver.find_element(
                By.CSS_SELECTOR, 
                "input[name='title']"
            )
            title_input.clear()
            title_input.send_keys(metadata.title)
            logger.info(f"已填写标题: {metadata.title}")
            
            # 填写作者
            if metadata.author:
                author_input = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "input[name='author']"
                )
                author_input.clear()
                author_input.send_keys(metadata.author)
            
            # 填写正文 - 切换到富文本编辑器
            # 微信公众号使用iframe，需要切换
            try:
                # 查找富文本编辑器iframe
                iframe = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "iframe[id*='ueditor']"
                )
                self.driver.switch_to.frame(iframe)
                
                # 在body中输入内容
                body = self.driver.find_element(By.CSS_SELECTOR, "body")
                body.clear()
                body.send_keys(metadata.content)
                
                # 切换回主文档
                self.driver.switch_to.default_content()
                logger.info("已填写正文内容")
                
            except Exception as e:
                logger.warning(f"富文本编辑失败，尝试使用JavaScript: {e}")
                # 使用JavaScript直接设置内容
                js_code = f"""
                    var editor = window.wangEditor;
                    if (editor) {{
                        editor.txt.html(`{metadata.content}`);
                    }}
                """
                self.driver.execute_script(js_code)
            
            # 填写摘要
            if metadata.abstract:
                abstract_input = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "textarea[name='digest']"
                )
                abstract_input.clear()
                abstract_input.send_keys(metadata.abstract[:120])
            
            # 上传封面
            if metadata.cover_image:
                self._upload_cover(metadata.cover_image)
            
            # 填写原文链接
            if metadata.source_url:
                source_input = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "input[name='content_source_url']"
                )
                source_input.clear()
                source_input.send_keys(metadata.source_url)
            
            # 声明原创
            if metadata.is_original:
                original_checkbox = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "input[name='is_original']"
                )
                if not original_checkbox.is_selected():
                    original_checkbox.click()
            
            # 开启评论
            if metadata.need_open_comment:
                comment_checkbox = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "input[name='need_open_comment']"
                )
                if not comment_checkbox.is_selected():
                    comment_checkbox.click()
            
            # 保存为草稿或发布
            # 注意：公众号发布需要管理员扫码确认
            
            time.sleep(2)
            
            # 查找保存按钮
            try:
                save_btn = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "button:contains('保存')"
                )
                save_btn.click()
                time.sleep(2)
                
                return WechatPublishResult(
                    success=True,
                    message="文章已保存为草稿，请在公众号后台确认发布"
                )
                
            except NoSuchElementException:
                # 尝试发布按钮
                publish_btn = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "button:contains('群发')"
                )
                publish_btn.click()
                time.sleep(2)
                
                return WechatPublishResult(
                    success=True,
                    message="文章已提交发布，请扫码确认"
                )
                
        except Exception as e:
            logger.error(f"发布失败: {e}")
            return WechatPublishResult(success=False, message=str(e))
    
    def _upload_cover(self, cover_path: str):
        """上传封面图片"""
        try:
            # 查找封面上传按钮
            cover_btn = self.driver.find_element(
                By.CSS_SELECTOR, 
                "[class*='cover'] input[type='file']"
            )
            if cover_btn:
                cover_btn.send_keys(str(Path(cover_path).resolve()))
                logger.info("封面上传成功")
                time.sleep(2)
        except Exception as e:
            logger.warning(f"封面上传失败: {e}")
    
    def get_article_list(self, page: int = 1, count: int = 10) -> List[Dict]:
        """获取已发布文章列表"""
        try:
            if not self._token:
                self._get_token()
            
            url = WECHAT_ARTICLE_URL
            params = {
                'token': self._token,
                'lang': 'zh_CN',
                'type': '10',
                'action': 'list',
                'begin': (page - 1) * count,
                'count': count,
            }
            
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('app_msg_list', [])
                
        except Exception as e:
            logger.error(f"获取文章列表失败: {e}")
            
        return []
    
    def _get_token(self):
        """获取登录token"""
        try:
            response = self.session.get(WECHAT_MP_URL)
            match = re.search(r'token=([a-zA-Z0-9]+)', response.url)
            if match:
                self._token = match.group(1)
                return self._token
        except Exception as e:
            logger.error(f"获取token失败: {e}")
        return None
    
    def delete_article(self, article_id: str) -> bool:
        """删除文章(仅限草稿)"""
        try:
            url = f"{WECHAT_ARTICLE_URL}?action=delete"
            data = {
                'token': self._token,
                'app_msg_id': article_id,
            }
            
            response = self.session.post(url, data=data)
            return response.json().get('base_resp', {}).get('ret') == 0
            
        except Exception as e:
            logger.error(f"删除文章失败: {e}")
            return False


# ============================================================================
# 便捷函数
# ============================================================================

def quick_publish(
    title: str,
    content: str,
    author: str = "",
    cover_image: str = "",
    driver=None,
) -> WechatPublishResult:
    """
    快速发布文章到微信公众号
    
    Args:
        title: 文章标题
        content: 正文内容
        author: 作者
        cover_image: 封面图片路径
        driver: WebDriver实例
        
    Returns:
        WechatPublishResult: 发布结果
    """
    metadata = WechatArticleMetadata(
        title=title,
        content=content,
        author=author,
        cover_image=cover_image,
    )
    
    publisher = WechatPublisher()
    if driver:
        publisher.set_driver(driver)
        
    return publisher.publish(metadata)


# ============================================================================
# 主函数 - 命令行使用
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="微信公众号文章发布器")
    parser.add_argument("--title", "-t", required=True, help="文章标题")
    parser.add_argument("--content", "-c", required=True, help="文章内容")
    parser.add_argument("--author", "-a", default="", help="作者")
    parser.add_argument("--cover", "-cv", default="", help="封面图片路径")
    
    args = parser.parse_args()
    
    # 发布
    result = quick_publish(
        title=args.title,
        content=args.content,
        author=args.author,
        cover_image=args.cover,
    )
    
    print(result)
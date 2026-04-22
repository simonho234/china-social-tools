#!/usr/bin/env python3
"""
China Social Media Automation Toolkit
B站(Bilibili)视频上传器 - 支持视频自动发布

功能:
1. 视频上传 - 支持 mp4, avi, mov 格式
2. 标题和描述自动生成
3. 标签管理
4. 封面设置
5. 分区选择
6. 与 AutoLogin 集成实现自动登录
"""

import os
import re
import time
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException,
    NoSuchElementException,
    ElementNotInteractableException
)

logger = logging.getLogger(__name__)

# ============================================================================
# 配置和常量
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
VIDEO_DIR = DATA_DIR / "videos"
COOKIE_FILE = DATA_DIR / "cookies.json"

# B站上传页面
BILIBILI_UPLOAD_URL = "https://member.bilibili.com/v2#/upload"
BILIBILI_MANAGE_URL = "https://member.bilibili.com/video/manage"

# 视频限制
VIDEO_MAX_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
VIDEO_MIN_DURATION = 1  # 最小1秒
VIDEO_MAX_DURATION = 60 * 60  # 最大60分钟
SUPPORTED_FORMATS = ['mp4', 'avi', 'mov', 'mkv', 'flv']

# 视频分区映射
VIDEO_CATEGORIES = {
    '生活': {
        '日常': 160,
        '手工': 138,
        '绘画': 171,
    },
    '游戏': {
        '单机游戏': 17,
        '电子竞技': 171,
        '手机游戏': 171,
    },
    '科技': {
        '数码': 95,
        '计算机': 172,
        '软件': 173,
    },
    '娱乐': {
        '明星': 5,
        '综艺': 17,
        'Music': 31,
    },
    '知识': {
        '职场': 150,
        '校园': 152,
        '野生技术协会': 153,
    },
    '资讯': {
        '热点': 203,
        '国际': 204,
    },
}

# 上传相关选择器
UPLOAD_SELECTORS = {
    'upload_button': [
        '.upload-btn',
        '.upload-button',
        'button:contains("上传视频")',
        'input[type="file"]',
    ],
    'title_input': [
        'input[placeholder*="标题"]',
        'input[name="title"]',
        '.video-title input',
    ],
    'description_input': [
        'textarea[placeholder*="简介"]',
        'textarea[name="desc"]',
        '.video-desc textarea',
    ],
    'tag_input': [
        'input[placeholder*="标签"]',
        'input[name="tag"]',
        '.video-tag input',
    ],
    'cover_upload': [
        '.cover-upload',
        'button:contains("上传封面")',
    ],
    'category_select': [
        'select[name="tid"]',
        '.category-select',
    ],
    'submit_button': [
        '.submit-btn',
        'button:contains("发布")',
        'button[type="submit"]',
    ],
}


# ============================================================================
# 数据类
# ============================================================================

class VideoCopyright(Enum):
    ORIGINAL = 1  # 原创
    REPOST = 2   # 转载


class VideoSource(Enum):
    """视频来源"""
    ORIGINAL = "original"  # 原创
    REPOST = "repost"      # 转载


class BilibiliVideoMetadata:
    """B站视频元数据"""
    
    def __init__(
        self,
        file_path: str,
        title: str,
        description: str = "",
        tags: List[str] = None,
        cover_path: str = None,
        category: str = "生活",
        sub_category: str = "日常",
        copyright: VideoCopyright = VideoCopyright.ORIGINAL,
        source: str = "",
        duration: int = 0,
    ):
        self.file_path = file_path
        self.title = title[:80]  # B站标题最大80字符
        self.description = description[:200]  # 简介最大200字符
        self.tags = tags or []
        self.cover_path = cover_path
        self.category = category
        self.sub_category = sub_category
        self.copyright = copyright
        self.source = source
        self.duration = duration
        
    def validate(self) -> tuple[bool, str]:
        """验证元数据"""
        path = Path(self.file_path)
        if not path.exists():
            return False, f"视频文件不存在: {self.file_path}"
        
        if path.stat().st_size > VIDEO_MAX_SIZE:
            return False, f"视频文件过大: {path.stat().st_size / 1024 / 1024:.0f}MB > 4GB"
        
        ext = path.suffix.lower().lstrip('.')
        if ext not in SUPPORTED_FORMATS:
            return False, f"不支持的视频格式: {ext}"
        
        if not self.title:
            return False, "视频标题不能为空"
            
        if len(self.tags) > 12:
            return False, f"标签数量过多: {len(self.tags)} > 12"
            
        return True, "验证通过"


class BilibiliUploadResult:
    """B站上传结果"""
    
    def __init__(
        self,
        success: bool,
        video_id: str = "",
        video_url: str = "",
        message: str = "",
        bvid: str = "",
        aid: int = 0,
    ):
        self.success = success
        self.video_id = video_id
        self.video_url = video_url
        self.message = message
        self.bvid = bvid
        self.aid = aid
        
    def __str__(self):
        if self.success:
            return f"上传成功! BVID: {self.bvid}, URL: {self.video_url}"
        return f"上传失败: {self.message}"


# ============================================================================
# B站视频上传器
# ============================================================================

class BilibiliUploader:
    """B站视频上传器"""
    
    def __init__(
        self,
        cookies_file: str = None,
        driver=None,
        timeout: int = 30,
    ):
        """
        初始化B站上传器
        
        Args:
            cookies_file: Cookie存储文件路径
            driver: WebDriver实例
            timeout: 等待超时时间(秒)
        """
        self.cookies_file = Path(cookies_file) if cookies_file else COOKIE_FILE
        self.driver = driver
        self.timeout = timeout
        self._session = None
        
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
                'Referer': 'https://www.bilibili.com',
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
                
            # 查找B站Cookie
            bilibili_cookies = cookies_data.get('bilibili', [])
            if not bilibili_cookies:
                bilibili_cookies = cookies_data.get('douyin', [])
                
            if not bilibili_cookies:
                logger.warning("未找到B站Cookie")
                return False
                
            # 添加到session
            for cookie in bilibili_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
                
            return True
            
        except Exception as e:
            logger.error(f"加载Cookie失败: {e}")
            return False
    
    def save_cookies(self, cookies: List[dict]):
        """保存Cookie"""
        try:
            self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有数据
            existing_data = {}
            if self.cookies_file.exists():
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    
            # 更新B站Cookie
            existing_data['bilibili'] = cookies
            
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
    
    def _find_element_by_selectors(
        self, 
        selectors: List[str],
        by: By = By.CSS_SELECTOR
    ) -> Optional[Any]:
        """尝试多个选择器查找元素"""
        for selector in selectors:
            try:
                element = self.driver.find_element(by, selector)
                if element and element.is_displayed():
                    return element
            except NoSuchElementException:
                continue
        return None
    
    def upload(
        self,
        metadata: BilibiliVideoMetadata,
        cover_path: str = None,
    ) -> BilibiliUploadResult:
        """
        上传视频
        
        Args:
            metadata: 视频元数据
            cover_path: 封面图片路径(可选)
            
        Returns:
            BilibiliUploadResult: 上传结果
        """
        # 验证元数据
        valid, message = metadata.validate()
        if not valid:
            return BilibiliUploadResult(success=False, message=message)
        
        # 使用WebDriver上传
        if self.driver:
            return self._upload_with_driver(metadata, cover_path)
        else:
            return self._upload_with_api(metadata, cover_path)
    
    def _upload_with_driver(
        self, 
        metadata: BilibiliVideoMetadata,
        cover_path: str = None,
    ) -> BilibiliUploadResult:
        """使用WebDriver上传视频"""
        try:
            # 访问上传页面
            self.driver.get(BILIBILI_UPLOAD_URL)
            time.sleep(2)
            
            # 检查登录状态
            if not self._check_login_status():
                return BilibiliUploadResult(
                    success=False, 
                    message="未登录，请先登录B站"
                )
            
            # 点击上传按钮 - 查找文件输入框
            file_input = self._find_element_by_selectors(
                UPLOAD_SELECTORS['upload_button']
            )
            
            if not file_input:
                # 尝试直接找到input[type="file"]
                file_input = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    'input[type="file"]'
                )
            
            if file_input:
                # 上传视频文件
                abs_path = str(Path(metadata.file_path).resolve())
                file_input.send_keys(abs_path)
                logger.info(f"已选择视频: {abs_path}")
                
                # 等待上传完成
                time.sleep(5)
                
                # 填写标题
                title_input = self._find_element_by_selectors(
                    UPLOAD_SELECTORS['title_input']
                )
                if title_input:
                    title_input.clear()
                    title_input.send_keys(metadata.title)
                    
                # 填写简介
                desc_input = self._find_element_by_selectors(
                    UPLOAD_SELECTORS['description_input']
                )
                if desc_input:
                    desc_input.clear()
                    desc_input.send_keys(metadata.description)
                    
                # 填写标签
                tag_input = self._find_element_by_selectors(
                    UPLOAD_SELECTORS['tag_input']
                )
                if tag_input and metadata.tags:
                    for tag in metadata.tags[:5]:  # 最多5个标签
                        tag_input.send_keys(tag)
                        tag_input.send_keys(Keys.ENTER)
                        time.sleep(0.3)
                
                # 上传封面
                if cover_path or metadata.cover_path:
                    cover_file = cover_path or metadata.cover_path
                    self._upload_cover(cover_file)
                
                # 选择分区
                self._select_category(metadata.category, metadata.sub_category)
                
                # 点击发布按钮
                submit_btn = self._find_element_by_selectors(
                    UPLOAD_SELECTORS['submit_button']
                )
                if submit_btn:
                    submit_btn.click()
                    time.sleep(3)
                    
                    # 获取视频信息
                    bvid = self._get_current_bvid()
                    if bvid:
                        return BilibiliUploadResult(
                            success=True,
                            video_id=bvid,
                            bvid=bvid,
                            video_url=f"https://www.bilibili.com/video/{bvid}",
                            message="上传成功"
                        )
                
                return BilibiliUploadResult(
                    success=True,
                    message="视频已提交审核"
                )
            else:
                return BilibiliUploadResult(
                    success=False,
                    message="找不到上传入口"
                )
                
        except Exception as e:
            logger.error(f"WebDriver上传失败: {e}")
            return BilibiliUploadResult(success=False, message=str(e))
    
    def _upload_cover(self, cover_path: str):
        """上传封面图片"""
        try:
            cover_btn = self._find_element_by_selectors(
                UPLOAD_SELECTORS['cover_upload']
            )
            if cover_btn:
                cover_btn.click()
                time.sleep(1)
                
                # 查找封面输入框
                file_input = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    'input[type="file"][accept*="image"]'
                )
                if file_input:
                    file_input.send_keys(str(Path(cover_path).resolve()))
                    logger.info("封面上传成功")
                    time.sleep(2)
        except Exception as e:
            logger.warning(f"封面上传失败: {e}")
    
    def _select_category(self, category: str, sub_category: str):
        """选择视频分区"""
        try:
            category_select = self._find_element_by_selectors(
                UPLOAD_SELECTORS['category_select']
            )
            if category_select:
                # 展开下拉框
                category_select.click()
                time.sleep(0.5)
                
                # 选择主分区
                category_key = VIDEO_CATEGORIES.get(category, {})
                if category_key:
                    tid = category_key.get(sub_category, 160)
                    # 选择子分区
                    option = self.driver.find_element(
                        By.CSS_SELECTOR, 
                        f'option[value="{tid}"]'
                    )
                    if option:
                        option.click()
                        logger.info(f"已选择分区: {category} > {sub_category}")
        except Exception as e:
            logger.warning(f"分区选择失败: {e}")
    
    def _check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            # 检查是否存在登录按钮或用户头像
            self.driver.get("https://www.bilibili.com")
            time.sleep(2)
            
            # 尝试找到用户头像或登录按钮
            try:
                self.driver.find_element(By.CSS_SELECTOR, '.header-avatar')
                return True
            except:
                try:
                    self.driver.find_element(By.LINK_TEXT, "登录")
                    return False
                except:
                    return False
        except:
            return False
    
    def _get_current_bvid(self) -> str:
        """获取当前上传视频的BVID"""
        try:
            # 从URL获取
            current_url = self.driver.current_url
            if 'bilibili.com/video/' in current_url:
                match = re.search(r'BV[\w]+', current_url)
                if match:
                    return match.group()
                    
            # 从页面元素获取
            bvid_elem = self.driver.find_element(
                By.CSS_SELECTOR, 
                '[class*="bvid"]'
            )
            return bvid_elem.text if bvid_elem else ""
        except:
            return ""
    
    def _upload_with_api(
        self, 
        metadata: BilibiliVideoMetadata,
        cover_path: str = None,
    ) -> BilibiliUploadResult:
        """使用API上传视频(需要Cookie)"""
        # B站的API上传需要复杂的multipart流程
        # 这里提供基础框架，实际使用WebDriver更可靠
        logger.info("API上传需要完整的Cookie认证，建议使用WebDriver模式")
        
        # 尝试加载Cookie并使用上传接口
        if self.load_cookies():
            try:
                # 预上传请求获取上传信息
                preupload_url = "https://member.bilibili.com/preupload"
                params = {
                    'name': Path(metadata.file_path).name,
                    'size': Path(metadata.file_path).stat().st_size,
                    'r': 'upos',
                    'profile': 'ugcupos/bup',
                    'ssl': 0,
                    'version': '2.14.0',
                    'build': 2140000,
                    'upcdn': 'bda2',
                    'probe_range': 1,
                }
                
                response = self.session.get(preupload_url, params=params)
                if response.status_code == 200:
                    upload_info = response.json()
                    logger.info(f"预上传成功: {upload_info}")
                    
                    # 实际文件上传需要分片上传
                    # 这里省略具体实现
                    
                return BilibiliUploadResult(
                    success=False,
                    message="API上传需要更多配置，建议使用WebDriver模式"
                )
                
            except Exception as e:
                logger.error(f"API上传失败: {e}")
                return BilibiliUploadResult(success=False, message=str(e))
        
        return BilibiliUploadResult(
            success=False,
            message="请提供有效的Cookie或使用WebDriver"
        )
    
    def upload_batch(
        self,
        videos: List[BilibiliVideoMetadata],
        delay: int = 10,
    ) -> List[BilibiliUploadResult]:
        """
        批量上传视频
        
        Args:
            videos: 视频元数据列表
            delay: 两次上传间隔(秒)
            
        Returns:
            List[BilibiliUploadResult]: 上传结果列表
        """
        results = []
        
        for i, metadata in enumerate(videos):
            logger.info(f"上传第 {i+1}/{len(videos)} 个视频: {metadata.title}")
            
            result = self.upload(metadata)
            results.append(result)
            
            if i < len(videos) - 1:
                logger.info(f"等待 {delay} 秒后继续...")
                time.sleep(delay)
                
        return results
    
    def get_video_list(self) -> List[Dict]:
        """获取已上传视频列表"""
        try:
            self.driver.get(BILIBILI_MANAGE_URL)
            time.sleep(2)
            
            videos = []
            # 查找视频列表元素
            video_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                '[class*="video-item"]'
            )
            
            for elem in video_elements:
                try:
                    title = elem.find_element(
                        By.CSS_SELECTOR, 
                        '[class*="title"]'
                    ).text
                    bvid = elem.get_attribute('data-bvid')
                    status = elem.find_element(
                        By.CSS_SELECTOR, 
                        '[class*="status"]'
                    ).text
                    
                    videos.append({
                        'title': title,
                        'bvid': bvid,
                        'status': status,
                        'url': f"https://www.bilibili.com/video/{bvid}" if bvid else ""
                    })
                except:
                    continue
                    
            return videos
            
        except Exception as e:
            logger.error(f"获取视频列表失败: {e}")
            return []
    
    def delete_video(self, bvid: str) -> bool:
        """删除视频"""
        try:
            self.driver.get(f"{BILIBILI_MANAGE_URL}?bvid={bvid}")
            time.sleep(2)
            
            # 查找删除按钮
            delete_btn = self.driver.find_element(
                By.CSS_SELECTOR, 
                '[class*="delete"]'
            )
            delete_btn.click()
            time.sleep(1)
            
            # 确认删除
            confirm_btn = self.driver.find_element(
                By.CSS_SELECTOR, 
                'button:contains("确认")'
            )
            confirm_btn.click()
            
            logger.info(f"视频 {bvid} 已删除")
            return True
            
        except Exception as e:
            logger.error(f"删除视频失败: {e}")
            return False


# ============================================================================
# 便捷函数
# ============================================================================

def quick_upload(
    video_path: str,
    title: str,
    description: str = "",
    tags: List[str] = None,
    driver=None,
) -> BilibiliUploadResult:
    """
    快速上传视频到B站
    
    Args:
        video_path: 视频文件路径
        title: 视频标题
        description: 视频描述
        tags: 标签列表
        driver: WebDriver实例
        
    Returns:
        BilibiliUploadResult: 上传结果
    """
    metadata = BilibiliVideoMetadata(
        file_path=video_path,
        title=title,
        description=description,
        tags=tags,
    )
    
    uploader = BilibiliUploader()
    if driver:
        uploader.set_driver(driver)
        
    return uploader.upload(metadata)


# ============================================================================
# 主函数 - 命令行使用
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="B站视频上传器")
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("--title", "-t", required=True, help="视频标题")
    parser.add_argument("--desc", "-d", default="", help="视频描述")
    parser.add_argument("--tags", "-g", nargs="+", help="视频标签")
    
    args = parser.parse_args()
    
    # 创建元数据
    metadata = BilibiliVideoMetadata(
        file_path=args.video,
        title=args.title,
        description=args.desc,
        tags=args.tags or [],
    )
    
    # 上传
    uploader = BilibiliUploader()
    result = uploader.upload(metadata)
    
    print(result)
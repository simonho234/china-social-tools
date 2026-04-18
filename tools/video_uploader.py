#!/usr/bin/env python3
"""
China Social Media Automation Toolkit
抖音视频上传器 - 支持视频自动发布

功能:
1. 视频上传 - 支持 mp4, mov, avi 格式
2. 标题和描述自动生成
3. 标签管理
4. 定时发布
5. 与 AutoLogin 集成实现自动登录
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

# 抖音上传页面
DOUYIN_UPLOAD_URL = "https://creator.douyin.com/creator-micro/upload"
DOUYIN_CREATE_URL = "https://creator.douyin.com/creator-micro/home"

# 视频限制
VIDEO_MAX_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
VIDEO_MIN_DURATION = 1  # 最小1秒
VIDEO_MAX_DURATION = 10 * 60  # 最大10分钟
SUPPORTED_FORMATS = ['mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv']

# 上传相关选择器
UPLOAD_SELECTORS = {
    'upload_button': [
        'button[class*="upload"]',
        '[class*="upload-btn"]',
        'button:contains("上传视频")',
        'input[type="file"]'
    ],
    'title_input': [
        'input[name="title"]',
        'input[placeholder*="标题"]',
        'div[contenteditable="true"]'
    ],
    'description_input': [
        'textarea[name="description"]',
        'textarea[placeholder*="描述"]',
        'div[contenteditable="true"]'
    ],
    'tag_input': [
        'input[placeholder*="标签"]',
        'input[class*="tag"]'
    ],
    'publish_button': [
        'button:contains("发布")',
        'button[class*="publish"]',
        'button:contains("立即发布")'
    ],
    'cover_selector': [
        'button:contains("设置封面")',
        '[class*="cover"]'
    ]
}


# ============================================================================
# 数据类
# ============================================================================

class VideoStatus(Enum):
    """视频状态"""
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class VideoMetadata:
    """视频元数据"""
    file_path: str
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    cover_image: Optional[str] = None
    location: Optional[str] = None
    visibility: str = "public"  # public, private, friends
    
    # 定时发布
    scheduled_time: Optional[datetime] = None
    
    # 互动设置
    allow_comment: bool = True
    allow_download: bool = True
    show_avatar: bool = True
    
    def validate(self) -> List[str]:
        """验证视频元数据"""
        errors = []
        
        # 检查文件存在
        if not os.path.exists(self.file_path):
            errors.append(f"视频文件不存在: {self.file_path}")
        else:
            # 检查文件大小
            file_size = os.path.getsize(self.file_path)
            if file_size > VIDEO_MAX_SIZE:
                errors.append(f"视频文件过大: {file_size / 1024 / 1024:.2f}MB (最大 {VIDEO_MAX_SIZE / 1024 / 1024:.0f}MB)")
            
            # 检查文件格式
            ext = os.path.splitext(self.file_path)[1].lower().lstrip('.')
            if ext not in SUPPORTED_FORMATS:
                errors.append(f"不支持的视频格式: {ext} (支持: {', '.join(SUPPORTED_FORMATS)})")
        
        # 检查标题长度
        if len(self.title) > 55:
            errors.append(f"标题过长: {len(self.title)}字符 (最大55字符)")
        
        # 检查描述长度
        if len(self.description) > 2000:
            errors.append(f"描述过长: {len(self.description)}字符 (最大2000字符)")
        
        # 检查标签数量
        if len(self.tags) > 20:
            errors.append(f"标签过多: {len(self.tags)}个 (最多20个)")
        
        return errors


@dataclass
class UploadResult:
    """上传结果"""
    success: bool
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'video_id': self.video_id,
            'video_url': self.video_url,
            'error_message': self.error_message,
            'duration': self.duration
        }


# ============================================================================
# 抖音视频上传器
# ============================================================================

class DouyinUploader:
    """
    抖音视频上传器
    
    使用示例:
    ```python
    from tools.video_uploader import DouyinUploader, VideoMetadata
    
    uploader = DouyinUploader()
    
    # 上传视频
    metadata = VideoMetadata(
        file_path="/path/to/video.mp4",
        title="我的第一个视频",
        description="这是测试视频",
        tags=["测试", "教程"]
    )
    
    result = uploader.upload(metadata)
    print(result)
    ```
    """
    
    def __init__(
        self,
        cookie_file: Path = COOKIE_FILE,
        video_dir: Path = VIDEO_DIR,
        timeout: int = 60
    ):
        self.cookie_file = cookie_file
        self.video_dir = video_dir
        self.timeout = timeout
        self.driver = None
        
        # 确保目录存在
        self.video_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'total_duration': 0.0
        }
    
    def set_driver(self, driver) -> None:
        """设置 Selenium WebDriver"""
        self.driver = driver
    
    def _load_cookies(self) -> List[Dict]:
        """加载保存的 Cookies"""
        try:
            if self.cookie_file.exists():
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('douyin', [])
        except Exception as e:
            logger.warning(f"加载Cookies失败: {e}")
        return []
    
    def _save_cookies(self, cookies: List[Dict]) -> bool:
        """保存 Cookies"""
        try:
            data = {}
            if self.cookie_file.exists():
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            data['douyin'] = cookies
            
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"保存Cookies失败: {e}")
            return False
    
    def _inject_cookies(self, driver) -> bool:
        """注入 Cookies 到浏览器"""
        cookies = self._load_cookies()
        if not cookies:
            return False
        
        try:
            driver.get("https://www.douyin.com")
            time.sleep(1)
            
            for cookie in cookies:
                # 处理 cookie 名称中的特殊字符
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"添加cookie失败: {cookie.get('name', 'unknown')}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"注入Cookies失败: {e}")
            return False
    
    def _find_element(self, driver, selectors: List[str], timeout: int = 10):
        """使用多个选择器查找元素"""
        for selector in selectors:
            try:
                if selector.startswith('button:contains'):
                    # 处理 contains 语法
                    text = re.search(r'contains\("(.+?)"\)', selector)
                    if text:
                        text = text.group(1)
                        elements = driver.find_elements(By.TAG_NAME, 'button')
                        for elem in elements:
                            if text in elem.text:
                                return elem
                elif selector.startswith('input[type="file"]'):
                    return driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                else:
                    return WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located(
                            By.CSS_SELECTOR, selector
                        )
                    )
            except Exception:
                continue
        
        raise NoSuchElementException(f"未找到元素: {selectors}")
    
    def _upload_video_file(self, driver, file_path: str) -> bool:
        """上传视频文件"""
        try:
            # 查找文件上传 input
            file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            
            # 发送文件路径
            file_input.send_keys(os.path.abspath(file_path))
            
            logger.info(f"已选择视频文件: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"上传视频文件失败: {e}")
            return False
    
    def _fill_title(self, driver, title: str) -> bool:
        """填写视频标题"""
        try:
            for selector in UPLOAD_SELECTORS['title_input']:
                try:
                    elem = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(By.CSS_SELECTOR, selector)
                    )
                    elem.clear()
                    elem.send_keys(title[:55])  # 限制55字符
                    return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"填写标题失败: {e}")
            return False
    
    def _fill_description(self, driver, description: str) -> bool:
        """填写视频描述"""
        try:
            for selector in UPLOAD_SELECTORS['description_input']:
                try:
                    elem = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(By.CSS_SELECTOR, selector)
                    )
                    elem.clear()
                    elem.send_keys(description[:2000])
                    return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"填写描述失败: {e}")
            return False
    
    def _add_tags(self, driver, tags: List[str]) -> bool:
        """添加标签"""
        try:
            for tag in tags[:20]:  # 最多20个标签
                for selector in UPLOAD_SELECTORS['tag_input']:
                    try:
                        tag_input = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located(By.CSS_SELECTOR, selector)
                        )
                        tag_input.clear()
                        tag_input.send_keys(tag)
                        time.sleep(0.5)
                        # 按回车确认
                        tag_input.send_keys(Keys.ENTER)
                        break
                    except Exception:
                        continue
            return True
        except Exception as e:
            logger.error(f"添加标签失败: {e}")
            return False
    
    def _click_publish(self, driver) -> bool:
        """点击发布按钮"""
        try:
            for selector in UPLOAD_SELECTORS['publish_button']:
                try:
                    button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(By.CSS_SELECTOR, selector)
                    )
                    button.click()
                    logger.info("点击发布按钮")
                    return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"点击发布按钮失败: {e}")
            return False
    
    def _wait_for_upload_complete(self, driver, timeout: int = 300) -> bool:
        """等待视频上传和处理完成"""
        try:
            # 等待上传进度消失 (表示上传完成)
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    progress = driver.find_element(By.CSS_SELECTOR, '[class*="progress"]')
                    if progress.is_displayed():
                        time.sleep(2)
                        continue
                except NoSuchElementException:
                    # 进度条消失，上传完成
                    pass
                
                # 检查是否有错误提示
                try:
                    error = driver.find_element(By.CSS_SELECTOR, '[class*="error"]')
                    if error.is_displayed():
                        logger.error(f"上传出错: {error.text}")
                        return False
                except NoSuchElementException:
                    pass
                
                # 检查发布成功
                try:
                    success = driver.find_element(By.CSS_SELECTOR, '[class*="success"]')
                    if success.is_displayed():
                        logger.info("视频发布成功")
                        return True
                except NoSuchElementException:
                    pass
                
                time.sleep(2)
            
            logger.warning("上传超时")
            return False
            
        except Exception as e:
            logger.error(f"等待上传完成失败: {e}")
            return False
    
    def upload(self, metadata: VideoMetadata) -> UploadResult:
        """
        上传视频
        
        Args:
            metadata: 视频元数据
            
        Returns:
            UploadResult: 上传结果
        """
        start_time = time.time()
        
        # 验证元数据
        errors = metadata.validate()
        if errors:
            return UploadResult(
                success=False,
                error_message="; ".join(errors)
            )
        
        self.stats['total'] += 1
        
        if not self.driver:
            return UploadResult(
                success=False,
                error_message="未设置 WebDriver，请调用 set_driver() 方法"
            )
        
        try:
            # 导航到上传页面
            self.driver.get(DOUYIN_UPLOAD_URL)
            time.sleep(2)
            
            # 上传视频文件
            if not self._upload_video_file(self.driver, metadata.file_path):
                raise Exception("上传视频文件失败")
            
            # 等待视频上传
            time.sleep(5)
            
            # 填写标题
            if metadata.title:
                self._fill_title(self.driver, metadata.title)
            
            # 填写描述
            if metadata.description:
                self._fill_description(self.driver, metadata.description)
            
            # 添加标签
            if metadata.tags:
                self._add_tags(self.driver, metadata.tags)
            
            # 点击发布
            if self._click_publish(self.driver):
                # 等待发布完成
                if self._wait_for_upload_complete(self.driver):
                    duration = time.time() - start_time
                    self.stats['success'] += 1
                    self.stats['total_duration'] += duration
                    
                    return UploadResult(
                        success=True,
                        video_id=str(int(time.time())),  # 简化处理
                        video_url=f"https://www.douyin.com/video/{int(time.time())}",
                        duration=duration
                    )
            
            raise Exception("发布失败")
            
        except Exception as e:
            self.stats['failed'] += 1
            logger.error(f"上传视频失败: {e}")
            return UploadResult(
                success=False,
                error_message=str(e)
            )
    
    def upload_batch(
        self, 
        videos: List[VideoMetadata],
        delay: int = 5
    ) -> List[UploadResult]:
        """
        批量上传视频
        
        Args:
            videos: 视频元数据列表
            delay: 上传间隔时间（秒）
            
        Returns:
            List[UploadResult]: 上传结果列表
        """
        results = []
        
        for i, metadata in enumerate(videos):
            logger.info(f"上传第 {i+1}/{len(videos)} 个视频")
            
            result = self.upload(metadata)
            results.append(result)
            
            if result.success:
                logger.info(f"视频 {i+1} 上传成功")
            else:
                logger.error(f"视频 {i+1} 上传失败: {result.error_message}")
            
            # 等待间隔
            if i < len(videos) - 1:
                time.sleep(delay)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'success_rate': f"{self.stats['success'] / max(self.stats['total'], 1) * 100:.1f}%",
            'avg_duration': f"{self.stats['total_duration'] / max(self.stats['success'], 1):.1f}s" if self.stats['success'] > 0 else "0s"
        }
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'total_duration': 0.0
        }


# ============================================================================
# 便捷函数
# ============================================================================

def upload_video(
    file_path: str,
    title: str = "",
    description: str = "",
    tags: List[str] = None,
    driver = None
) -> UploadResult:
    """
    便捷函数：上传单个视频
    
    Args:
        file_path: 视频文件路径
        title: 视频标题
        description: 视频描述
        tags: 标签列表
        driver: Selenium WebDriver
        
    Returns:
        UploadResult: 上传结果
    """
    if tags is None:
        tags = []
    
    metadata = VideoMetadata(
        file_path=file_path,
        title=title,
        description=description,
        tags=tags
    )
    
    uploader = DouyinUploader()
    if driver:
        uploader.set_driver(driver)
    
    return uploader.upload(metadata)


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python video_uploader.py <视频文件路径> [标题] [描述] [标签1,标签2,...]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else ""
    description = sys.argv[3] if len(sys.argv) > 3 else ""
    tags = sys.argv[4].split(',') if len(sys.argv) > 4 else []
    
    result = upload_video(file_path, title, description, tags)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
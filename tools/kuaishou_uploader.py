#!/usr/bin/env python3
"""
快手视频上传工具
Kuaishou Video Uploader
"""

import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class KuaishouVideoMetadata:
    """快手视频元数据"""
    file_path: str
    title: str
    description: str = ""
    tags: List[str] = None
    location: Optional[str] = None
    visibility: str = "public"  # public, private
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class KuaishouUploadResult:
    """上传结果"""
    success: bool
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = None
    
    def __post_init__():
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class KuaishouUploader:
    """快手视频上传器"""
    
    BASE_URL = "https://www.kuaishou.com"
    UPLOAD_URL = "https://www.kuaishou.com/short-video/upload"
    
    def __init__(self, phone: str = None, password: str = None):
        """
        初始化快手上传器
        
        Args:
            phone: 快手账号手机号
            password: 账号密码
        """
        self.phone = phone or os.getenv("KUAI_SHOU_PHONE")
        self.password = password or os.getenv("KUAI_SHOU_PASSWORD")
        self.driver = None
        self._logged_in = False
    
    def set_driver(self, driver):
        """
        设置WebDriver
        
        Args:
            driver: Selenium WebDriver实例
        """
        self.driver = driver
        logger.info("WebDriver已设置")
    
    def login(self, driver=None) -> bool:
        """
        登录快手账号
        
        Args:
            driver: 可选的WebDriver，如果不设置则使用self.driver
            
        Returns:
            bool: 登录是否成功
        """
        if driver:
            self.driver = driver
        
        if not self.driver:
            logger.error("请先设置WebDriver")
            return False
        
        if not self.phone or not self.password:
            logger.error("请配置手机号和密码")
            return False
        
        try:
            logger.info(f"开始登录快手账号: {self.phone}")
            
            # 访问登录页面
            self.driver.get(f"{self.BASE_URL}/short-video/upload")
            time.sleep(2)
            
            # 点击登录按钮
            login_btn = self.driver.find_element("xpath", "//button[contains(text(), '登录')]")
            login_btn.click()
            time.sleep(1)
            
            # 输入手机号
            phone_input = self.driver.find_element("xpath", "//input[@placeholder='手机号']")
            phone_input.send_keys(self.phone)
            time.sleep(0.5)
            
            # 输入密码
            password_input = self.driver.find_element("xpath", "//input[@type='password']")
            password_input.send_keys(self.password)
            time.sleep(0.5)
            
            # 点击确认登录
            submit_btn = self.driver.find_element("xpath", "//button[@type='submit']")
            submit_btn.click()
            time.sleep(3)
            
            # 检���登录状态
            if "upload" in self.driver.current_url:
                self._logged_in = True
                logger.info("登录成功!")
                return True
            
            logger.warning("登录可能未成功，请检查")
            return False
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False
    
    def upload(self, metadata: KuaishouVideoMetadata, driver=None) -> KuaishouUploadResult:
        """
        上传视频
        
        Args:
            metadata: 视频元数据
            driver: 可选的WebDriver
            
        Returns:
            KuaishouUploadResult: 上传结果
        """
        if driver:
            self.driver = driver
        
        if not self.driver:
            return KuaishouUploadResult(
                success=False, 
                error="请先设置WebDriver"
            )
        
        # 检查文件是否存在
        if not os.path.exists(metadata.file_path):
            return KuaishouUploadResult(
                success=False,
                error=f"视频文件不存在: {metadata.file_path}"
            )
        
        try:
            logger.info(f"开始上传视频: {metadata.title}")
            
            # 访问上传页面
            self.driver.get(self.UPLOAD_URL)
            time.sleep(2)
            
            # 查找文件上传输入框
            file_input = self.driver.find_element("xpath", "//input[@type='file']")
            file_input.send_keys(os.path.abspath(metadata.file_path))
            time.sleep(3)
            
            # 填写标题
            title_input = self.driver.find_element(
                "xpath", 
                "//input[@placeholder='给视频起个标题']"
            )
            title_input.send_keys(metadata.title)
            time.sleep(0.5)
            
            # 填写描述
            if metadata.description:
                desc_input = self.driver.find_element(
                    "xpath",
                    "//textarea[@placeholder='添加描述']"
                )
                desc_input.send_keys(metadata.description)
                time.sleep(0.5)
            
            # 添加标签
            for tag in metadata.tags:
                tag_input = self.driver.find_element(
                    "xpath",
                    "//input[@placeholder='添加标签']"
                )
                tag_input.send_keys(f"#{tag} ")
                time.sleep(0.3)
            
            # 点击发布按钮
            publish_btn = self.driver.find_element(
                "xpath",
                "//button[contains(text(), '发布')]"
            )
            publish_btn.click()
            time.sleep(3)
            
            # 获取视频URL
            video_url = self.driver.current_url
            
            logger.info(f"视频上传成功: {video_url}")
            
            return KuaishouUploadResult(
                success=True,
                video_url=video_url,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"上传失败: {e}")
            return KuaishouUploadResult(
                success=False,
                error=str(e)
            )
    
    def upload_batch(
        self, 
        videos: List[KuaishouVideoMetadata], 
        delay: int = 5,
        driver=None
    ) -> List[KuaishouUploadResult]:
        """
        批量上传视频
        
        Args:
            videos: 视频元数据列表
            delay: 视频之间延迟(秒)
            driver: 可选的WebDriver
            
        Returns:
            List[KuaishouUploadResult]: 上传结果列表
        """
        results = []
        
        for i, metadata in enumerate(videos):
            logger.info(f"上传第 {i+1}/{len(videos)} 个视频")
            
            result = self.upload(metadata, driver)
            results.append(result)
            
            # 等待后再上传下一个
            if i < len(videos) - 1:
                time.sleep(delay)
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"批量上传完成: {success_count}/{len(videos)} 成功")
        
        return results
    
    def get_profile(self, driver=None) -> dict:
        """
        获取账号信息
        
        Args:
            driver: 可选的WebDriver
            
        Returns:
            dict: 账号信息
        """
        if driver:
            self.driver = driver
        
        if not self.driver:
            return {"error": "请先设置WebDriver"}
        
        try:
            self.driver.get(f"{self.BASE_URL}/profile")
            time.sleep(2)
            
            # 获取粉丝数、关注数等
            stats = {}
            
            # 粉丝
            fans_elem = self.driver.find_element("xpath", "//span[contains(text(), '粉丝')]/preceding-sibling::span")
            stats["fans"] = fans_elem.text if fans_elem else "0"
            
            # 作品数
            videos_elem = self.driver.find_element("xpath", "//span[contains(text(), '作品')]/preceding-sibling::span")
            stats["videos"] = videos_elem.text if videos_elem else "0"
            
            return stats
            
        except Exception as e:
            logger.error(f"获取账号信息失败: {e}")
            return {"error": str(e)}


# 便捷函数
def quick_upload(video_path: str, title: str, description: str = "", tags: List[str] = None):
    """
    快速上传视频
    
    Args:
        video_path: 视频文件路径
        title: 标题
        description: 描述
        tags: 标签列表
        
    Returns:
        KuaishouUploadResult: 上传结果
    """
    metadata = KuaishouVideoMetadata(
        file_path=video_path,
        title=title,
        description=description,
        tags=tags
    )
    
    uploader = KuaishouUploader()
    # 需要先设置driver才能使用
    return uploader.upload(metadata)


if __name__ == "__main__":
    # 测试代码
    print("快手视频上传器已加载")
    print("使用示例:")
    print("""
from tools.kuaishou_uploader import KuaishouUploader, KuaishouVideoMetadata

# 创建元数据
metadata = KuaishouVideoMetadata(
    file_path="/path/to/video.mp4",
    title="我的视频",
    description="这是测试视频",
    tags=["测试", "教程"]
)

# 上传视频
uploader = KuaishouUploader(phone="xxx", password="xxx")
uploader.set_driver(driver)
result = uploader.upload(metadata)
print(f"上传结果: {result.success}")
""")
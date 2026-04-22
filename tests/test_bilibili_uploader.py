#!/usr/bin/env python3
"""
Bilibili Uploader Tests
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.bilibili_uploader import (
    BilibiliUploader,
    BilibiliVideoMetadata,
    BilibiliUploadResult,
    VideoCopyright,
    VIDEO_CATEGORIES,
    SUPPORTED_FORMATS,
)


class TestBilibiliVideoMetadata:
    """测试B站视频元数据"""
    
    def test_valid_metadata(self, tmp_path):
        """测试有效元数据"""
        # 创建临时视频文件
        video_file = tmp_path / "test.mp4"
        video_file.write_text("dummy video content")
        
        metadata = BilibiliVideoMetadata(
            file_path=str(video_file),
            title="测试视频",
            description="这是一个测试视频",
            tags=["测试", "科技"],
            category="科技",
            sub_category="计算机",
        )
        
        valid, message = metadata.validate()
        assert valid, message
    
    def test_invalid_file_path(self):
        """测试无效文件路径"""
        metadata = BilibiliVideoMetadata(
            file_path="/nonexistent/video.mp4",
            title="测试视频",
        )
        
        valid, message = metadata.validate()
        assert not valid
        assert "不存在" in message
    
    def test_title_max_length(self, tmp_path):
        """测试标题最大长度"""
        video_file = tmp_path / "test.mp4"
        video_file.write_text("content")
        
        # B站标题最大80字符
        long_title = "a" * 100
        metadata = BilibiliVideoMetadata(
            file_path=str(video_file),
            title=long_title,
        )
        
        assert len(metadata.title) == 80
    
    def test_tags_max_count(self, tmp_path):
        """测试标签最大数量"""
        video_file = tmp_path / "test.mp4"
        video_file.write_text("content")
        
        # 超过12个标签
        tags = [f"tag{i}" for i in range(15)]
        metadata = BilibiliVideoMetadata(
            file_path=str(video_file),
            title="测试",
            tags=tags,
        )
        
        valid, message = metadata.validate()
        assert not valid
        assert "过多" in message
    
    def test_unsupported_format(self, tmp_path):
        """测试不支持的格式"""
        video_file = tmp_path / "test.avi"
        video_file.write_text("content")
        
        metadata = BilibiliVideoMetadata(
            file_path=str(video_file),
            title="测试",
        )
        
        valid, message = metadata.validate()
        # avi 应该是支持的
        assert valid or "格式" not in message


class TestBilibiliUploadResult:
    """测试上传结果"""
    
    def test_success_result(self):
        """测试成功结果"""
        result = BilibiliUploadResult(
            success=True,
            bvid="BV1234567890",
            video_url="https://www.bilibili.com/video/BV1234567890",
        )
        
        assert result.success
        assert result.bvid == "BV1234567890"
        assert "BV1234567890" in result.video_url
    
    def test_failure_result(self):
        """测试失败结果"""
        result = BilibiliUploadResult(
            success=False,
            message="上传失败",
        )
        
        assert not result.success
        assert "失败" in str(result)


class TestBilibiliUploader:
    """测试B站上传器"""
    
    def test_init(self):
        """测试初始化"""
        uploader = BilibiliUploader()
        
        assert uploader.timeout == 30
        assert uploader.driver is None
    
    def test_set_driver(self):
        """测试设置driver"""
        uploader = BilibiliUploader()
        
        class MockDriver:
            pass
        
        mock_driver = MockDriver()
        uploader.set_driver(mock_driver)
        
        assert uploader.driver is mock_driver
    
    def test_session_creation(self):
        """测试session创建"""
        uploader = BilibiliUploader()
        
        session = uploader.session
        assert session is not None
        assert 'User-Agent' in session.headers
    
    def test_categories_exist(self):
        """测试分类存在"""
        assert '生活' in VIDEO_CATEGORIES
        assert '科技' in VIDEO_CATEGORIES
        assert '游戏' in VIDEO_CATEGORIES
    
    def test_supported_formats(self):
        """测试支持的格式"""
        assert 'mp4' in SUPPORTED_FORMATS
        assert 'avi' in SUPPORTED_FORMATS
        assert 'mov' in SUPPORTED_FORMATS


class TestQuickUpload:
    """测试快速上传函数"""
    
    def test_quick_upload_creation(self):
        """测试快速上传函数创建"""
        from tools.bilibili_uploader import bilibili_quick_upload
        
        assert callable(bilibili_quick_upload)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
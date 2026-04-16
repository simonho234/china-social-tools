#!/usr/bin/env python3
"""
ImageGenerator 单元测试
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call, AsyncMock
from datetime import datetime

import sys
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from tools.advanced import ImageGenerator


class TestImageGenerator:
    """测试 ImageGenerator 类"""
    
    def test_init_default(self):
        """测试默认初始化"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            assert generator is not None
            assert generator.provider is None
    
    def test_init_with_openai(self):
        """测试使用 OpenAI 初始化"""
        with patch('tools.advanced.setup_logging'):
            with patch('tools.advanced.OpenAI') as mock_openai:
                generator = ImageGenerator(provider="openai", api_key="test-key")
                
                mock_openai.assert_called_once_with(api_key="test-key")
                assert generator.provider == "openai"
    
    def test_init_with_anthropic(self):
        """测试使用 Anthropic 初始化"""
        with patch('tools.advanced.setup_logging'):
            with patch('tools.advanced.anthropic') as mock_anthropic:
                generator = ImageGenerator(provider="anthropic", api_key="test-key")
                
                assert generator.provider == "anthropic"
    
    def test_init_invalid_provider(self):
        """测试无效的 provider"""
        with patch('tools.advanced.setup_logging'):
            with pytest.raises(ValueError):
                ImageGenerator(provider="invalid")
    
    @patch('tools.advanced.OpenAI')
    def test_generate_with_openai(self, mock_openai):
        """测试使用 OpenAI 生成图片"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator(provider="openai", api_key="test-key")
            
            # Mock 响应
            mock_response = MagicMock()
            mock_response.data = []
            generator.client.images.generate.return_value = mock_response
            
            result = generator.generate("科技主题")
            
            assert isinstance(result, dict)
            generator.client.images.generate.assert_called_once()
    
    @patch('tools.advanced.anthropic.Anthropic')
    def test_generate_with_anthropic(self, mock_anthropic):
        """测试使用 Anthropic 生成图片"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator(provider="anthropic", api_key="test-key")
            
            # Mock 响应
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"image_base64": "test123"}')]
            generator.client.images.generate.return_value = mock_response
            
            result = generator.generate("科技主题")
            
            assert isinstance(result, dict)
    
    def test_generate_no_provider(self):
        """测试无 provider 时的生成"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            
            result = generator.generate("测试主题")
            
            assert result["success"] is False
            assert "provider" in result["error"].lower()
    
    def test_cache_mechanism(self):
        """测试缓存机制"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            
            # 测试缓存设置
            generator.set_cache_dir("/tmp/image_cache")
            assert generator.cache_dir == "/tmp/image_cache"
            
            # 测试缓存启用/禁用
            generator.enable_cache(True)
            assert generator.cache_enabled is True
            
            generator.enable_cache(False)
            assert generator.cache_enabled is False
    
    def test_get_cache_key(self):
        """测试缓存键生成"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            
            key1 = generator._get_cache_key("科技主题")
            key2 = generator._get_cache_key("科技主题")
            key3 = generator._get_cache_key("其他主题")
            
            assert key1 == key2  # 相同内容应该生成相同的 key
            assert key1 != key3  # 不同内容应该生成不同的 key
    
    def test_get_cached_image(self):
        """测试获取缓存图片"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            generator.cache_enabled = True
            generator.cache_dir = Path("/tmp/test_cache")
            
            # Mock 缓存目录存在
            with patch.object(generator.cache_dir, 'exists', return_value=True):
                with patch('tools.advanced.Path.glob', return_value=[]):
                    cached = generator._get_cached_image("test_key")
                    assert cached is None
    
    def test_save_to_cache(self):
        """测试保存到缓存"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            generator.cache_dir = Path("/tmp/test_cache")
            
            with patch.object(generator.cache_dir, 'mkdir'):
                with patch('builtins.open', create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_open.return_value.__enter__.return_value = mock_file
                    
                    generator._save_to_cache("test_key", b"image_data")
                    
                    mock_file.write.assert_called_once_with(b"image_data")
    
    def test_get_providers(self):
        """测试获取支持的 providers"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            
            providers = generator.get_providers()
            
            assert "openai" in providers
            assert "anthropic" in providers
    
    def test_validate_prompt(self):
        """测试验证提示词"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator()
            
            # 正常提示词
            assert generator._validate_prompt("正常提示词") is True
            
            # 空提示词
            assert generator._validate_prompt("") is False
            
            # 太短的提示词
            assert generator._validate_prompt("ab") is False
    
    def test_generate_with_custom_size(self):
        """测试自定义图片尺寸"""
        with patch('tools.advanced.OpenAI') as mock_openai:
            with patch('tools.advanced.setup_logging'):
                generator = ImageGenerator(provider="openai", api_key="test-key")
                
                mock_response = MagicMock()
                mock_response.data = []
                generator.client.images.generate.return_value = mock_response
                
                result = generator.generate("测试", size="1024x1024")
                
                call_kwargs = generator.client.images.generate.call_args.kwargs
                assert call_kwargs.get("size") == "1024x1024"
    
    def test_generate_with_style(self):
        """测试自定义风格"""
        with patch('tools.advanced.OpenAI') as mock_openai:
            with patch('tools.advanced.setup_logging'):
                generator = ImageGenerator(provider="openai", api_key="test-key")
                
                mock_response = MagicMock()
                mock_response.data = []
                generator.client.images.generate.return_value = mock_response
                
                result = generator.generate("测试", style="natural")
                
                call_kwargs = generator.client.images.generate.call_args.kwargs
                assert call_kwargs.get("style") == "natural"
    
    def test_generate_quality(self):
        """测试图片质量"""
        with patch('tools.advanced.OpenAI') as mock_openai:
            with patch('tools.advanced.setup_logging'):
                generator = ImageGenerator(provider="openai", api_key="test-key")
                
                mock_response = MagicMock()
                mock_response.data = []
                generator.client.images.generate.return_value = mock_response
                
                result = generator.generate("测试", quality="high")
                
                call_kwargs = generator.client.images.generate.call_args.kwargs
                assert call_kwargs.get("quality") == "high"


class TestImageGeneratorErrorHandling:
    """测试错误处理"""
    
    @patch('tools.advanced.OpenAI')
    def test_api_error_handling(self, mock_openai):
        """测试 API 错误处理"""
        with patch('tools.advanced.setup_logging'):
            generator = ImageGenerator(provider="openai", api_key="test-key")
            
            # 模拟 API 错误
            generator.client.images.generate.side_effect = Exception("API Error")
            
            result = generator.generate("测试")
            
            assert result["success"] is False
            assert "error" in result
    
    def test_invalid_size_handling(self):
        """测试无效尺寸处理"""
        with patch('tools.advanced.OpenAI') as mock_openai:
            with patch('tools.advanced.setup_logging'):
                generator = ImageGenerator(provider="openai", api_key="test-key")
                
                # 测试无效尺寸
                result = generator.generate("测试", size="invalid")
                
                assert result["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

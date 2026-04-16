#!/usr/bin/env python3
"""
ContentGenerator 单元测试
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

import sys
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from tools.advanced import ContentGenerator


class TestContentGenerator:
    """测试 ContentGenerator 类"""
    
    def test_init_default(self):
        """测试默认初始化"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            assert generator is not None
            assert generator.provider is None
    
    def test_init_with_openai(self):
        """测试使用 OpenAI 初始化"""
        with patch('tools.advanced.setup_logging'):
            with patch('tools.advanced.OpenAI') as mock_openai:
                generator = ContentGenerator(provider="openai", api_key="test-key")
                
                mock_openai.assert_called_once_with(api_key="test-key")
                assert generator.provider == "openai"
    
    def test_init_with_anthropic(self):
        """测试使用 Anthropic 初始化"""
        with patch('tools.advanced.setup_logging'):
            with patch('tools.advanced.anthropic') as mock_anthropic:
                generator = ContentGenerator(provider="anthropic", api_key="test-key")
                
                assert generator.provider == "anthropic"
    
    def test_init_invalid_provider(self):
        """测试无效的 provider"""
        with patch('tools.advanced.setup_logging'):
            with pytest.raises(ValueError):
                ContentGenerator(provider="invalid")
    
    @patch('tools.advanced.OpenAI')
    def test_generate_basic(self, mock_openai):
        """测试基本内容生成"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            # Mock 响应
            mock_choice = MagicMock()
            mock_choice.message.content = "这是一篇关于科技的文章。"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            result = generator.generate("科技")
            
            assert isinstance(result, dict)
            assert "content" in result
    
    @patch('tools.advanced.OpenAI')
    def test_generate_with_system_prompt(self, mock_openai):
        """测试带系统提示词的内容生成"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            mock_choice = MagicMock()
            mock_choice.message.content = "测试内容"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            system_prompt = "你是一个专业的内容创作者"
            result = generator.generate("测试主题", system_prompt=system_prompt)
            
            # 验证系统提示词被使用
            call_args = generator.client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])
            system_messages = [m for m in messages if m.get("role") == "system"]
            assert len(system_messages) > 0
    
    @patch('tools.advanced.OpenAI')
    def test_generate_with_custom_model(self, mock_openai):
        """测试自定义模型"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            mock_choice = MagicMock()
            mock_choice.message.content = "测试"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            result = generator.generate("测试", model="gpt-4")
            
            call_args = generator.client.chat.completions.create.call_args
            assert call_args.kwargs.get("model") == "gpt-4"
    
    def test_generate_no_provider(self):
        """测试无 provider 时的生成"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            
            result = generator.generate("测试主题")
            
            assert result["success"] is False
            assert "provider" in result["error"].lower()
    
    @patch('tools.advanced.OpenAI')
    def test_generate_with_temperature(self, mock_openai):
        """测试温度参数"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            mock_choice = MagicMock()
            mock_choice.message.content = "测试"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            result = generator.generate("测试", temperature=0.8)
            
            call_args = generator.client.chat.completions.create.call_args
            assert call_args.kwargs.get("temperature") == 0.8
    
    @patch('tools.advanced.OpenAI')
    def test_generate_with_max_tokens(self, mock_openai):
        """测试最大 token 数"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            mock_choice = MagicMock()
            mock_choice.message.content = "测试"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            result = generator.generate("测试", max_tokens=2000)
            
            call_args = generator.client.chat.completions.create.call_args
            assert call_args.kwargs.get("max_tokens") == 2000
    
    def test_history_tracking(self):
        """测试历史记录跟踪"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            
            # 添加到历史
            generator.add_to_history("主题1", "内容1")
            generator.add_to_history("主题2", "内容2")
            
            assert len(generator.history) == 2
            assert generator.history[0]["topic"] == "主题1"
            assert generator.history[1]["topic"] == "主题2"
    
    def test_history_limit(self):
        """测试历史记录限制"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(max_history=3)
            
            # 添加超过限制的记录
            for i in range(5):
                generator.add_to_history(f"主题{i}", f"内容{i}")
            
            assert len(generator.history) == 3
            assert generator.history[0]["topic"] == "主题2"
    
    def test_clear_history(self):
        """测试清空历史记录"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            
            generator.add_to_history("主题1", "内容1")
            assert len(generator.history) > 0
            
            generator.clear_history()
            assert len(generator.history) == 0
    
    def test_quality_evaluation(self):
        """测试质量评估"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            
            # 评估高质量内容
            good_content = "这是一篇非常详细且内容丰富的文章，包含了大量的信息和深刻的见解。"
            score = generator.evaluate_quality(good_content)
            assert score > 0.5
            
            # 评估低质量内容
            bad_content = "好"
            score = generator.evaluate_quality(bad_content)
            assert score < 0.5
    
    def test_get_stats(self):
        """测试获取统计信息"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            
            generator.add_to_history("主题1", "内容1")
            generator.add_to_history("主题2", "内容2")
            
            stats = generator.get_stats()
            
            assert "total_generated" in stats
            assert stats["total_generated"] == 2
    
    @patch('tools.advanced.OpenAI')
    def test_generate_with_topics_extraction(self, mock_openai):
        """测试从内容中提取主题"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            mock_choice = MagicMock()
            mock_choice.message.content = "主题1,主题2,主题3"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            result = generator.extract_topics("关于科技和生活的文章")
            
            assert isinstance(result, list)
    
    def test_get_providers(self):
        """测试获取支持的 providers"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            
            providers = generator.get_providers()
            
            assert "openai" in providers
            assert "anthropic" in providers


class TestContentGeneratorErrorHandling:
    """测试错误处理"""
    
    @patch('tools.advanced.OpenAI')
    def test_api_error_handling(self, mock_openai):
        """测试 API 错误处理"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            # 模拟 API 错误
            generator.client.chat.completions.create.side_effect = Exception("API Error")
            
            result = generator.generate("测试主题")
            
            assert result["success"] is False
            assert "error" in result
    
    @patch('tools.advanced.OpenAI')
    def test_empty_response_handling(self, mock_openai):
        """测试空响应处理"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            # Mock 空响应
            mock_response = MagicMock()
            mock_response.choices = []
            generator.client.chat.completions.create.return_value = mock_response
            
            result = generator.generate("测试主题")
            
            assert result["success"] is False
    
    def test_invalid_temperature(self):
        """测试无效温度参数"""
        with patch('tools.advanced.OpenAI') as mock_openai:
            with patch('tools.advanced.setup_logging'):
                generator = ContentGenerator(provider="openai", api_key="test-key")
                
                # 测试超出范围的值
                result = generator.generate("测试", temperature=2.0)
                
                assert result["success"] is False


class TestContentGeneratorAdvanced:
    """测试高级功能"""
    
    @patch('tools.advanced.OpenAI')
    def test_batch_generate(self, mock_openai):
        """测试批量生成"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            mock_choice = MagicMock()
            mock_choice.message.content = "测试内容"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            topics = ["科技", "生活", "娱乐"]
            results = generator.batch_generate(topics)
            
            assert len(results) == len(topics)
    
    @patch('tools.advanced.OpenAI')
    def test_regenerate(self, mock_openai):
        """测试重新生成"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator(provider="openai", api_key="test-key")
            
            mock_choice = MagicMock()
            mock_choice.message.content = "新内容"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response
            
            original = "原始内容"
            result = generator.regenerate(original)
            
            assert result["success"] is True
    
    def test_template_system(self):
        """测试模板系统"""
        with patch('tools.advanced.setup_logging'):
            generator = ContentGenerator()
            
            # 测试使用模板
            result = generator.generate_with_template(
                "科技",
                template_type="news"
            )
            
            assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

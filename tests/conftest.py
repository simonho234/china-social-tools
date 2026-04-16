#!/usr/bin/env python3
"""
测试配置文件
提供通用的 fixtures 和 mock
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime

# 添加项目路径
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))


@pytest.fixture
def mock_temp_dir(tmp_path):
    """创建临时目录用于测试"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return tmp_path


@pytest.fixture
def mock_config():
    """模拟配置"""
    return {
        "openai_api_key": "test-key",
        "anthropic_api_key": "test-key",
        "toutiao_phone": "13800138000",
        "toutiao_password": "test-password"
    }


@pytest.fixture
def mock_cookies():
    """模拟 cookies"""
    return [
        {"name": "token", "value": "test_token_12345", "domain": ".toutiao.com"},
        {"name": "session_id", "value": "session_abcde", "domain": ".toutiao.com"}
    ]


@pytest.fixture
def mock_driver():
    """模拟 Selenium WebDriver"""
    driver = MagicMock()
    driver.current_url = "https://www.toutiao.com/profile/"
    driver.page_source = "<html>Logged in</html>"
    driver.get_cookies.return_value = []
    driver.title = "今日头条"
    return driver


@pytest.fixture
def mock_response():
    """模拟 HTTP 响应"""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"code": 0, "message": "success"}
    response.text = "OK"
    response.content = b"OK"
    return response

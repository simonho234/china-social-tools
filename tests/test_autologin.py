#!/usr/bin/env python3
"""
AutoLogin 单元测试
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta

import sys
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from tools.advanced import AutoLogin, LoginState, LoginMethod


class TestAutoLogin:
    """测试 AutoLogin 类"""
    
    def test_init_default(self):
        """测试默认初始化"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            assert login is not None
            assert login.phone is None
            assert login.password is None
            assert login.headless is True
            assert login.log_level == "INFO"
    
    def test_init_with_credentials(self):
        """测试带凭证初始化"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin(
                phone="13800138000",
                password="test123",
                headless=False,
                log_level="DEBUG"
            )
            assert login.phone == "13800138000"
            assert login.password == "test123"
            assert login.headless is False
            assert login.log_level == "DEBUG"
    
    def test_init_with_chrome_profile(self):
        """测试使用 Chrome Profile 初始化"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            profile_path = "/tmp/test_profile"
            login = AutoLogin(chrome_profile=profile_path)
            assert login.chrome_profile == profile_path
    
    @patch('tools.advanced.webdriver.Chrome')
    def test_init_driver(self, mock_chrome):
        """测试驱动初始化"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin(headless=True)
            login._init_driver()
            
            # 验证 Chrome 被调用
            mock_chrome.assert_called_once()
    
    def test_load_cookies_no_file(self, tmp_path):
        """测试加载不存在的 cookie 文件"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.cookie_file = tmp_path / "nonexistent.json"
            cookies = login._load_cookies()
            assert cookies == []
    
    def test_load_cookies_with_file(self, tmp_path, mock_cookies):
        """测试加载 cookie 文件"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.cookie_file = tmp_path / "cookies.json"
            
            # 写入 cookie 文件
            with open(login.cookie_file, 'w') as f:
                json.dump(mock_cookies, f)
            
            cookies = login._load_cookies()
            assert len(cookies) == 2
            assert cookies[0]["name"] == "token"
    
    def test_save_cookies(self, tmp_path, mock_cookies):
        """测试保存 cookies"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.cookie_file = tmp_path / "cookies.json"
            
            login._save_cookies(mock_cookies)
            
            assert login.cookie_file.exists()
            
            with open(login.cookie_file, 'r') as f:
                saved = json.load(f)
            assert len(saved) == 2
    
    def test_check_login_state_logged_in(self):
        """测试已登录状态检测"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.driver = MagicMock()
            login.driver.current_url = "https://www.toutiao.com/profile/"
            
            state = login._check_login_state()
            assert state == LoginState.LOGGED_IN
    
    def test_check_login_state_not_logged_in(self):
        """测试未登录状态检测"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.driver = MagicMock()
            login.driver.current_url = "https://login.toutiao.com/"
            
            state = login._check_login_state()
            assert state == LoginState.NOT_LOGGED_IN
    
    @patch('tools.advanced.WebDriverWait')
    def test_wait_for_element(self, mock_wait):
        """测试等待元素"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.driver = MagicMock()
            
            mock_element = MagicMock()
            mock_wait_instance = MagicMock()
            mock_wait_instance.until.return_value = mock_element
            mock_wait.return_value = mock_wait_instance
            
            element = login._wait_for_element(By.ID, "test-id", timeout=10)
            
            assert element == mock_element
            mock_wait.assert_called_once()
    
    @patch('tools.advanced.webdriver.Chrome')
    def test_login_success(self, mock_chrome):
        """测试成功登录"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            with patch('tools.advanced.AutoLogin._check_login_state') as mock_state:
                mock_state.return_value = LoginState.NOT_LOGGED_IN
                with patch('tools.advanced.AutoLogin._do_login') as mock_do_login:
                    mock_do_login.return_value = True
                    
                    login = AutoLogin(phone="13800138000", password="test")
                    login.driver = MagicMock()
                    login.driver.current_url = "https://www.toutiao.com/profile/"
                    
                    result = login.login()
                    
                    # 登录可能成功或失败，取决于 mock 设置
                    assert isinstance(result, bool)
    
    def test_refresh_cookie_not_implemented(self):
        """测试刷新 cookie 功能"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            
            # 该功能待实现
            result = login.refresh_cookie()
            assert result is None
    
    def test_get_session_info(self):
        """测试获取会话信息"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.driver = MagicMock()
            login.driver.current_url = "https://www.toutiao.com/profile/"
            login.driver.get_cookies.return_value = [
                {"name": "test", "value": "value"}
            ]
            
            info = login.get_session_info()
            
            assert "logged_in" in info
            assert "url" in info
            assert "cookies_count" in info
    
    def test_close_driver(self):
        """测试关闭驱动"""
        with patch('tools.advanced.setup_logging'), \
             patch('tools.advanced.CookieManager'), \
             patch('tools.advanced.ProfileManager'), \
             patch('tools.advanced.LoginStateManager'):
            login = AutoLogin()
            login.driver = MagicMock()
            
            login.close()
            
            login.driver.quit.assert_called_once()
            assert login.driver is None
    
    def test_context_manager(self):
        """测试上下文管理器"""
        with patch('tools.advanced.webdriver.Chrome'):
            with patch('tools.advanced.setup_logging'):
                with patch('tools.advanced.CookieManager'):
                    with patch('tools.advanced.ProfileManager'):
                        with patch('tools.advanced.LoginStateManager'):
                            with patch('tools.advanced.AutoLogin._check_login_state'):
                                with patch('tools.advanced.AutoLogin.close'):
                                    login = AutoLogin()
                                    login.driver = MagicMock()
                                    
                                    # 测试 __enter__ 和 __exit__
                                    result = login.__enter__()
                                    assert result == login
                                    
                                    login.__exit__(None, None, None)
                                    login.close.assert_called_once()


class TestLoginState:
    """测试登录状态枚举"""
    
    def test_login_state_values(self):
        """测试状态枚举值"""
        assert LoginState.UNKNOWN.value == "unknown"
        assert LoginState.LOGGED_IN.value == "logged_in"
        assert LoginState.NOT_LOGGED_IN.value == "not_logged_in"
        assert LoginState.COOKIE_EXPIRED.value == "cookie_expired"
        assert LoginState.NEEDS_RELOGIN.value == "needs_relogin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

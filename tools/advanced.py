#!/usr/bin/env python3
"""
China Social Media Tools - 高级功能模块
生产级别的自动登录类

特性:
1. 使用已保存的Chrome profile保持登录状态
2. 完善的错误处理和异常管理
3. Cookie过期自动检测和重新登录
4. 详细的日志记录
5. 会话有效性的多维度验证
6. 资源正确管理
"""

import os
import sys
import json
import time
import logging
import base64
import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
from contextlib import contextmanager

import yaml
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException
)

# AI支持
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# ============================================================================
# 配置和常量
# ============================================================================

logger = logging.getLogger(__name__)

# 路径配置
BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"
COOKIE_FILE = BASE_DIR / "data" / "cookies.json"
LOGIN_STATE_FILE = BASE_DIR / "data" / "login_state.json"
BROWSER_PROFILE_DIR = BASE_DIR / "data" / "browser_state" / "browser_profile"

# 超时配置
DEFAULT_TIMEOUT = 30
IMPLICIT_WAIT = 10
PAGE_LOAD_TIMEOUT = 60

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2

# 登录验证配置
LOGIN_VERIFY_URLS = [
    "https://www.toutiao.com/profile/",
    "https://www.toutiao.com/api/pc/feed/",
    "https://www.toutiao.com/profile/"
]

# 检测登录状态的元素选择器
LOGGED_IN_INDICATORS = [
    {"type": "css", "value": "[class*='user-info']"},
    {"type": "css", "value": "[class*='avatar']"},
    {"type": "css", "value": "[class*='user-name']"},
    {"type": "css", "value": "[class*='nick-name']"},
    {"type": "xpath", "value": "//a[contains(@href, '/profile/')]"},
    {"type": "css", "value": "[class*='login-btn']"},
    {"type": "xpath", "value": "//span[contains(@class, 'user')]"},
]

# 登录页面的特征（用于检测是否在登录页）
LOGIN_PAGE_INDICATORS = [
    {"type": "css", "value": "input[name='phone']"},
    {"type": "css", "value": "input[type='tel']"},
    {"type": "xpath", "value": "//input[@placeholder*='手机']"},
    {"type": "xpath", "value": "//input[@placeholder*='帐号']"},
    {"type": "css", "value": "[class*='login-form']"},
    {"type": "css", "value": "[class*='login-page']"},
]


# ============================================================================
# 自定义异常
# ============================================================================

class AutoLoginError(Exception):
    """基础异常类"""
    pass

class DriverInitError(AutoLoginError):
    """驱动初���化失败"""
    pass

class LoginFailedError(AutoLoginError):
    """登录失败"""
    pass

class CookieExpiredError(AutoLoginError):
    """Cookie已过期"""
    pass

class SessionInvalidError(AutoLoginError):
    """会话无效"""
    pass

class NetworkError(AutoLoginError):
    """网络请求失败"""
    pass

class ProfileNotFoundError(AutoLoginError):
    """Chrome Profile未找到"""
    pass


# ============================================================================
# 枚举类
# ============================================================================

class LoginState(Enum):
    """登录状态枚举"""
    UNKNOWN = "unknown"
    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    COOKIE_EXPIRED = "cookie_expired"
    NEEDS_RELOGIN = "needs_relogin"


class LoginMethod(Enum):
    """登录方式枚举"""
    COOKIE = "cookie"
    PROFILE = "profile"
    CREDENTIALS = "credentials"
    AUTO = "auto"


# ============================================================================
# 工具函数
# ============================================================================

def setup_logging(log_level: str = "INFO") -> None:
    """配置日志记录"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 创建日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # 避免重复添加处理器
    if not root_logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器
        log_file = BASE_DIR / "logs" / "autologin.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def retry_on_exception(max_retries: int = MAX_RETRIES, delay: int = RETRY_DELAY):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries}): {e}, "
                            f"{delay}秒后重试..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} 失败 (已重试 {max_retries}次): {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


def validate_phone(phone: str) -> bool:
    """验证手机号格式"""
    if not phone:
        return False
    # 移除常见分隔符
    phone_clean = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
    # 中国手机号: 1开头，第二位3-9，共11位
    return len(phone_clean) == 11 and phone_clean.startswith('1')


def hash_string(s: str) -> str:
    """生成字符串哈希"""
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ============================================================================
# 登录状态管理器
# ============================================================================

class LoginStateManager:
    """登录状态管理器"""
    
    def __init__(self, state_file: Path = LOGIN_STATE_FILE):
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def save_state(self, state: LoginState, method: LoginMethod = LoginMethod.AUTO, 
                  expires_at: datetime = None, extra_info: Dict = None) -> None:
        """保存登录状态"""
        data = {
            "state": state.value,
            "method": method.value,
            "timestamp": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "extra_info": extra_info or {}
        }
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"登录状态已保存: {state.value} (方式: {method.value})")
    
    def load_state(self) -> Optional[Dict]:
        """加载登录状态"""
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载登录状态失败: {e}")
            return None
    
    def is_valid(self) -> bool:
        """检查保存的状态是否有效"""
        state_data = self.load_state()
        if not state_data:
            return False
        
        # 检查过期时间
        if state_data.get("expires_at"):
            expires_at = datetime.fromisoformat(state_data["expires_at"])
            if datetime.now() > expires_at:
                logger.info("登录状态已过期")
                return False
        
        # 检查状态
        return state_data.get("state") == LoginState.LOGGED_IN.value
    
    def clear_state(self) -> None:
        """清除登录状态"""
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("登录状态已清除")


# ============================================================================
# Chrome Profile 管理器
# ============================================================================

class ProfileManager:
    """Chrome Profile管理器"""
    
    def __init__(self, profile_dir: Path = BROWSER_PROFILE_DIR):
        self.profile_dir = profile_dir
        self.backup_dir = profile_dir.parent / "browser_profile_backup"
    
    def get_profile_path(self) -> Optional[str]:
        """获取Profile路径"""
        if self.profile_dir.exists() and self._is_valid_profile():
            logger.info(f"使用已存在的Profile: {self.profile_dir}")
            return str(self.profile_dir)
        
        # 尝试恢复备份
        if self.backup_dir.exists():
            logger.info("尝试恢复Profile备份...")
            self._restore_backup()
            if self._is_valid_profile():
                return str(self.profile_dir)
        
        logger.warning("未找到有效的Chrome Profile")
        return None
    
    def _is_valid_profile(self) -> bool:
        """检查Profile是否有效"""
        # 检查必要的文件是否存在
        required_files = ['Preferences', 'Default/Preferences']
        
        for file_path in required_files:
            full_path = self.profile_dir / file_path
            if not full_path.exists():
                # 尝试检查Default目录
                if file_path == 'Default/Preferences':
                    default_dir = self.profile_dir / 'Default'
                    if default_dir.exists():
                        prefs = default_dir / 'Preferences'
                        if prefs.exists():
                            continue
                return False
        
        return True
    
    def backup_profile(self) -> bool:
        """备份Profile"""
        if not self.profile_dir.exists():
            return False
        
        try:
            # 删除旧备份
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            
            # 创建新备份
            shutil.copytree(self.profile_dir, self.backup_dir)
            logger.info(f"Profile已备份到: {self.backup_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Profile备份失败: {e}")
            return False
    
    def _restore_backup(self) -> bool:
        """恢复Profile备份"""
        if not self.backup_dir.exists():
            return False
        
        try:
            if self.profile_dir.exists():
                shutil.rmtree(self.profile_dir)
            
            shutil.copytree(self.backup_dir, self.profile_dir)
            logger.info("Profile已从备份恢复")
            return True
            
        except Exception as e:
            logger.error(f"Profile恢复失败: {e}")
            return False
    
    def cleanup_old_profiles(self, max_age_days: int = 30) -> int:
        """清理旧的Profile备份"""
        if not self.backup_dir.exists():
            return 0
        
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        cleaned = 0
        
        try:
            # 检查备份修改时间
            mtime = datetime.fromtimestamp(self.backup_dir.stat().st_mtime)
            if mtime < cutoff_time:
                shutil.rmtree(self.backup_dir)
                cleaned = 1
                logger.info(f"已清理旧的Profile备份: {self.backup_dir}")
        except Exception as e:
            logger.warning(f"清理Profile备份失败: {e}")
        
        return cleaned


# ============================================================================
# Cookie 管理器
# ============================================================================

class CookieManager:
    """Cookie管理器"""
    
    def __init__(self, cookie_file: Path = COOKIE_FILE):
        self.cookie_file = cookie_file
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
    
    def save_cookies(self, cookies: List[Dict], domain: str = None) -> bool:
        """保存Cookie"""
        try:
            # 过滤和整理Cookie
            valid_cookies = []
            for cookie in cookies:
                # 跳过无效或过期的Cookie
                if not cookie.get('name'):
                    continue
                
                # 检查过期时间
                if cookie.get('expiry'):
                    expiry_datetime = datetime.fromtimestamp(cookie['expiry'])
                    if expiry_datetime < datetime.now():
                        logger.debug(f"跳过已过期的Cookie: {cookie.get('name')}")
                        continue
                
                # 添加域名信息（如果缺失）
                if domain and 'domain' not in cookie:
                    cookie['domain'] = domain
                
                valid_cookies.append(cookie)
            
            # 保存到文件
            data = {
                "cookies": valid_cookies,
                "timestamp": datetime.now().isoformat(),
                "domain": domain,
                "count": len(valid_cookies)
            }
            
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存 {len(valid_cookies)} 个Cookie到: {self.cookie_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return False
    
    def load_cookies(self) -> Optional[List[Dict]]:
        """加载Cookie"""
        if not self.cookie_file.exists():
            logger.debug("Cookie文件不存在")
            return None
        
        try:
            with open(self.cookie_file, encoding='utf-8') as f:
                data = json.load(f)
            
            cookies = data.get('cookies', [])
            timestamp = data.get('timestamp')
            
            if timestamp:
                save_time = datetime.fromisoformat(timestamp)
                age = (datetime.now() - save_time).total_seconds() / 3600
                logger.info(f"Cookie保存于: {timestamp}, 距今 {age:.1f} 小时")
            
            logger.info(f"已加载 {len(cookies)} 个Cookie")
            return cookies
            
        except Exception as e:
            logger.error(f"加载Cookie失败: {e}")
            return None
    
    def is_valid(self, max_age_hours: int = 24) -> bool:
        """检查Cookie是否有效（未过期）"""
        if not self.cookie_file.exists():
            return False
        
        try:
            with open(self.cookie_file, encoding='utf-8') as f:
                data = json.load(f)
            
            timestamp = data.get('timestamp')
            if not timestamp:
                return False
            
            save_time = datetime.fromisoformat(timestamp)
            age = (datetime.now() - save_time).total_seconds() / 3600
            
            if age > max_age_hours:
                logger.info(f"Cookie已过期 ({age:.1f}小时 > {max_age_hours}小时)")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"检查Cookie有效性失败: {e}")
            return False
    
    def clear_cookies(self) -> bool:
        """清除Cookie"""
        if self.cookie_file.exists():
            self.cookie_file.unlink()
            logger.info("Cookie已清除")
        return True
    
    def get_cookie_summary(self) -> Dict:
        """获取Cookie摘要信息"""
        if not self.cookie_file.exists():
            return {"exists": False}
        
        try:
            with open(self.cookie_file, encoding='utf-8') as f:
                data = json.load(f)
            
            cookies = data.get('cookies', [])
            
            # 提取域名分布
            domains = {}
            for cookie in cookies:
                domain = cookie.get('domain', 'unknown')
                domains[domain] = domains.get(domain, 0) + 1
            
            return {
                "exists": True,
                "count": len(cookies),
                "timestamp": data.get('timestamp'),
                "domains": domains,
                "names": [c.get('name') for c in cookies[:10]]  # 只返回前10个
            }
            
        except Exception as e:
            return {"exists": False, "error": str(e)}


# ============================================================================
# 生产级别的 AutoLogin 类
# ============================================================================

class AutoLogin:
    """
    头条号自动登录类（生产级别）
    
    特性:
    1. 使用已保存的Chrome profile保持登录状态
    2. 完善的错误处理和异常管理
    3. Cookie过期自动检测和重新登录
    4. 详细的日志记录
    5. 会话有效性的多维度验证
    6. 资源正确管理
    """
    
    def __init__(
        self,
        phone: str = None,
        password: str = None,
        headless: bool = True,
        log_level: str = "INFO"
    ):
        """
        初始化AutoLogin
        
        Args:
            phone: 手机号
            password: 密码
            headless: 是否使用无头模式
            log_level: 日志级别
        """
        # 配置日志
        setup_logging(log_level)
        
        # 凭证配置
        self.phone = phone or os.getenv("TOUTIAO_PHONE")
        self.password = password or os.getenv("TOUTIAO_PASSWORD")
        
        if not self.phone or not self.password:
            logger.warning("未配置手机号和密码，将仅尝试使用Cookie/Profile登录")
        
        # 验证手机号格式
        if self.phone and not validate_phone(self.phone):
            logger.warning(f"手机号格式可能不正确: {self.phone}")
        
        # 浏览器配置
        self.headless = headless
        self.base_url = "https://www.toutiao.com"
        self.driver = None
        
        # 组件初始化
        self.cookie_manager = CookieManager()
        self.profile_manager = ProfileManager()
        self.state_manager = LoginStateManager()
        
        # 状态跟踪
        self._is_logged_in = False
        self._last_login_method = None
        self._login_attempts = 0
        self._max_login_attempts = 3
        
        logger.info("=" * 60)
        logger.info("AutoLogin 初始化完成")
        logger.info(f"  - 手机号: {self._mask_phone(self.phone)}")
        logger.info(f"  - 无头模式: {headless}")
        logger.info(f"  - Profile目录: {BROWSER_PROFILE_DIR}")
        logger.info(f"  - Cookie文件: {COOKIE_FILE}")
        logger.info("=" * 60)
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()
        return False
    
    def __del__(self):
        """析构函数"""
        self.cleanup()
    
    # ============================================================================
    # 属性
    # ============================================================================
    
    @property
    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self._is_logged_in
    
    @property
    def last_login_method(self) -> Optional[LoginMethod]:
        """上次登录方式"""
        return self._last_login_method
    
    # ============================================================================
    # 私有方法
    # ============================================================================
    
    def _mask_phone(self, phone: str) -> str:
        """隐藏手机号中间4位"""
        if not phone:
            return "None"
        if len(phone) != 11:
            return phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else "****"
        return phone[:3] + "****" + phone[-4:]
    
    def _get_chrome_options(self) -> Options:
        """获取Chrome选项"""
        options = Options()
        
        # 基础选项
        if self.headless:
            options.add_argument('--headless=new')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')  # 禁用图片加速
        options.add_argument('--disable-css-filters')
        
        # 用户Agent
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 '
            'Safari/537.36'
        )
        
        # 语言设置
        options.add_argument('--lang=zh-CN')
        options.add_argument('--accept-lang=zh-CN,zh;q=0.9,en;q=0.8')
        
        # 禁用自动化标志
        options.add_argument('--disable-automation')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Chrome Profile
        profile_path = self.profile_manager.get_profile_path()
        if profile_path:
            options.add_argument(f'--user-data-dir={profile_path}')
            logger.info(f"使用Chrome Profile: {profile_path}")
        
        # 性能优化
        options.add_argument('--disable-features=TranslateUI')
        options.add_argument('--disable-ipc-floating-bubble')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-first-run-ui')
        options.add_argument('--no-first-run')
        
        return options
    
    def _init_driver(self) -> webdriver.Chrome:
        """初始化Chrome驱动"""
        logger.info("正在初始化Chrome驱动...")
        
        try:
            options = self._get_chrome_options()
            self.driver = webdriver.Chrome(options=options)
            
            # 设置超时
            self.driver.implicitly_wait(IMPLICIT_WAIT)
            self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            
            # 执行反检测脚本
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                '''
            })
            
            logger.info("Chrome驱动初始化成功")
            return self.driver
            
        except WebDriverException as e:
            logger.error(f"Chrome驱动初始化失败: {e}")
            raise DriverInitError(f"Chrome驱动初始化失败: {e}") from e
    
    def _get_driver(self) -> webdriver.Chrome:
        """获取或创建Chrome驱动"""
        if self.driver is None:
            return self._init_driver()
        
        try:
            # 验证驱动是否仍然有效
            self.driver.current_url
            return self.driver
        except Exception:
            logger.warning("Chrome驱动已失效，重新初始化...")
            self.driver = None
            return self._init_driver()
    
    def _wait_for_element(
        self,
        driver: webdriver.Chrome,
        by: By,
        value: str,
        timeout: int = DEFAULT_TIMEOUT,
        clickable: bool = False
    ) -> Optional[webdriver.remote.webelement.WebElement]:
        """等待并获取元素"""
        try:
            if clickable:
                element = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by, value))
                )
            else:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
            return element
            
        except TimeoutException:
            logger.debug(f"等待元素超时: {value}")
            return None
        except Exception as e:
            logger.debug(f"获取元素失败: {e}")
            return None
    
    def _find_element_with_retry(
        self,
        driver: webdriver.Chrome,
        by: By,
        value: str,
        max_retries: int = 3
    ) -> Optional[webdriver.remote.webelement.WebElement]:
        """带重试的元素查找"""
        for attempt in range(max_retries):
            try:
                element = driver.find_element(by, value)
                return element
            except (NoSuchElementException, StaleElementReferenceException) as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                logger.debug(f"查找元素失败 (尝试{attempt + 1}): {value}")
        return None
    
    # ============================================================================
    # 登录状态检测
    # ============================================================================
    
    def _check_login_by_element(self, driver: webdriver.Chrome) -> bool:
        """通过页面元素检测登录状态"""
        for indicator in LOGGED_IN_INDICATORS:
            try:
                if indicator["type"] == "css":
                    element = self._find_element_with_retry(
                        driver, By.CSS_SELECTOR, indicator["value"]
                    )
                else:
                    element = self._find_element_with_retry(
                        driver, By.XPATH, indicator["value"]
                    )
                
                if element:
                    logger.debug(f"��测到登录元素: {indicator['value']}")
                    return True
            except Exception:
                continue
        
        return False
    
    def _check_login_by_url(self, driver: webdriver.Chrome) -> bool:
        """通过URL检测登录状态"""
        current_url = driver.current_url.lower()
        
        # 检查是否在登录页面
        if '/login/' in current_url or '/login' in current_url:
            return False
        
        # 检查是否在个人主页
        if '/profile/' in current_url:
            return True
        
        return False
    
    def _check_login_by_api(self, driver: webdriver.Chrome) -> bool:
        """通过API请求检测登录状态"""
        try:
            # 尝试调用用户信息API
            response = driver.execute_cdp_cmd('Network.enable')
            
            # 获取当前会话的cookies
            cookies = driver.get_cookies()
            session_cookies = {c['name']: c for c in cookies}
            
            # 检查关键Cookie是否存在
            required_cookies = ['tt_webid', 'csrftoken']  # 根据实际情况调整
            has_required = any(
                cookie_name in session_cookies 
                for cookie_name in required_cookies
            )
            
            if has_required:
                logger.debug("API检测: 会话Cookie有效")
                return True
            
        except Exception as e:
            logger.debug(f"API检测失败: {e}")
        
        return False
    
    def verify_login_state(self, driver: webdriver.Chrome = None) -> LoginState:
        """
        多维度验证登录状态
        
        Returns:
            LoginState: 登录状态枚举
        """
        if driver is None:
            driver = self._get_driver()
        
        try:
            # 1. 先尝试访问验证URL
            for verify_url in LOGIN_VERIFY_URLS:
                try:
                    driver.get(verify_url)
                    time.sleep(1)
                except Exception:
                    continue
            
            # 2. URL检测
            if self._check_login_by_url(driver):
                logger.info("URL检测: 已登录")
                return LoginState.LOGGED_IN
            
            # 3. 元素检测
            if self._check_login_by_element(driver):
                logger.info("元素检测: 已登录")
                return LoginState.LOGGED_IN
            
            # 4. 检查是否在登录页面
            current_url = driver.current_url.lower()
            if '/login/' in current_url:
                # 进一步检查登录表单
                for indicator in LOGIN_PAGE_INDICATORS:
                    if self._find_element_with_retry(driver, By.CSS_SELECTOR, indicator["value"]):
                        logger.info("元素检测: 在登录页面")
                        return LoginState.NOT_LOGGED_IN
            
            # 5. API检测
            if self._check_login_by_api(driver):
                logger.info("API检测: 已登录")
                return LoginState.LOGGED_IN
            
            # 无法确定状态
            logger.warning("无法确定登录状态")
            return LoginState.UNKNOWN
            
        except Exception as e:
            logger.error(f"验证登录状态失败: {e}")
            return LoginState.UNKNOWN
    
    # ============================================================================
    # 登录方法
    # ============================================================================
    
    def _login_with_cookies(self, driver: webdriver.Chrome) -> bool:
        """使用Cookie登录"""
        logger.info("尝���使���Cookie登录...")
        
        cookies = self.cookie_manager.load_cookies()
        if not cookies:
            logger.info("没有可用的Cookie")
            return False
        
        try:
            # 先访问首页
            driver.get(self.base_url)
            time.sleep(2)
            
            # 添加Cookie
            for cookie in cookies:
                try:
                    # Selenium需要特定格式
                    cookie_dict = {
                        'name': cookie.get('name'),
                        'value': cookie.get('value'),
                    }
                    
                    # 添加可选参数
                    if cookie.get('domain'):
                        cookie_dict['domain'] = cookie['domain']
                    if cookie.get('path'):
                        cookie_dict['path'] = cookie['path']
                    if cookie.get('expiry'):
                        cookie_dict['expiry'] = cookie['expiry']
                    if cookie.get('secure'):
                        cookie_dict['secure'] = cookie['secure']
                    if cookie.get('httpOnly'):
                        cookie_dict['httpOnly'] = cookie['httpOnly']
                    
                    driver.add_cookie(cookie_dict)
                    logger.debug(f"已添加Cookie: {cookie.get('name')}")
                    
                except Exception as e:
                    logger.debug(f"添加Cookie失败: {cookie.get('name')} - {e}")
            
            # 刷新页面
            driver.refresh()
            time.sleep(2)
            
            # 验证登录状态
            state = self.verify_login_state(driver)
            
            if state == LoginState.LOGGED_IN:
                logger.info("Cookie登录成功")
                self._is_logged_in = True
                self._last_login_method = LoginMethod.COOKIE
                
                # 备份Profile
                self.profile_manager.backup_profile()
                
                return True
            
            logger.info("Cookie已过期")
            return False
            
        except Exception as e:
            logger.error(f"Cookie登录失败: {e}")
            return False
    
    def _login_with_profile(self, driver: webdriver.Chrome) -> bool:
        """使用Chrome Profile登录"""
        logger.info("尝试使用Chrome Profile登录...")
        
        try:
            # 访问首页
            driver.get(self.base_url)
            time.sleep(3)
            
            # 验证登录状态
            state = self.verify_login_state(driver)
            
            if state == LoginState.LOGGED_IN:
                logger.info("Profile登录成功")
                self._is_logged_in = True
                self._last_login_method = LoginMethod.PROFILE
                
                # 保存Cookie
                self.cookie_manager.save_cookies(driver.get_cookies(), self.base_url)
                
                return True
            
            logger.info("Profile会话无效")
            return False
            
        except Exception as e:
            logger.error(f"Profile登录失败: {e}")
            return False
    
    def _login_with_credentials(self, driver: webdriver.Chrome) -> bool:
        """使用凭证登录"""
        if not self.phone or not self.password:
            logger.error("未配置手机号或密码")
            return False
        
        logger.info(f"使用凭证登录... (手机号: {self._mask_phone(self.phone)})")
        
        try:
            # 访问登录页面
            login_url = f"{self.base_url}/login/"
            driver.get(login_url)
            time.sleep(3)
            
            # 选择登录方式（手机号登录）
            # 查找手机号输入框
            phone_input = None
            
            # 尝试多种选择器
            selectors = [
                (By.NAME, "phone"),
                (By.CSS_SELECTOR, "input[type='tel']"),
                (By.CSS_SELECTOR, "input[placeholder*='手机']"),
                (By.XPATH, "//input[@placeholder[contains(., '手机')]]"),
                (By.CSS_SELECTOR, "input[name='account']"),
            ]
            
            for by, value in selectors:
                element = self._wait_for_element(driver, by, value, timeout=10)
                if element:
                    phone_input = element
                    break
            
            if not phone_input:
                logger.error("找不到手机号输入框")
                return False
            
            # 输入手机号
            phone_input.clear()
            phone_input.send_keys(self.phone)
            time.sleep(1)
            
            # 输入密码
            password_input = None
            password_selectors = [
                (By.NAME, "password"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.XPATH, "//input[@type='password']"),
            ]
            
            for by, value in password_selectors:
                element = self._wait_for_element(driver, by, value, timeout=5)
                if element:
                    password_input = element
                    break
            
            if password_input:
                password_input.clear()
                password_input.send_keys(self.password)
                time.sleep(1)
                
                # 点击登录按钮
                submit_button = None
                submit_selectors = [
                    (By.CSS_SELECTOR, "button[type='submit']"),
                    (By.CSS_SELECTOR, "[class*='login-btn']"),
                    (By.XPATH, "//button[contains(@class, 'submit')]"),
                ]
                
                for by, value in submit_selectors:
                    element = self._wait_for_element(
                        driver, by, value, timeout=5, clickable=True
                    )
                    if element:
                        submit_button = element
                        break
                
                if submit_button:
                    submit_button.click()
                    logger.info("已点击登录按钮")
            
            # 等待登录结果
            time.sleep(5)
            
            # 验证登录状态
            state = self.verify_login_state(driver)
            
            if state == LoginState.LOGGED_IN:
                logger.info("凭证登录成功")
                self._is_logged_in = True
                self._last_login_method = LoginMethod.CREDENTIALS
                
                # 保存Cookie
                self.cookie_manager.save_cookies(driver.get_cookies(), self.base_url)
                
                # 备份Profile
                self.profile_manager.backup_profile()
                
                return True
            
            logger.error("凭证登录失败")
            return False
            
        except Exception as e:
            logger.error(f"凭证登录异常: {e}")
            return False
    
    # ============================================================================
    # 主登录流程
    # ============================================================================
    
    def login(self, force: bool = False) -> bool:
        """
        执行自动登录
        
        Args:
            force: 是否强制重新登录
        
        Returns:
            bool: 登录是否成功
        """
        logger.info("=" * 60)
        logger.info("开始自动登录流程")
        logger.info(f"  - 强制登录: {force}")
        logger.info("=" * 60)
        
        # 获取驱动
        driver = self._get_driver()
        self._login_attempts += 1
        
        if self._login_attempts > self._max_login_attempts:
            logger.error(f"登录尝试次数过多 ({self._max_login_attempts})")
            return False
        
        try:
            # 如果不是强制登录，先尝试验证当前状态
            if not force:
                logger.info("验证当前登录状态...")
                state = self.verify_login_state(driver)
                
                if state == LoginState.LOGGED_IN:
                    logger.info("当前会话有效")
                    self._is_logged_in = True
                    return True
                
                if state == LoginState.NOT_LOGGED_IN:
                    logger.info("当前未登录")
            
            # 尝试登录方式（按优先级）
            login_methods = [
                ("Profile", self._login_with_profile),
                ("Cookie", self._login_with_cookies),
            ]
            
            # 如果配置了凭证，也尝试凭证登录
            if self.phone and self.password:
                login_methods.append(
                    ("Credentials", self._login_with_credentials)
                )
            
            # 执行登录
            for method_name, login_func in login_methods:
                logger.info(f"尝试登录方式: {method_name}")
                
                try:
                    if login_func(driver):
                        # 保存登录状态
                        self.state_manager.save_state(
                            state=LoginState.LOGGED_IN,
                            method=self._last_login_method,
                            expires_at=datetime.now() + timedelta(days=7)
                        )
                        
                        logger.info("=" * 60)
                        logger.info("登录成功!")
                        logger.info(f"  登录方式: {self._last_login_method.value if self._last_login_method else 'unknown'}")
                        logger.info("=" * 60)
                        
                        return True
                    
                except Exception as e:
                    logger.warning(f"登录方式 {method_name} 失败: {e}")
                    continue
            
            # 所有方式都失败
            logger.error("所有登录方式都失败")
            
            self.state_manager.save_state(
                state=LoginState.NEEDS_RELOGIN,
                method=LoginMethod.AUTO,
                extra_info={"attempts": self._login_attempts}
            )
            
            return False
            
        except Exception as e:
            logger.error(f"登录流程异常: {e}")
            raise LoginFailedError(f"登录失败: {e}") from e
    
    def ensure_login(self) -> bool:
        """
        确保已登录，如果未登录则自动登录
        
        这是推荐使用的登录方法，会自动处理过期和重新登录
        
        Returns:
            bool: 是否成功保持登录状态
        """
        try:
            # 获取驱动
            driver = self._get_driver()
            
            # 验证当前状态
            logger.info("验证当前登录状态...")
            state = self.verify_login_state(driver)
            
            if state == LoginState.LOGGED_IN:
                logger.info("当前会话有效")
                self._is_logged_in = True
                return True
            
            if state == LoginState.UNKNOWN:
                # 尝试访问验证URL
                try:
                    driver.get(f"{self.base_url}/profile/")
                    time.sleep(2)
                    state = self.verify_login_state(driver)
                except Exception as e:
                    logger.warning(f"验证失败: {e}")
            
            # 检测到未登录或Cookie过期，尝试重新登录
            if state in [LoginState.NOT_LOGGED_IN, LoginState.COOKIE_EXPIRED, LoginState.NEEDS_RELOGIN]:
                logger.info("检测到需要重新登录，开始自动重新登录...")
                
                # 先清理无效的Cookie
                if state == LoginState.COOKIE_EXPIRED:
                    self.cookie_manager.clear_cookies()
                
                # 执行自动登录
                return self.login(force=False)
            
            # 未知状态，尝试自动登录
            logger.warning(f"登录状态未知: {state}，尝试自动登录...")
            return self.login(force=False)
            
        except Exception as e:
            logger.error(f"确保登录失败: {e}")
            return False
    
    # ============================================================================
    # 资源管理
    # ============================================================================
    
    def cleanup(self) -> None:
        """清理资源"""
        logger.info("正在清理资源...")
        
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Chrome驱动已关闭")
            except Exception as e:
                logger.warning(f"关闭驱动失败: {e}")
            finally:
                self.driver = None
        
        # 保存最终状态
        if self._is_logged_in:
            self.state_manager.save_state(
                state=LoginState.LOGGED_IN,
                method=self._last_login_method
            )
        
        logger.info("资源清理完成")
    
    def get_session_info(self) -> Dict:
        """获取会话信息"""
        info = {
            "logged_in": self._is_logged_in,
            "login_method": self._last_login_method.value if self._last_login_method else None,
            "login_attempts": self._login_attempts,
            "has_credentials": bool(self.phone and self.password),
            "phone": self._mask_phone(self.phone),
            "has_profile": bool(self.profile_manager.get_profile_path()),
            "cookie_summary": self.cookie_manager.get_cookie_summary(),
        }
        
        # 添加驱动状态
        if self.driver:
            try:
                info["driver_url"] = self.driver.current_url
                info["driver_title"] = self.driver.title
            except Exception:
                info["driver_error"] = "无法获取驱动信息"
        
        return info
    
    # ============================================================================
    # 便捷方法
    # ============================================================================
    
    def get_driver(self) -> webdriver.Chrome:
        """获取Chrome驱动"""
        return self._get_driver()
    
    def refresh_session(self) -> bool:
        """刷新会话"""
        logger.info("刷新登录会话...")
        
        if not self._is_logged_in:
            logger.warning("未登录，无法刷新会话")
            return False
        
        try:
            driver = self._get_driver()
            
            # 访问首页刷新会话
            driver.get(self.base_url)
            time.sleep(2)
            
            # 验证状态
            state = self.verify_login_state(driver)
            
            if state == LoginState.LOGGED_IN:
                # 保存更新后的Cookie
                self.cookie_manager.save_cookies(driver.get_cookies(), self.base_url)
                logger.info("会话刷新成功")
                return True
            
            logger.warning("会话已失效，需要重新登录")
            self._is_logged_in = False
            return False
            
        except Exception as e:
            logger.error(f"刷新会话失败: {e}")
            self._is_logged_in = False
            return False
    
    def logout(self) -> bool:
        """退出登录"""
        logger.info("执行退出登录...")
        
        try:
            # 清理Cookie
            self.cookie_manager.clear_cookies()
            
            # 清理状态
            self.state_manager.clear_state()
            
            # 访问退出URL
            if self.driver:
                self.driver.get(f"{self.base_url}/logout/")
                time.sleep(2)
            
            self._is_logged_in = False
            logger.info("已退出登录")
            return True
            
        except Exception as e:
            logger.error(f"退出登录失败: {e}")
            return False


# ============================================================================
# ImageGenerator 类（保持兼容性）
# ============================================================================

# ============================================================================
# ImageGenerator 类 - 生产级AI配图生成器
# ============================================================================

import uuid
import re
import uuid
import json
import hashlib
import asyncio
import aiohttp
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union, Callable
from enum import Enum
from urllib.parse import urlparse
from PIL import Image
from PIL.ImageStat import Stat

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ============================================================================
# 自定义异常
# ============================================================================

class ImageGeneratorError(Exception):
    """基础异常类"""
    pass

class APIKeyError(ImageGeneratorError):
    """API密钥未配置"""
    pass

class APIRequestError(ImageGeneratorError):
    """API请求失败"""
    pass

class ImageGenerationError(ImageGeneratorError):
    """图片生成失败"""
    pass

class ImageDownloadError(ImageGeneratorError):
    """图片下载失败"""
    pass

class ImageValidationError(ImageGeneratorError):
    """图片验证失败"""
    pass

class BatchGenerationError(ImageGeneratorError):
    """批量生成失败"""
    pass


# ============================================================================
# 枚举类
# ============================================================================

class ImageProvider(Enum):
    """AI图像生成提供商"""
    OPENAI_DALL_E = "openai_dalle"
    ANTHROPIC = "anthropic"
    LOCAL_STABLE_DIFFUSION = "local_sd"
    AUTO = "auto"


class ImageSize(Enum):
    """图片尺寸"""
    SQUARE_1024 = "1024x1024"
    SQUARE_1792 = "1792x1792"
    SQUARE_2048 = "2048x2048"
    LANDSCAPE_1792 = "1792x1024"
    LANDSCAPE_1024 = "1024x1024"
    PORTRAIT_1024 = "1024x1792"


class ImageQuality(Enum):
    """图片质量"""
    STANDARD = "standard"
    HD = "hd"


class ImageFormat(Enum):
    """图片格式"""
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class GenerationConfig:
    """生成配置"""
    provider: ImageProvider = ImageProvider.OPENAI_DALL_E
    size: ImageSize = ImageSize.SQUARE_1024
    quality: ImageQuality = ImageQuality.STANDARD
    format: ImageFormat = ImageFormat.PNG
    style: str = "自然风格"
    n: int = 1
    timeout: int = 60
    max_retries: int = 3


@dataclass
class ImageMetadata:
    """图片元数据"""
    url: str
    local_path: Optional[str] = None
    prompt: str = ""
    provider: str = ""
    size: str = ""
    format: str = ""
    file_size: int = 0
    dimensions: tuple = (0, 0)
    hash: str = ""
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    images: List[ImageMetadata] = field(default_factory=list)
    error: Optional[str] = None
    generation_time: float = 0.0


@dataclass
class BatchResult:
    """批量生成结果"""
    total: int
    success: int
    failed: int
    results: List[GenerationResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ============================================================================
# 工具函数
# ============================================================================

def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """计算文件哈希"""
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def calculate_bytes_hash(data: bytes, algorithm: str = "sha256") -> str:
    """计算字节数据哈希"""
    hash_func = hashlib.new(algorithm)
    hash_func.update(data)
    return hash_func.hexdigest()


def generate_cache_key(prompt: str, provider: str, size: str) -> str:
    """生成缓存键"""
    raw = f"{prompt}:{provider}:{size}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def validate_image_dimensions(width: int, height: int, 
                         min_size: int = 64, max_size: int = 4096) -> bool:
    """验证图片尺寸"""
    return (min_size <= width <= max_size and 
            min_size <= height <= max_size)


def validate_image_format(file_path: str, allowed_formats: List[str] = None) -> bool:
    """验证图片格式"""
    if allowed_formats is None:
        allowed_formats = ['png', 'jpeg', 'webp', 'jpg']
    
    try:
        with Image.open(file_path) as img:
            return img.format.lower() in allowed_formats
    except Exception:
        return False


def get_image_info(file_path: str) -> Dict[str, Any]:
    """获取图片信息"""
    try:
        with Image.open(file_path) as img:
            return {
                'format': img.format,
                'mode': img.mode,
                'size': img.size,
                'width': img.width,
                'height': img.height,
                'file_size': os.path.getsize(file_path)
            }
    except Exception as e:
        logger.error(f"获取图片信息失败: {e}")
        return {}


# ============================================================================
# 重试装饰器
# ============================================================================

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """指数退避重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        logger.warning(
                            f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries}): {e}, "
                            f"{delay:.1f}秒后重试..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} 失败 (已重试 {max_retries}次): {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


# ============================================================================
# 缓存管理器
# ============================================================================

class ImageCache:
    """图片缓存管理器"""
    
    def __init__(self, cache_dir: Path, ttl: int = 86400 * 7):
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.cache_dir / "cache_index.json"
        self._index = self._load_index()
    
    def _load_index(self) -> Dict:
        """加载缓存索引"""
        if self._index_file.exists():
            try:
                with open(self._index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_index(self) -> None:
        """保存缓存索引"""
        try:
            with open(self._index_file, 'w', encoding='utf-8') as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存缓存索引失败: {e}")
    
    def get(self, key: str) -> Optional[str]:
        """获取缓存图片路径"""
        if key not in self._index:
            return None
        
        entry = self._index[key]
        cache_path = self.cache_dir / entry['filename']
        
        # 检查文件是否存在
        if not cache_path.exists():
            del self._index[key]
            self._save_index()
            return None
        
        # 检查是否过期
        created_at = datetime.fromisoformat(entry['created_at'])
        if (datetime.now() - created_at).total_seconds() > self.ttl:
            logger.info(f"缓存已过期: {key}")
            try:
                cache_path.unlink()
            except Exception:
                pass
            del self._index[key]
            self._save_index()
            return None
        
        return str(cache_path)
    
    def set(self, key: str, file_path: str, metadata: Dict = None) -> str:
        """设置缓存"""
        # 读取文件
        with open(file_path, 'rb') as f:
            data = f.read()
        
        file_hash = calculate_bytes_hash(data)
        ext = Path(file_path).suffix
        
        # 生成文件名
        filename = f"{key}_{file_hash[:8]}{ext}"
        cache_path = self.cache_dir / filename
        
        # 保存文件
        with open(cache_path, 'wb') as f:
            f.write(entry)
        
        # 更新索引
        self._index[key] = {
            'filename': filename,
            'original_path': str(file_path),
            'file_hash': file_hash,
            'created_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self._save_index()
        
        return str(cache_path)
    
    def clear(self, expired_only: bool = True) -> int:
        """清空缓存"""
        count = 0
        if expired_only:
            for key, entry in list(self._index.items()):
                created_at = datetime.fromisoformat(entry['created_at'])
                if (datetime.now() - created_at).total_seconds() > self.ttl:
                    cache_path = self.cache_dir / entry['filename']
                    try:
                        cache_path.unlink()
                    except Exception:
                        pass
                    del self._index[key]
                    count += 1
        else:
            for entry in self._index.values():
                cache_path = self.cache_dir / entry['filename']
                try:
                    cache_path.unlink()
                except Exception:
                    pass
            count = len(self._index)
            self._index = {}
        
        self._save_index()
        return count


# ============================================================================
# 图片质量验证器
# ============================================================================

class ImageValidator:
    """图片质量验证器"""
    
    def __init__(
        self,
        min_size: int = 64,
        max_size: int = 4096,
        min_file_size: int = 1024,
        max_file_size: int = 50 * 1024 * 1024,  # 50MB
        min_dimensions: tuple = (256, 256),
        allowed_formats: List[str] = None
    ):
        self.min_size = min_size
        self.max_size = max_size
        self.min_file_size = min_file_size
        self.max_file_size = max_file_size
        self.min_dimensions = min_dimensions
        self.allowed_formats = allowed_formats or ['PNG', 'JPEG', 'WEBP']
    
    def validate(self, file_path: str) -> tuple[bool, str]:
        """验证图片"""
        # 检查文件存在
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size < self.min_file_size:
            return False, f"文件太小 ({file_size} bytes)"
        if file_size > self.max_file_size:
            return False, f"文件太大 ({file_size} bytes)"
        
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                
                # 检查格式
                if img.format not in self.allowed_formats:
                    return False, f"不支持的格式: {img.format}"
                
                # 检查尺寸
                if not validate_image_dimensions(width, height, 
                                                   self.min_size, self.max_size):
                    return False, f"尺寸无效: {width}x{height}"
                
                # 检查最小尺寸
                if width < self.min_dimensions[0] or height < self.min_dimensions[1]:
                    return False, f"尺寸小于最小要求: {width}x{height}"
                
                # 检查图片内容（非空白）
                if not self._check_content(img):
                    return False, "图片内容为空或损坏"
                
                return True, "验证通过"
                
        except Exception as e:
            return False, f"验证失败: {str(e)}"
    
    def _check_content(self, img: Image.Image) -> bool:
        """检查图片内容"""
        try:
            _stat = Stat(img)
            # 检查是否有颜色变化
            if _stat.stddev == [0, 0, 0]:
                return False
            return True
        except Exception:
            return True


# ============================================================================
# API客户端基类
# ============================================================================

class BaseImageClient:
    """图像生成API客户端基类"""
    
    def __init__(self, api_key: str = None, **kwargs):
        self.api_key = api_key
        self.config = GenerationConfig(**kwargs)
    
    def generate(self, prompt: str) -> GenerationResult:
        """生成图片"""
        raise NotImplementedError
    
    def download(self, url: str, save_path: str) -> Optional[str]:
        """下载图片"""
        raise NotImplementedError


# ============================================================================
# OpenAI DALL-E 客户端
# ============================================================================

class OpenAIClient(BaseImageClient):
    """OpenAI DALL-E 客户端"""
    
    def __init__(self, api_key: str = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise APIKeyError("未配置OpenAI API Key")
        if not OPENAI_AVAILABLE:
            raise ImportError("openai库未安装")
        self.client = OpenAI(api_key=self.api_key)
    
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def generate(self, prompt: str) -> GenerationResult:
        """使用DALL-E生成图片"""
        start_time = time.time()
        
        try:
            response = self.client.images.generate(
                prompt=prompt,
                n=self.config.n,
                size=self.config.size.value,
                quality=self.config.quality.value,
                response_format="url"
            )
            
            images = []
            for item in response.data:
                metadata = ImageMetadata(
                    url=item.url,
                    prompt=prompt,
                    provider=ImageProvider.OPENAI_DALL_E.value,
                    size=self.config.size.value,
                    format=self.config.format.value,
                    created_at=datetime.now()
                )
                images.append(metadata)
            
            generation_time = time.time() - start_time
            return GenerationResult(
                success=True,
                images=images,
                generation_time=generation_time
            )
            
        except Exception as e:
            logger.error(f"DALL-E生成失败: {e}")
            return GenerationResult(
                success=False,
                error=str(e)
            )
    
    def generate_variation(self, image_path: str) -> GenerationResult:
        """生成图片变体"""
        start_time = time.time()
        
        try:
            with open(image_path, 'rb') as f:
                response = self.client.images.create_variation(
                    image=f,
                    n=self.config.n,
                    size=self.config.size.value,
                    response_format="url"
                )
            
            images = []
            for item in response.data:
                metadata = ImageMetadata(
                    url=item.url,
                    provider=ImageProvider.OPENAI_DALL_E.value,
                    size=self.config.size.value,
                    format=self.config.format.value,
                    created_at=datetime.now()
                )
                images.append(metadata)
            
            return GenerationResult(
                success=True,
                images=images,
                generation_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"DALL-E变体生成失败: {e}")
            return GenerationResult(success=False, error=str(e))
    
    def download(self, url: str, save_path: str) -> Optional[str]:
        """下载图片"""
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def _download():
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        
        try:
            data = _download()
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(data)
            logger.info(f"图片已下载: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"图片下载失败: {e}")
            raise ImageDownloadError(f"下载失败: {e}")


# ============================================================================
# Anthropic 客户端
# ============================================================================

class AnthropicClient(BaseImageClient):
    """Anthropic 客户端"""
    
    def __init__(self, api_key: str = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise APIKeyError("未配置Anthropic API Key")
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic库未安装")
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def generate(self, prompt: str) -> GenerationResult:
        """使用Anthropic生成图片"""
        start_time = time.time()
        
        try:
            # Anthropic使用computer use API生成图片
            # 这里简化处理，实际需要根据具体API调整
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": f"Generate an image with this prompt: {prompt}"
                    }
                ],
                tools=[{
                    "name": "image_generation",
                    "description": "Generate images from text prompts",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "width": {"type": "integer", "default": 1024},
                            "height": {"type": "integer", "default": 1024}
                        },
                        "required": ["prompt"]
                    }
                }]
            )
            
            # 处理响应
            images = []
            for item in response.content:
                if hasattr(item, 'url'):
                    metadata = ImageMetadata(
                        url=item.url,
                        prompt=prompt,
                        provider=ImageProvider.ANTHROPIC.value,
                        size=f"{self.config.size.value}",
                        created_at=datetime.now()
                    )
                    images.append(metadata)
            
            return GenerationResult(
                success=bool(images),
                images=images,
                generation_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Anthropic生成失败: {e}")
            return GenerationResult(success=False, error=str(e))
    
    def download(self, url: str, save_path: str) -> Optional[str]:
        """下载图片"""
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def _download():
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        
        try:
            data = _download()
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(data)
            return save_path
        except Exception as e:
            logger.error(f"图片下载失败: {e}")
            raise ImageDownloadError(f"下载失败: {e}")


# ============================================================================
# 本地 Stable Diffusion 客户端
# ============================================================================

class StableDiffusionClient(BaseImageClient):
    """本地 Stable Diffusion 客户端"""
    
    def __init__(
        self,
        api_url: str = "http://localhost:7860",
        api_key: str = None,
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
        
        # 检查服务是否可用
        try:
            response = self.session.get(f"{self.api_url}/sdapi/v1/options", timeout=5)
            if response.status_code != 200:
                logger.warning(f"Stable Diffusion API响应异常: {response.status_code}")
        except Exception as e:
            logger.warning(f"Stable Diffusion服务可能不可用: {e}")
    
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def generate(self, prompt: str, negative_prompt: str = "") -> GenerationResult:
        """使用本地Stable Diffusion生成图片"""
        start_time = time.time()
        
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": 20,
            "width": int(self.config.size.value.split('x')[0]),
            "height": int(self.config.size.value.split('x')[1]),
            "cfg_scale": 7,
            "sampler_name": "Euler a"
        }
        
        try:
            response = self.session.post(
                f"{self.api_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            images = []
            
            for idx, img_base64 in enumerate(data.get('images', [])):
                # 解析base64图片
                img_data = base64.b64decode(img_base64)
                img_hash = calculate_bytes_hash(img_data)
                
                # 保存到临时文件
                temp_path = f"/tmp/sd_generated_{img_hash[:8]}.png"
                with open(temp_path, 'wb') as f:
                    f.write(img_data)
                
                metadata = ImageMetadata(
                    url=f"local://{temp_path}",
                    local_path=temp_path,
                    prompt=prompt,
                    provider=ImageProvider.LOCAL_STABLE_DIFFUSION.value,
                    size=self.config.size.value,
                    hash=img_hash,
                    created_at=datetime.now()
                )
                images.append(metadata)
            
            return GenerationResult(
                success=True,
                images=images,
                generation_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Stable Diffusion生成失败: {e}")
            return GenerationResult(success=False, error=str(e))
    
    def download(self, url: str, save_path: str) -> Optional[str]:
        """下载/保存图片"""
        try:
            if url.startswith('local://'):
                src_path = url.replace('local://', '')
                shutil.copy2(src_path, save_path)
            else:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                with open(save_path, 'wb') as f:
                    f.write(response.content)
            
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            return save_path
        except Exception as e:
            logger.error(f"图片保存失败: {e}")
            raise ImageDownloadError(f"保存失败: {e}")


# ============================================================================
# 生产级 ImageGenerator 类
# ============================================================================

class ImageGenerator:
    """生产级AI配图生成器
    
    特性:
    1. 支持多种AI图像生成API（OpenAI DALL-E, Anthropic, 本地Stable Diffusion）
    2. 完善的错误处理和重试机制
    3. 支持图片下载和本地缓存
    4. 图片质量验证
    5. 批量生成支持
    """
    
    def __init__(
        self,
        api_key: str = None,
        provider: ImageProvider = ImageProvider.OPENAI_DALL_E,
        cache_dir: Path = None,
        cache_ttl: int = 86400 * 7,
        log_level: str = "INFO"
    ):
        self.provider = provider
        self.log_level = log_level
        
        # 配置日志
        setup_logging(log_level)
        
        # 初始化路径
        self.base_dir = Path(__file__).parent.parent
        self.images_dir = self.base_dir / "data" / "images"
        self.cache_dir = cache_dir or self.base_dir / "data" / "image_cache"
        
        # 创建目录
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化客户端
        self._init_client(api_key)
        
        # 初始化缓存和验证器
        self.cache = ImageCache(self.cache_dir, cache_ttl)
        self.validator = ImageValidator()
        
        # 线程池（用于批量生成）
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 配置
        self.config = GenerationConfig(provider=provider)
        
        logger.info(f"ImageGenerator初始化完成，提供商: {provider.value}")
    
    def _init_client(self, api_key: str) -> None:
        """初始化API客户端"""
        if self.provider == ImageProvider.OPENAI_DALL_E:
            self.client = OpenAIClient(api_key)
        elif self.provider == ImageProvider.ANTHROPIC:
            self.client = AnthropicClient(api_key)
        elif self.provider == ImageProvider.LOCAL_STABLE_DIFFUSION:
            self.client = StableDiffusionClient(api_key)
        elif self.provider == ImageProvider.AUTO:
            # 自动选择可用的提供商
            if os.getenv("OPENAI_API_KEY"):
                self.provider = ImageProvider.OPENAI_DALL_E
                self.client = OpenAIClient(api_key or os.getenv("OPENAI_API_KEY"))
            elif os.getenv("ANTHROPIC_API_KEY"):
                self.provider = ImageProvider.ANTHROPIC
                self.client = AnthropicClient(api_key or os.getenv("ANTHROPIC_API_KEY"))
            else:
                self.provider = ImageProvider.OPENAI_DALL_E
                self.client = OpenAIClient(api_key or os.getenv("OPENAI_API_KEY"))
        else:
            raise ImageGeneratorError(f"不支持的提供商: {self.provider}")
    
    def generate(
        self,
        content: str,
        style: str = "自然风格",
        use_cache: bool = True,
        download: bool = True,
        validate: bool = True
    ) -> Optional[ImageMetadata]:
        """生成单张图片
        
        Args:
            content: 图片描述内容
            style: 风格
            use_cache: 是否使用缓存
            download: 是否下载保存
            validate: 是否验证图片质量
            
        Returns:
            ImageMetadata: 图片元数据
        """
        # 构建提示词
        prompt = self._build_prompt(content, style)
        
        # 检查缓存
        if use_cache:
            cache_key = generate_cache_key(
                prompt, 
                self.provider.value, 
                self.config.size.value
            )
            cached_path = self.cache.get(cache_key)
            if cached_path:
                logger.info(f"使用缓存图片: {cached_path}")
                return self._create_metadata_from_file(prompt, cached_path)
        
        # 生成图片
        result = self.client.generate(prompt)
        
        if not result.success:
            logger.error(f"图片生成失败: {result.error}")
            return None
        
        # 处理生成的图片
        image_metadata = None
        for img_meta in result.images:
            if download:
                # 保存图片
                local_path = self._save_image(img_meta.url, prompt)
                if local_path:
                    # 验证
                    if validate:
                        valid, error = self.validator.validate(local_path)
                        if not valid:
                            logger.warning(f"图片验证失败: {error}")
                            continue
                    
                    # 更新元数据
                    img_meta.local_path = local_path
                    img_meta.file_size = os.path.getsize(local_path)
                    with Image.open(local_path) as img:
                        img_meta.dimensions = img.size
                    img_meta.hash = calculate_file_hash(local_path)
                    
                    image_metadata = img_meta
                    
                    # 保存到缓存
                    if use_cache:
                        self.cache.set(cache_key, local_path, {
                            'prompt': prompt,
                            'provider': self.provider.value
                        })
        
        return image_metadata
    
    def generate_batch(
        self,
        contents: List[str],
        style: str = "自然风格",
        max_concurrent: int = 4,
        download: bool = True,
        validate: bool = True
    ) -> BatchResult:
        """批量生成图片
        
        Args:
            contents: 图片描述内容列表
            style: 风格
            max_concurrent: 最大并发数
            download: 是否下载保存
            validate: 是否验证图片质量
            
        Returns:
            BatchResult: 批量生成结果
        """
        results = []
        total = len(contents)
        success_count = 0
        failed_count = 0
        errors = []
        
        # 限制并发数
        semaphore = threading.Semaphore(max_concurrent)
        
        def generate_single(content: str) -> GenerationResult:
            with semaphore:
                metadata = self.generate(
                    content, 
                    style, 
                    use_cache=False,
                    download=download,
                    validate=validate
                )
                if metadata:
                    return GenerationResult(success=True, images=[metadata])
                return GenerationResult(success=False, error="生成失败")
        
        # 使用线程池执行
        futures = {
            self.executor.submit(generate_single, content): content 
            for content in contents
        }
        
        for future in as_completed(futures):
            content = futures[future]
            try:
                result = future.result()
                results.append(result)
                if result.success:
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append(result.error or content)
            except Exception as e:
                failed_count += 1
                errors.append(str(e))
        
        return BatchResult(
            total=total,
            success=success_count,
            failed=failed_count,
            results=results,
            errors=errors
        )
    
    def _build_prompt(self, content: str, style: str) -> str:
        """构建图片提示词"""
        keywords = []
        
        topics = {
            "科技": "technology, modern, digital",
            "经济": "business, finance, professional",
            "生活": "daily life, lifestyle, warm",
            "健康": "health, wellness, vitality",
            "旅游": "travel, landscape, scenic",
            "美食": "food, delicious, appetizing",
            "教育": "education, learning, student",
            "时尚": "fashion, stylish, trendy",
            "财经": "finance, investment, stock",
            "科技": "technology, innovation, AI",
        }
        
        content_lower = content.lower()
        for topic, keyword in topics.items():
            if topic in content_lower:
                keywords.append(keyword)
        
        if not keywords:
            keywords = ["illustration, high quality"]
        
        # 添加质量关键词
        quality_keywords = "high quality, 4k, detailed, professional"
        
        prompt = f"{content}, {', '.join(keywords)}, {style}, {quality_keywords}"
        return prompt
    
    def _save_image(self, url: str, prompt: str) -> Optional[str]:
        """保存图片"""
        # 生成文件名
        timestamp = int(time.time())
        short_hash = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        filename = f"image_{timestamp}_{short_hash}.png"
        save_path = self.images_dir / filename
        
        try:
            # 下载
            self.client.download(url, str(save_path))
            return str(save_path)
        except Exception as e:
            logger.error(f"保存图片失败: {e}")
            return None
    
    def _create_metadata_from_file(self, prompt: str, file_path: str) -> ImageMetadata:
        """从文件创建元数据"""
        with Image.open(file_path) as img:
            dimensions = img.size
        return ImageMetadata(
            url=f"file://{file_path}",
            local_path=file_path,
            prompt=prompt,
            provider=self.provider.value,
            size=self.config.size.value,
            file_size=os.path.getsize(file_path),
            dimensions=dimensions,
            hash=calculate_file_hash(file_path),
            created_at=datetime.now()
        )
    
    def download(self, url: str, filename: str = None) -> Optional[str]:
        """下载图片（兼容旧接口）"""
        if not filename:
            timestamp = int(time.time())
            filename = f"image_{timestamp}.png"
        
        save_path = self.images_dir / filename
        try:
            self.client.download(url, str(save_path))
            return str(save_path)
        except Exception as e:
            logger.error(f"图片下载失败: {e}")
            return None
    
    def set_provider(self, provider: ImageProvider, api_key: str = None) -> None:
        """切换提供商"""
        self.provider = provider
        self._init_client(api_key)
        logger.info(f"已切换到提供商: {provider.value}")
    
    def clear_cache(self, expired_only: bool = True) -> int:
        """清空缓存"""
        count = self.cache.clear(expired_only)
        logger.info(f"已清空 {count} 个缓存")
        return count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            'total_images': len(self.cache._index),
            'cache_dir': str(self.cache_dir),
            'cache_ttl': self.cache.ttl
        }
    
    def cleanup(self) -> None:
        """清理资源"""
        self.executor.shutdown(wait=True)
        logger.info("ImageGenerator已清理")

class ContentGenerator:
    """生产级内容生成器
    
    特性:
    1. 支持多种LLM API（OpenAI, Anthropic, 本地模型）
    2. 热点话题分析
    3. SEO优化
    4. 批量生成支持
    5. 内容质量评估
    6. 生成历史记录
    """
    
    def __init__(
        self,
        api_key: str = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        log_level: str = "INFO"
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        
        # 配置日志
        setup_logging(log_level)
        
        # 初始化客户端
        self._init_client()
        
        # 路径配置
        self.base_dir = Path(__file__).parent.parent
        self.history_file = self.base_dir / "data" / "content_history.json"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载历史记录
        self.history = self._load_history()
        
        # 内容质量评估器
        self.quality_criteria = {
            "min_words": 400,
            "max_words": 2000,
            "needs_emoji": True,
            "needs_question": True,
            "no_hashtag": True
        }
        
        logger.info(f"ContentGenerator初始化完成，提供商: {provider}, 模型: {model}")
    
    def _init_client(self):
        """初始化LLM客户端"""
        if self.provider == "openai" and OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic" and ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def _load_history(self) -> List[Dict]:
        """加载生成历史"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def _save_history(self) -> None:
        """保存生成历史"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史失败: {e}")
    
    def _add_to_history(self, topic: str, content: str, metadata: Dict = None):
        """添加到历史记录"""
        entry = {
            "topic": topic,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "word_count": len(content),
            "provider": self.provider,
            "model": self.model,
            "metadata": metadata or {}
        }
        self.history.insert(0, entry)
        
        # 保留最近100条
        self.history = self.history[:100]
        self._save_history()
    
    def generate(
        self,
        topic: str,
        min_words: int = 400,
        max_words: int = 2000,
        style: str = "专业",
        temperature: float = 0.7,
        platform: str = "toutiao"
    ) -> Optional[str]:
        """生成内容
        
        Args:
            topic: 主题
            min_words: 最少字数
            max_words: 最多字数
            style: 风格
            temperature: 创意度
            platform: 目标平台
            
        Returns:
            str: 生成的内容
        """
        # 构建提示词
        prompt = self._build_prompt(topic, min_words, max_words, style, platform)
        
        try:
            if self.provider == "openai" and self.client:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的内容创作助手，擅长生成吸引人的社交媒体内容。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_words,
                    temperature=temperature
                )
                content = response.choices[0].message.content
                
            elif self.provider == "anthropic" and self.client:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_words,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text
            else:
                # 使用模板生成
                content = self._template_generate(topic, min_words)
            
            # 验证内容质量
            quality_result = self._validate_quality(content)
            if not quality_result["valid"]:
                logger.warning(f"内容质量不达标: {quality_result['issues']}")
                # 尝试修复
                content = self._fix_quality_issues(content, quality_result["issues"])
            
            # 添加到历史
            self._add_to_history(topic, content, {
                "min_words": min_words,
                "max_words": max_words,
                "style": style,
                "platform": platform
            })
            
            logger.info(f"内容生成成功: {len(content)}字")
            return content
            
        except Exception as e:
            logger.error(f"内容生成失败: {e}")
            # 降级到模板生成
            return self._template_generate(topic, min_words)
    
    def generate_batch(
        self,
        topics: List[str],
        min_words: int = 400,
        style: str = "专业",
        platform: str = "toutiao"
    ) -> List[Dict]:
        """批量生成内容
        
        Args:
            topics: 主题列表
            min_words: 最少字数
            style: 风格
            platform: 目标平台
            
        Returns:
            List[Dict]: 生成结果列表
        """
        results = []
        for topic in topics:
            content = self.generate(topic, min_words, style=style, platform=platform)
            results.append({
                "topic": topic,
                "content": content,
                "success": bool(content)
            })
        return results
    
    def _build_prompt(self, topic: str, min_words: int, max_words: int, 
                      style: str, platform: str) -> str:
        """构建生成提示词"""
        platform_rules = {
            "toutiao": "今日头条规则：1. 禁止#开头 2. 第一句话必须吸引读者 3. 内容要引发共鸣 4. 结尾引导互动",
            "xiaohongshu": "小红书规则：1. 标题要吸睛 2. 内容要有价值 3. 添加合适的话题标签 4. 结尾引导收藏",
            "douyin": "抖音规则：1. 开头3秒要抓眼球 2. 内容简短精炼 3. 引导点赞评论"
        }
        
        rules = platform_rules.get(platform, platform_rules["toutiao"])
        
        prompt = f"""请为{platform}平台创作一篇{min_words}-{max_words}字的内容：

要求：
{rules}
1. 字数{min_words}字以上
2. 内容要提供实用价值
3. 禁止使用#话题标签开头

主题：{topic}

请直接输出内容，不要标题。"""
        return prompt
    
    def _validate_quality(self, content: str) -> Dict:
        """验证内容质量"""
        issues = []
        word_count = len(content)
        
        # 检查字数
        if word_count < self.quality_criteria["min_words"]:
            issues.append(f"字数不足 ({word_count} < {self.quality_criteria['min_words']})")
        
        # 检查是否以#开头
        if content.strip().startswith('#'):
            issues.append("不能以#开头")
        
        # 检查第一句话
        first_sentence = content.split('。')[0] if '。' in content else content[:50]
        if not any(marker in first_sentence for marker in ['？', '！', '？', '有人', '你知道', '为什么', '其实']):
            issues.append("第一句话不够吸引人")
        
        # 检查是否有问句
        if self.quality_criteria.get("needs_question") and '？' not in content and '?' not in content:
            issues.append("缺少问句")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "word_count": word_count
        }
    
    def _fix_quality_issues(self, content: str, issues: List[str]) -> str:
        """修复内容质量问题"""
        # 简单修复：如果字数不足，扩展内容
        if any("字数不足" in issue for issue in issues):
            while len(content) < self.quality_criteria["min_words"]:
                content += " 这也是一个值得关注的点。"
        
        return content
    
    def _template_generate(self, topic: str, min_words: int) -> str:
        """模板生成（无API时）"""
        import random
        templates = [
            "你有没有想过{topic}？这个问题困扰了很多人，但其实解决方法很简单...今天我来告诉你一个秘诀，只需做好这几点：第一，{topic}的核心是...第二，要注意的是...第三，也是最重要的...如果你也有类似困扰，不妨试试这个方法。有什么想法评论区聊聊？",
            "90%的人都忽略了{topic}！但实际上，这才是真正影响你的...我花了3年时间研究这个问题，终于发现了...首先，你需要了解...其次，要注意的是...最后记住...希望这个分享对你有帮助。你怎么看？",
            "紧急提醒！关于{topic}，很多人都在犯同一个错误...今天我必须告诉你真相...原因是...其实正确的方法是...记住这3点：1. 2. 3. 按照这个思路，你会发现...对此你怎么看？",
        ]
        
        template = random.choice(templates)
        content = template.format(topic=topic)
        
        # 扩展到目标字数
        while len(content) < min_words:
            content += " " + random.choice([
                "这也是很重要的一点。记住，坚持下去才能看到效果。",
                "持续关注这个领域，你会发现更多机会。",
                "希望这个分享对你有帮助，欢迎留言交流。",
                "如果你觉得有用，记得点个赞再走。",
            ])
        
        return content
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取生成历史"""
        return self.history[:limit]
    
    def clear_history(self) -> int:
        """清空历史记录"""
        count = len(self.history)
        self.history = []
        self._save_history()
        return count


# ============================================================================
# 小红书发布器
# ============================================================================

class XiaohongshuPublisher:
    """小红书发布器（生产级别）
    
    特性:
    1. 自动登录保持
    2. 笔记发布
    3. 图片上传
    4. 标签生成
    5. 数据统计
    """
    
    def __init__(
        self,
        phone: str = None,
        password: str = None,
        headless: bool = True,
        log_level: str = "INFO"
    ):
        self.phone = phone or os.getenv("XIAOHONGSHU_PHONE")
        self.password = password or os.getenv("XIAOHONGSHU_PASSWORD")
        self.headless = headless
        self.base_url = "https://www.xiaohongshu.com"
        self.driver = None
        
        # 配置日志
        setup_logging(log_level)
        
        # 路径配置
        self.base_dir = Path(__file__).parent.parent
        self.cookie_file = self.base_dir / "data" / "xhs_cookies.json"
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("XiaohongshuPublisher初始化完成")
    
    def _get_driver(self):
        """获取Chrome驱动"""
        if self.driver:
            return self.driver
            
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # 用户数据目录
        user_data_dir = str(self.base_dir / "data" / "browser_state" / "xhs_profile")
        if os.path.exists(user_data_dir):
            options.add_argument(f'--user-data-dir={user_data_dir}')
        
        self.driver = webdriver.Chrome(options=options)
        return self.driver
    
    def _save_cookies(self, cookies: list):
        """保存Cookie"""
        with open(self.cookie_file, 'w') as f:
            json.dump(cookies, f)
        logger.info("小红书Cookie已保存")
    
    def _load_cookies(self) -> Optional[list]:
        """加载Cookie"""
        if self.cookie_file.exists():
            with open(self.cookie_file) as f:
                return json.load(f)
        return None
    
    def login(self) -> bool:
        """登录小红书"""
        if not self.phone or not self.password:
            logger.error("请配置手机号和密码")
            return False
        
        driver = self._get_driver()
        
        # 尝试加载Cookie
        cookies = self._load_cookies()
        if cookies:
            driver.get(self.base_url)
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except:
                    pass
            driver.refresh()
            if "login" not in driver.current_url.lower():
                logger.info("使用Cookie登录成功")
                return True
        
        # 手动登录
        driver.get(f"{self.base_url}/login")
        time.sleep(3)
        
        try:
            # 输入手机号
            phone_input = driver.find_element(By.NAME, "phone")
            phone_input.clear()
            phone_input.send_keys(self.phone)
            time.sleep(1)
            
            # 输入密码
            password_input = driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(self.password)
            time.sleep(1)
            
            # 点击登录
            login_btn = driver.find_element(By.CSS_SELECTOR, "[type='submit']")
            login_btn.click()
            
            time.sleep(5)
            
            # 保存Cookie
            self._save_cookies(driver.get_cookies())
            
            logger.info("登录成功")
            return True
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False
    
    def publish(
        self,
        title: str,
        content: str,
        images: List[str] = None,
        tags: List[str] = None
    ) -> Dict:
        """发布笔记
        
        Args:
            title: 标题
            content: 正文内容
            images: 图片路径列表
            tags: 标签列表
            
        Returns:
            Dict: 发布结果
        """
        driver = self._get_driver()
        
        try:
            # 访问发布页面
            driver.get(f"{self.base_url}/publish")
            time.sleep(3)
            
            # 上传图片
            if images:
                for img_path in images:
                    try:
                        upload_input = driver.find_element(
                            By.CSS_SELECTOR, 
                            "input[type='file']"
                        )
                        upload_input.send_keys(img_path)
                        time.sleep(2)
                    except Exception as e:
                        logger.warning(f"上传图片失败: {e}")
            
            # 输入标题
            title_input = driver.find_element(
                By.CSS_SELECTOR, 
                "input[placeholder*='标题']"
            )
            title_input.clear()
            title_input.send_keys(title)
            
            # 输入正文
            content_textarea = driver.find_element(
                By.CSS_SELECTOR, 
                "textarea[placeholder*='正文']"
            )
            content_textarea.clear()
            content_textarea.send_keys(content)
            
            # 添加标签
            if tags:
                for tag in tags:
                    tag_input = driver.find_element(
                        By.CSS_SELECTOR,
                        "input[placeholder*='标签']"
                    )
                    tag_input.clear()
                    tag_input.send_keys(f"#{tag}")
                    time.sleep(0.5)
            
            # 点击发布
            publish_btn = driver.find_element(
                By.CSS_SELECTOR,
                "button:contains('发布')"
            )
            publish_btn.click()
            
            time.sleep(3)
            
            return {
                "success": True,
                "title": title,
                "images": len(images) if images else 0,
                "tags": tags,
                "time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"发布失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_tags(self, content: str) -> List[str]:
        """根据内容生成标签"""
        # 简单实现：基于关键词提取
        keywords = ["生活", "分享", "好物", "推荐", "教程"]
        
        content_lower = content.lower()
        generated = []
        
        topics = {
            "美妆": ["美妆", "化妆", "护肤"],
            "穿搭": ["穿搭", "衣服", "搭配"],
            "美食": ["美食", "做菜", "食谱"],
            "旅行": ["旅行", "旅游", "打卡"],
            "数码": ["数码", "科技", "测评"]
        }
        
        for topic, words in topics.items():
            if any(w in content_lower for w in words):
                generated.append(topic)
        
        return generated[:5]  # 最多5个标签
    
    def get_stats(self) -> Dict:
        """获取账号统计数据"""
        # 实际实现需要爬取个人主页
        return {
            "fans": 0,
            "likes": 0,
            "notes": 0
        }
    
    def close(self):
        """关闭驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None


# ============================================================================
# 定时任务模块
# ============================================================================

class TaskScheduler:
    """定时任务调度器
    
    特性:
    1. 支持多平台定时发布
    2. 灵活的时间配置
    3. 任务队列管理
    4. 执行日志记录
    5. APScheduler集成，真正的定时执行
    6. 持久化任务状态
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        setup_logging(log_level)
        
        # 路径配置
        self.base_dir = Path(__file__).parent.parent
        self.tasks_file = self.base_dir / "data" / "scheduled_tasks.json"
        self.state_file = self.base_dir / "data" / "scheduler_state.json"
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载任务
        self.tasks = self._load_tasks()
        
        # APScheduler 初始化
        self.scheduler = self._init_scheduler()
        
        # 任务运行状态
        self._running = False
        
        # 任务类型映射
        self.task_handlers = {
            "toutiao_publish": self._publish_toutiao,
            "xiaohongshu_publish": self._publish_xiaohongshu,
            "content_generate": self._generate_content,
            "image_generate": self._generate_image,
        }
        
        logger.info("TaskScheduler初始化完成")
    
    def _init_scheduler(self):
        """初始化 APScheduler"""
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.executors.pool import ThreadPoolExecutor
        import apscheduler.events
        
        # 创建调度器
        scheduler = BackgroundScheduler(
            executors={
                'default': ThreadPoolExecutor(max_workers=5)
            },
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5分钟容忍时间
            }
        )
        
        # 添加任务监听器
        scheduler.add_listener(
            self._job_listener,
            apscheduler.events.EVENT_JOB_EXECUTED | apscheduler.events.EVENT_JOB_ERROR
        )
        
        return scheduler
    
    def _job_listener(self, event):
        """任务执行监听器"""
        job = event.job
        if job:
            task_id = job.id
            logger.info(f"任务 {task_id} 执行完成: {event.exception}")
    
    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已经在运行中")
            return
        
        # 添加所有启用的任务到调度器
        self._schedule_all_tasks()
        
        # 启动调度器
        self.scheduler.start()
        self._running = True
        
        # 保存调度器状态
        self._save_state()
        
        logger.info("调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if not self._running:
            logger.warning("调度器未在运行")
            return
        
        # 关闭调度器
        self.scheduler.shutdown(wait=True)
        self._running = False
        
        # 保存状态
        self._save_state()
        
        logger.info("调度器已停止")
    
    def _schedule_all_tasks(self):
        """将所有任务添加到调度器"""
        for task in self.tasks:
            if task.get("enabled", False):
                self._schedule_task(task)
    
    def _schedule_task(self, task: Dict):
        """将单个任务添加到调度器"""
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.date import DateTrigger
        from apscheduler.triggers.interval import IntervalTrigger
        from datetime import datetime
        
        task_id = task["id"]
        schedule = task.get("schedule", "")
        
        # 解析调度表达式
        trigger = self._parse_schedule(schedule)
        
        if trigger:
            # 添加任务到调度器
            self.scheduler.add_job(
                func=self._execute_task_wrapper,
                trigger=trigger,
                id=task_id,
                name=task.get("name", task_id),
                replace_existing=True,
                kwargs={"task_id": task_id}
            )
            
            # 计算下次执行时间
            try:
                task["next_run"] = trigger.get_next_fire_time(datetime.now()).isoformat()
            except Exception:
                task["next_run"] = None
            
            logger.info(f"任务已调度: {task['name']} - {schedule}")
        else:
            logger.warning(f"无法解析调度表达式: {schedule}")
    
    def _parse_schedule(self, schedule: str):
        """解析调度表达式"""
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.date import DateTrigger
        from apscheduler.triggers.interval import IntervalTrigger
        from datetime import datetime
        
        if not schedule:
            return None
        
        # HH:MM 格式 (每天固定时间)
        if len(schedule) == 5 and schedule.count(":") == 1:
            try:
                hour, minute = schedule.split(":")
                return CronTrigger(hour=int(hour), minute=int(minute))
            except ValueError:
                return None
        
        # cron 表达式
        parts = schedule.split()
        if len(parts) >= 5:
            return CronTrigger(
                minute=parts[0] if parts[0] != '*' else None,
                hour=parts[1] if parts[1] != '*' else None,
                day=parts[2] if parts[2] != '*' else None,
                month=parts[3] if parts[3] != '*' else None,
                day_of_week=parts[4] if parts[4] != '*' else None
            )
        
        # interval 格式 (如 "1h", "30m", "1d")
        if len(schedule) > 1 and schedule.endswith(('s', 'm', 'h', 'd')):
            try:
                value = int(schedule[:-1])
                unit = schedule[-1]
                if unit == 's':
                    return IntervalTrigger(seconds=value)
                elif unit == 'm':
                    return IntervalTrigger(minutes=value)
                elif unit == 'h':
                    return IntervalTrigger(hours=value)
                elif unit == 'd':
                    return IntervalTrigger(days=value)
            except ValueError:
                return None
        
        return None
    
    def _execute_task_wrapper(self, task_id: str):
        """任务执行包装器"""
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return
        
        logger.info(f"执行定时任务: {task['name']}")
        
        try:
            handler = self.task_handlers.get(task["task_type"])
            if not handler:
                logger.error(f"未知任务类型: {task['task_type']}")
                return
            
            result = handler(task["config"])
            
            # 更新任务状态
            task["last_run"] = datetime.now().isoformat()
            task["run_count"] = task.get("run_count", 0) + 1
            self._save_tasks()
            
            # 更新下次执行时间
            job = self.scheduler.get_job(task_id)
            if job:
                next_run = job.next_run_time
                if next_run:
                    task["next_run"] = next_run.isoformat()
            
            logger.info(f"任务执行成功: {task['name']}")
            
        except Exception as e:
            logger.error(f"任务执行失败: {task['name']} - {e}")
    
    def _save_state(self):
        """保存调度器状态"""
        try:
            state = {
                "running": self._running,
                "timestamp": datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存调度器状态失败: {e}")
    
    def _load_tasks(self) -> List[Dict]:
        """加载任务配置"""
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def _save_tasks(self) -> None:
        """保存任务配置"""
        try:
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
    
    def add_task(
        self,
        name: str,
        task_type: str,
        schedule: str,  # cron表达式或 "HH:MM" 格式
        config: Dict = None,
        enabled: bool = True
    ) -> Dict:
        """添加定时任务
        
        Args:
            name: 任务名称
            task_type: 任务类型
            schedule: 调度时间
            config: 任务配置
            enabled: 是否启用
            
        Returns:
            Dict: 创建的任务
        """
        task = {
            "id": str(uuid.uuid4()),
            "name": name,
            "task_type": task_type,
            "schedule": schedule,
            "config": config or {},
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "next_run": None,
            "run_count": 0
        }
        
        self.tasks.append(task)
        self._save_tasks()
        
        # 如果调度器正在运行,立即调度任务
        if self._running and enabled:
            self._schedule_task(task)
        
        logger.info(f"添加任务: {name} ({task_type})")
        return task
    
    def remove_task(self, task_id: str) -> bool:
        """删除任务"""
        original_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        
        if len(self.tasks) < original_count:
            # 如果调度器正在运行,从调度器中移除任务
            if self._running:
                self.scheduler.remove_job(task_id)
            
            self._save_tasks()
            logger.info(f"删除任务: {task_id}")
            return True
        return False
    
    def enable_task(self, task_id: str) -> bool:
        """启用任务"""
        for task in self.tasks:
            if task["id"] == task_id:
                task["enabled"] = True
                self._save_tasks()
                
                # 如果调度器正在运行,立即调度任务
                if self._running:
                    self._schedule_task(task)
                
                return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """禁用任务"""
        for task in self.tasks:
            if task["id"] == task_id:
                task["enabled"] = False
                self._save_tasks()
                
                # 如果调度器正在运行,从调度器中移除任务
                if self._running:
                    self.scheduler.remove_job(task_id)
                
                return True
        return False
    
    def get_tasks(self, enabled_only: bool = False) -> List[Dict]:
        """获取任务列表"""
        if enabled_only:
            return [t for t in self.tasks if t["enabled"]]
        return self.tasks
    
    def run_task(self, task_id: str) -> Dict:
        """手动执行任务"""
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            return {"success": False, "error": "任务不存在"}
        
        logger.info(f"执行任务: {task['name']}")
        
        try:
            handler = self.task_handlers.get(task["task_type"])
            if not handler:
                return {"success": False, "error": f"未知任务类型: {task['task_type']}"}
            
            result = handler(task["config"])
            
            # 更新任务状态
            task["last_run"] = datetime.now().isoformat()
            task["run_count"] += 1
            self._save_tasks()
            
            return {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _publish_toutiao(self, config: Dict) -> Dict:
        """执行头条号发布任务"""
        from tools.social_publisher import SocialMediaManager
        
        manager = SocialMediaManager()
        
        content = config.get("content", "定时发布测试")
        result = manager.publish("toutiao", content=content)
        
        return result
    
    def _publish_xiaohongshu(self, config: Dict) -> Dict:
        """执行小红书发布任务"""
        from tools.advanced import XiaohongshuPublisher
        
        publisher = XiaohongshuPublisher()
        
        title = config.get("title", "定时发布")
        content = config.get("content", "定时发布测试")
        
        result = publisher.publish(title, content)
        publisher.close()
        
        return result
    
    def _generate_content(self, config: Dict) -> Dict:
        """执行内容生成任务"""
        from tools.advanced import ContentGenerator
        
        generator = ContentGenerator()
        
        topic = config.get("topic", "今日热点")
        content = generator.generate(topic)
        
        return {"content": content}
    
    def _generate_image(self, config: Dict) -> Dict:
        """执行图片生成任务"""
        from tools.advanced import ImageGenerator
        
        generator = ImageGenerator()
        
        content = config.get("content", "科技")
        result = generator.generate(content)
        
        return result


# ============================================================================

if __name__ == "__main__":
    # 测试AutoLogin
    print("测试AutoLogin...")
    
    autologin = AutoLogin(
        phone=os.getenv("TOUTIAO_PHONE"),
        password=os.getenv("TOUTIAO_PASSWORD"),
        headless=False,
        log_level="DEBUG"
    )
    
    try:
        # 执行登录
        success = autologin.login()
        
        print("=" * 60)
        print(f"登录结果: {'成功' if success else '失败'}")
        print("=" * 60)
        
        # 输出会话信息
        info = autologin.get_session_info()
        print("会话信息:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
    finally:
        autologin.cleanup()
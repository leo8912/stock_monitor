"""
网络请求模块
封装所有网络请求相关的功能
"""

import requests
import time
from typing import Optional, Dict, Any
from ..utils.logger import app_logger


class NetworkManager:
    """网络请求管理器"""
    
    def __init__(self, timeout: int = 10):
        """
        初始化网络管理器
        
        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()
        # 设置默认请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        发送GET请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            Response对象或None（如果失败）
        """
        try:
            if 'timeout' not in kwargs:
                kwargs['timeout'] = self.timeout
                
            response = self.session.get(url, **kwargs)
            response.raise_for_status()  # 检查HTTP错误
            app_logger.debug(f"GET请求成功: {url}")
            return response
        except requests.exceptions.RequestException as e:
            app_logger.error(f"GET请求失败: {url}, 错误: {e}")
            return None
    
    def post(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        发送POST请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            Response对象或None（如果失败）
        """
        try:
            if 'timeout' not in kwargs:
                kwargs['timeout'] = self.timeout
                
            response = self.session.post(url, **kwargs)
            response.raise_for_status()  # 检查HTTP错误
            app_logger.debug(f"POST请求成功: {url}")
            return response
        except requests.exceptions.RequestException as e:
            app_logger.error(f"POST请求失败: {url}, 错误: {e}")
            return None
    
    def github_api_request(self, url: str) -> Optional[Dict[Any, Any]]:
        """
        发送GitHub API请求
        
        Args:
            url: GitHub API URL
            
        Returns:
            JSON响应数据或None（如果失败）
        """
        response = self.get(url)
        if response:
            try:
                return response.json()
            except ValueError as e:
                app_logger.error(f"解析GitHub API响应失败: {e}")
                return None
        return None
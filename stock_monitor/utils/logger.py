import logging
import os
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler

class Logger:
    """日志记录器"""
    
    def __init__(self, name: str = "stock_monitor", log_file: Optional[str] = None, 
                 log_level: int = logging.INFO, max_file_size: int = 10*1024*1024,  # 10MB
                 backup_count: int = 5):
        """
        初始化日志记录器
        
        Args:
            name: 日志记录器名称
            log_file: 日志文件路径，如果为None则只输出到控制台
            log_level: 日志级别
            max_file_size: 单个日志文件最大大小（字节）
            backup_count: 保留的备份日志文件数量
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        
        # 清除现有的处理器以避免重复
        self.logger.handlers.clear()
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 如果指定了日志文件，添加文件处理器（带轮转）
        if log_file:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            # 使用轮转文件处理器
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=max_file_size, 
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别的日志
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """记录一般信息"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """记录警告信息"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录错误信息"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """记录严重错误信息"""
        self.logger.critical(message)

def setup_logger(name: str = "stock_monitor", log_level: int = logging.INFO) -> Logger:
    """
    设置并返回日志记录器实例
    
    Args:
        name: 日志记录器名称
        log_level: 日志级别
        
    Returns:
        Logger实例
    """
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 创建日志目录
        log_dir = os.path.join(project_root, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 日志文件路径
        log_file_path = os.path.join(log_dir, "stock_monitor.log")
        
        # 创建日志记录器
        return Logger(name, log_file_path, log_level)
    except Exception as e:
        # 如果创建文件日志失败，则只使用控制台日志
        print(f"创建文件日志记录器失败: {e}")
        return Logger(name, log_level=log_level)

# 创建全局日志记录器实例
app_logger = setup_logger()
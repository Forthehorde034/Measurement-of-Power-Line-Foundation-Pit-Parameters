import logging
import os
import sys


class LogManager:
    """日志管理工具类"""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._logger = cls._setup_logging()
        return cls._instance
    
    @staticmethod
    def _setup_logging():
        """配置应用程序日志"""
        # 检查是否为打包环境
        if getattr(sys, 'frozen', False):
            # 打包环境 - 使用exe文件所在目录
            exe_dir = os.path.dirname(sys.executable)
            log_dir = os.path.join(exe_dir, 'logs')
        else:
            # 开发环境
            project_root = os.getcwd()
            log_dir = os.path.join(os.path.dirname(project_root), 'logs')
        # 确保日志目录存在
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, 'pcdviewer.log')

        # 创建日志记录器
        logger = logging.getLogger('pcdviewer')
        logger.setLevel(logging.DEBUG)

        # 避免重复添加处理器
        if logger.handlers:
            return logger

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加处理器到记录器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger
    
    @classmethod
    def get_logger(cls):
        """获取日志记录器实例"""
        if cls._instance is None:
            cls()
        return cls._logger
    
    @classmethod
    def debug(cls, message):
        """记录debug级别日志"""
        cls.get_logger().debug(message)
    
    @classmethod
    def info(cls, message):
        """记录info级别日志"""
        cls.get_logger().info(message)
    
    @classmethod
    def warning(cls, message):
        """记录warning级别日志"""
        cls.get_logger().warning(message)
    
    @classmethod
    def error(cls, message):
        """记录error级别日志"""
        cls.get_logger().error(message)

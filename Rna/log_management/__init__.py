"""
RnAgent日志管理模块
提供启动时自动清理功能
"""

from .startup_cleaner import cleanup_logs_on_startup

__all__ = ['cleanup_logs_on_startup'] 
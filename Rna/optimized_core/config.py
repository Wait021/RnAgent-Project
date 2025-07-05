#!/usr/bin/env python3
"""
RNA项目优化版本 - 统一配置管理
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from functools import lru_cache

@dataclass
class ServerConfig:
    """服务器配置"""
    host: str = "localhost"
    frontend_port: int = 8501
    agent_port: int = 8002
    mcp_port: int = 8000
    log_level: str = "INFO"
    max_workers: int = 4

@dataclass
class DataConfig:
    """数据配置"""
    pbmc3k_path: str = "PBMC3kRNA-seq/filtered_gene_bc_matrices/hg19/"
    cache_dir: str = "cache"
    plots_dir: str = "tmp/plots"
    max_cache_size: int = 1024 * 1024 * 1024  # 1GB
    cache_ttl: int = 3600  # 1小时

@dataclass
class PerformanceConfig:
    """性能配置"""
    max_concurrent_requests: int = 10
    request_timeout: int = 300  # 5分钟
    max_log_file_size: int = 100 * 1024 * 1024  # 100MB
    log_backup_count: int = 5
    memory_threshold: float = 0.8  # 80%内存使用率阈值

@dataclass
class CacheConfig:
    """缓存配置"""
    enable_data_cache: bool = True
    enable_plot_cache: bool = True
    enable_result_cache: bool = True
    cache_cleanup_interval: int = 3600  # 1小时清理一次

class Config:
    """统一配置管理器"""
    
    def __init__(self):
        self.server = ServerConfig()
        self.data = DataConfig()
        self.performance = PerformanceConfig()
        self.cache = CacheConfig()
        self._load_from_env()
        self._ensure_directories()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 服务器配置
        self.server.frontend_port = int(os.getenv("FRONTEND_PORT", "8501"))
        self.server.agent_port = int(os.getenv("AGENT_PORT", "8002"))
        self.server.mcp_port = int(os.getenv("MCP_PORT", "8000"))
        self.server.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.server.max_workers = int(os.getenv("MAX_WORKERS", "4"))
        
        # 数据配置
        self.data.pbmc3k_path = os.getenv("PBMC3K_PATH", self.data.pbmc3k_path)
        self.data.cache_dir = os.getenv("CACHE_DIR", "cache")
        self.data.plots_dir = os.getenv("PLOTS_DIR", "tmp/plots")
        
        # 性能配置
        self.performance.max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
        self.performance.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "300"))
        
        # 缓存配置
        self.cache.enable_data_cache = os.getenv("ENABLE_DATA_CACHE", "true").lower() == "true"
        self.cache.enable_plot_cache = os.getenv("ENABLE_PLOT_CACHE", "true").lower() == "true"
        self.cache.enable_result_cache = os.getenv("ENABLE_RESULT_CACHE", "true").lower() == "true"
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        directories = [
            self.data.cache_dir,
            self.data.plots_dir,
            "logs"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    @property
    def api_keys(self) -> Dict[str, Optional[str]]:
        """获取API密钥配置"""
        return {
            "openai": os.getenv("OPENAI_API_KEY"),
            "deepseek": os.getenv("DEEPSEEK_API_KEY")
        }
    
    def get_data_path(self, filename: str = "") -> str:
        """获取数据文件路径"""
        return os.path.join(self.data.pbmc3k_path, filename)
    
    def get_cache_path(self, filename: str = "") -> str:
        """获取缓存文件路径"""
        return os.path.join(self.data.cache_dir, filename)
    
    def get_plots_path(self, filename: str = "") -> str:
        """获取图片文件路径"""
        return os.path.join(self.data.plots_dir, filename)

# 全局配置实例
@lru_cache(maxsize=1)
def get_config() -> Config:
    """获取全局配置实例（单例模式）"""
    return Config()

# 配置验证
def validate_config() -> bool:
    """验证配置有效性"""
    config = get_config()
    
    # 检查数据路径
    if not os.path.exists(config.data.pbmc3k_path):
        print(f"⚠️ 数据路径不存在: {config.data.pbmc3k_path}")
        return False
    
    # 检查必要文件
    required_files = ['matrix.mtx', 'barcodes.tsv', 'genes.tsv']
    for file in required_files:
        if not os.path.exists(config.get_data_path(file)):
            print(f"⚠️ 缺少必要文件: {file}")
            return False
    
    # 检查API密钥
    api_keys = config.api_keys
    if not any(api_keys.values()):
        print("⚠️ 未设置任何API密钥")
        return False
    
    return True

if __name__ == "__main__":
    # 配置测试
    config = get_config()
    print("🔧 配置信息:")
    print(f"  服务器: {config.server}")
    print(f"  数据: {config.data}")
    print(f"  性能: {config.performance}")
    print(f"  缓存: {config.cache}")
    print(f"  API密钥: {list(config.api_keys.keys())}")
    
    if validate_config():
        print("✅ 配置验证通过")
    else:
        print("❌ 配置验证失败") 
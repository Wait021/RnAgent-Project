#!/usr/bin/env python3
"""
RnAgent 统一配置管理
支持本地和服务器环境
"""

import os
import platform
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class EnvironmentConfig:
    """环境配置"""
    name: str
    data_path: str
    host: str = "localhost"
    frontend_port: int = 8501
    agent_port: int = 8002
    mcp_port: int = 8000
    log_level: str = "INFO"

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.current_env = self._detect_environment()
        self.config = self._load_config()
    
    def _detect_environment(self) -> str:
        """自动检测运行环境"""
        # 检查环境变量
        env_var = os.getenv("RNA_ENV")
        if env_var:
            return env_var
        
        # 检查是否在服务器上（通过特定路径或主机名）
        if os.path.exists("/home") and platform.system() == "Linux":
            return "server"
        
        # 检查是否在macOS本地开发
        if platform.system() == "Darwin":
            return "local"
        
        # 默认为本地环境
        return "local"
    
    def _load_config(self) -> EnvironmentConfig:
        """加载环境配置"""
        if self.current_env == "local":
            return self._get_local_config()
        elif self.current_env == "server":
            return self._get_server_config()
        else:
            raise ValueError(f"未知环境: {self.current_env}")
    
    def _get_local_config(self) -> EnvironmentConfig:
        """本地开发环境配置"""
        return EnvironmentConfig(
            name="local",
            data_path="/Volumes/T7/哈尔滨工业大学-2025/课题组项目/Agent-项目/PBMC3kRNA-seq/filtered_gene_bc_matrices/hg19/",
            host="localhost",
            frontend_port=8501,
            agent_port=8002,
            mcp_port=8000,
            log_level="DEBUG"
        )
    
    def _get_server_config(self) -> EnvironmentConfig:
        """服务器环境配置"""
        # 从环境变量获取用户名，或使用默认值
        username = os.getenv("USER", "ubuntu")
        base_path = f"/workspace/rna_project"
        
        return EnvironmentConfig(
            name="server",
            data_path=f"{base_path}/PBMC3kRNA-seq/filtered_gene_bc_matrices/hg19/",
            host="0.0.0.0",  # 监听所有接口
            frontend_port=8501,
            agent_port=8002,
            mcp_port=8000,
            log_level="INFO"
        )
    
    def get_data_path(self, filename: str = "") -> str:
        """获取数据文件路径"""
        return os.path.join(self.config.data_path, filename)
    
    def get_cache_path(self, filename: str = "") -> str:
        """获取缓存文件路径"""
        cache_dir = "cache"
        Path(cache_dir).mkdir(exist_ok=True)
        return os.path.join(cache_dir, filename)
    
    def get_plots_path(self, filename: str = "") -> str:
        """获取图片输出路径"""
        plots_dir = "tmp/plots"
        Path(plots_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(plots_dir, filename)
    
    @property
    def api_keys(self) -> Dict[str, Optional[str]]:
        """获取API密钥"""
        return {
            "openai": os.getenv("OPENAI_API_KEY"),
            "deepseek": os.getenv("DEEPSEEK_API_KEY")
        }
    
    def validate_config(self) -> bool:
        """验证配置是否有效"""
        # 检查数据路径
        if not os.path.exists(self.config.data_path):
            print(f"❌ 数据路径不存在: {self.config.data_path}")
            return False
        
        # 检查必需的数据文件
        required_files = ['matrix.mtx', 'barcodes.tsv', 'genes.tsv']
        for file in required_files:
            file_path = os.path.join(self.config.data_path, file)
            if not os.path.exists(file_path):
                print(f"❌ 缺少数据文件: {file}")
                return False
        
        # 检查API密钥
        if not any(self.api_keys.values()):
            print("⚠️ 未设置API密钥")
            return False
        
        return True
    
    def print_config_info(self):
        """打印配置信息"""
        print(f"\n📋 当前环境配置:")
        print(f"  环境: {self.config.name}")
        print(f"  数据路径: {self.config.data_path}")
        print(f"  监听地址: {self.config.host}")
        print(f"  前端端口: {self.config.frontend_port}")
        print(f"  Agent端口: {self.config.agent_port}")
        print(f"  MCP端口: {self.config.mcp_port}")
        print(f"  日志级别: {self.config.log_level}")
        
        # API密钥状态
        openai_key = "✅" if self.api_keys["openai"] else "❌"
        deepseek_key = "✅" if self.api_keys["deepseek"] else "❌"
        print(f"  OpenAI密钥: {openai_key}")
        print(f"  DeepSeek密钥: {deepseek_key}")

# 全局配置实例
config_manager = ConfigManager()

def get_config() -> EnvironmentConfig:
    """获取当前环境配置"""
    return config_manager.config

def get_data_path(filename: str = "") -> str:
    """获取数据路径"""
    return config_manager.get_data_path(filename)

def get_cache_path(filename: str = "") -> str:
    """获取缓存路径"""
    return config_manager.get_cache_path(filename)

def get_plots_path(filename: str = "") -> str:
    """获取图片路径"""
    return config_manager.get_plots_path(filename) 
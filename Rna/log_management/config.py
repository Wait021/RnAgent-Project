"""
日志管理配置
"""

# 启动时清理配置
STARTUP_CLEANUP_CONFIG = {
    # 清理动作: "delete" 删除文件, "truncate" 清空内容
    "action": "delete",
    
    # 是否显示详细日志
    "verbose": True,
    
    # 需要扫描的日志文件模式
    "log_patterns": [
        "1_frontend/*.log",
        "2_agent_core/*.log", 
        "3_backend_mcp/*.log",
        "optimized_core/logs/*.log",
        "logs/*.log",
        "*.log",
        "tmp/logs/*.log",
        "cache/*.log",
        "**/logs/*.log",
    ],
    
    # 排除的文件模式（不删除这些文件）
    "exclude_patterns": [
        # 可以在这里添加不希望删除的日志文件
    ]
} 
#!/usr/bin/env python3
"""
启动时日志清理器
在RnAgent启动时自动清理所有日志文件
"""

import os
import glob
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_log_files(base_dir: str) -> List[str]:
    """
    获取所有日志文件路径
    
    Args:
        base_dir: 项目根目录
        
    Returns:
        日志文件路径列表
    """
    log_patterns = [
        # 主要日志文件
        "1_frontend/*.log",
        "2_agent_core/*.log", 
        "3_backend_mcp/*.log",
        "optimized_core/logs/*.log",
        "logs/*.log",
        "*.log",
        
        # 临时和缓存日志
        "tmp/logs/*.log",
        "cache/*.log",
        "**/logs/*.log",
    ]
    
    log_files = []
    for pattern in log_patterns:
        files = glob.glob(os.path.join(base_dir, pattern), recursive=True)
        log_files.extend(files)
    
    # 去重并排序
    return sorted(list(set(log_files)))


def cleanup_single_log(file_path: str, action: str = "delete") -> Tuple[bool, str]:
    """
    清理单个日志文件
    
    Args:
        file_path: 文件路径
        action: 清理动作 ("delete"=删除, "truncate"=清空内容)
        
    Returns:
        (是否成功, 结果消息)
    """
    try:
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"
        
        file_size = os.path.getsize(file_path)
        
        if action == "delete":
            os.remove(file_path)
            return True, f"删除 {file_path} ({file_size} bytes)"
            
        elif action == "truncate":
            with open(file_path, 'w') as f:
                f.write("")
            return True, f"清空 {file_path} ({file_size} bytes)"
        else:
            return False, f"未知操作: {action}"
            
    except PermissionError:
        return False, f"权限不足: {file_path}"
    except Exception as e:
        return False, f"处理失败 {file_path}: {str(e)}"


def cleanup_logs_on_startup(base_dir: str | None = None, action: str = "delete", dry_run: bool = False) -> dict:
    """
    启动时清理日志文件
    
    Args:
        base_dir: 项目根目录，默认为当前目录的父目录
        action: 清理动作 ("delete"=删除文件, "truncate"=清空内容)
        dry_run: 是否为模拟运行
        
    Returns:
        清理结果统计
    """
    if base_dir is None:
        # 默认为当前脚本所在目录的父目录（即Rna目录）
        current_dir = Path(__file__).parent.parent
        base_dir = str(current_dir.absolute())
    
    logger.info(f"🧹 开始启动时日志清理 (模式: {'模拟' if dry_run else action})")
    logger.info(f"📁 扫描目录: {base_dir}")
    
    # 获取所有日志文件
    log_files = get_log_files(base_dir)
    
    if not log_files:
        logger.info("✅ 未发现日志文件")
        return {
            "total_files": 0,
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "total_size_freed": 0
        }
    
    logger.info(f"📋 发现 {len(log_files)} 个日志文件")
    
    # 统计信息
    stats = {
        "total_files": len(log_files),
        "processed": 0,
        "skipped": 0, 
        "errors": 0,
        "total_size_freed": 0
    }
    
    # 处理每个文件
    for file_path in log_files:
        try:
            if not os.path.exists(file_path):
                stats["skipped"] += 1
                continue
                
            file_size = os.path.getsize(file_path)
            
            if dry_run:
                logger.info(f"[模拟] 将{action} {file_path} ({file_size} bytes)")
                stats["processed"] += 1
                stats["total_size_freed"] += file_size
            else:
                success, message = cleanup_single_log(file_path, action)
                if success:
                    logger.info(f"✅ {message}")
                    stats["processed"] += 1
                    stats["total_size_freed"] += file_size
                else:
                    logger.warning(f"⚠️ {message}")
                    stats["errors"] += 1
                    
        except Exception as e:
            logger.error(f"❌ 处理文件时出错 {file_path}: {str(e)}")
            stats["errors"] += 1
    
    # 打印统计结果
    print("\n" + "="*60)
    print("📊 清理统计结果")
    print("="*60)
    print(f"总文件数: {stats['total_files']}")
    print(f"已处理: {stats['processed']}")
    print(f"跳过: {stats['skipped']}")
    print(f"错误: {stats['errors']}")
    print(f"释放空间: {stats['total_size_freed']} bytes ({stats['total_size_freed']/1024:.1f} KB)")
    print("="*60)
    
    if dry_run:
        print("🔍 这是模拟运行，实际文件未被修改")
    else:
        print(f"✅ 日志清理完成 ({'删除' if action == 'delete' else '清空'})")
    
    return stats


def main():
    """命令行测试入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RnAgent启动时日志清理器")
    parser.add_argument("--base-dir", type=str, help="项目根目录")
    parser.add_argument("--action", choices=["delete", "truncate"], 
                       default="delete", help="清理动作")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行")
    
    args = parser.parse_args()
    
    cleanup_logs_on_startup(
        base_dir=args.base_dir,
        action=args.action,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main() 
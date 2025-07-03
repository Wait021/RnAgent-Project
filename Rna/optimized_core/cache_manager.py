#!/usr/bin/env python3
"""
RNA项目优化版本 - 智能缓存管理系统
"""

import os
import pickle
import hashlib
import time
import psutil
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock
import weakref
import gc

from config import get_config

class CacheEntry:
    """缓存条目"""
    
    def __init__(self, value: Any, ttl: int = 3600):
        self.value = value
        self.created_time = time.time()
        self.access_time = time.time()
        self.access_count = 1
        self.ttl = ttl
        self.size = self._calculate_size(value)
    
    def _calculate_size(self, obj: Any) -> int:
        """计算对象大小（估算）"""
        try:
            if hasattr(obj, '__sizeof__'):
                return obj.__sizeof__()
            else:
                return len(pickle.dumps(obj))
        except:
            return 1024  # 默认1KB
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.created_time > self.ttl
    
    def touch(self):
        """更新访问时间"""
        self.access_time = time.time()
        self.access_count += 1

class InMemoryCache:
    """内存缓存管理器"""
    
    def __init__(self, max_size: int = 512 * 1024 * 1024):  # 512MB
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self.max_size = max_size
        self.current_size = 0
        
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry.is_expired():
                    del self._cache[key]
                    self.current_size -= entry.size
                    return None
                else:
                    entry.touch()
                    return entry.value
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存值"""
        with self._lock:
            entry = CacheEntry(value, ttl)
            
            # 检查内存使用率
            if self._should_evict(entry.size):
                self._evict_entries(entry.size)
            
            # 如果键已存在，更新大小
            if key in self._cache:
                self.current_size -= self._cache[key].size
            
            self._cache[key] = entry
            self.current_size += entry.size
    
    def _should_evict(self, new_size: int) -> bool:
        """判断是否需要清理缓存"""
        return (self.current_size + new_size) > self.max_size
    
    def _evict_entries(self, required_size: int):
        """清理缓存条目（LRU策略）"""
        # 按访问时间排序，优先清理最久未访问的
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1].access_time
        )
        
        freed_size = 0
        for key, entry in sorted_items:
            if freed_size >= required_size:
                break
            
            del self._cache[key]
            freed_size += entry.size
            self.current_size -= entry.size
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self.current_size = 0
    
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_entries = len(self._cache)
            total_accesses = sum(entry.access_count for entry in self._cache.values())
            
            return {
                "total_entries": total_entries,
                "current_size_mb": round(self.current_size / (1024 * 1024), 2),
                "max_size_mb": round(self.max_size / (1024 * 1024), 2),
                "memory_usage_percent": round((self.current_size / self.max_size) * 100, 2),
                "total_accesses": total_accesses,
                "avg_accesses_per_entry": round(total_accesses / max(total_entries, 1), 2)
            }

class DiskCache:
    """磁盘缓存管理器"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
    
    def _get_file_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.cache"
    
    def _get_meta_path(self, key: str) -> Path:
        """获取元数据文件路径"""
        return self.cache_dir / f"{key}.meta"
    
    def get(self, key: str) -> Optional[Any]:
        """从磁盘获取缓存"""
        file_path = self._get_file_path(key)
        meta_path = self._get_meta_path(key)
        
        if not file_path.exists() or not meta_path.exists():
            return None
        
        try:
            # 检查元数据
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            # 检查是否过期
            if time.time() > meta['expires_at']:
                self._remove_cache_files(key)
                return None
            
            # 读取缓存数据
            with open(file_path, 'rb') as f:
                value = pickle.load(f)
            
            # 更新访问时间
            meta['access_time'] = time.time()
            meta['access_count'] += 1
            with open(meta_path, 'w') as f:
                json.dump(meta, f)
            
            return value
            
        except Exception as e:
            print(f"读取磁盘缓存失败: {e}")
            self._remove_cache_files(key)
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """保存到磁盘缓存"""
        file_path = self._get_file_path(key)
        meta_path = self._get_meta_path(key)
        
        try:
            with self._lock:
                # 保存数据
                with open(file_path, 'wb') as f:
                    pickle.dump(value, f)
                
                # 保存元数据
                meta = {
                    'created_time': time.time(),
                    'access_time': time.time(),
                    'access_count': 1,
                    'expires_at': time.time() + ttl,
                    'ttl': ttl
                }
                with open(meta_path, 'w') as f:
                    json.dump(meta, f)
                    
        except Exception as e:
            print(f"保存磁盘缓存失败: {e}")
            self._remove_cache_files(key)
    
    def _remove_cache_files(self, key: str):
        """删除缓存文件"""
        file_path = self._get_file_path(key)
        meta_path = self._get_meta_path(key)
        
        try:
            if file_path.exists():
                file_path.unlink()
            if meta_path.exists():
                meta_path.unlink()
        except Exception as e:
            print(f"删除缓存文件失败: {e}")
    
    def clear(self):
        """清空磁盘缓存"""
        try:
            for file_path in self.cache_dir.glob("*.cache"):
                file_path.unlink()
            for file_path in self.cache_dir.glob("*.meta"):
                file_path.unlink()
        except Exception as e:
            print(f"清空磁盘缓存失败: {e}")
    
    def cleanup_expired(self):
        """清理过期的缓存文件"""
        current_time = time.time()
        
        for meta_path in self.cache_dir.glob("*.meta"):
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                
                if current_time > meta['expires_at']:
                    key = meta_path.stem
                    self._remove_cache_files(key)
                    
            except Exception as e:
                print(f"清理过期缓存失败: {e}")
                # 删除损坏的文件
                try:
                    meta_path.unlink()
                except:
                    pass

class CacheManager:
    """统一缓存管理器"""
    
    def __init__(self):
        self.config = get_config()
        self.memory_cache = InMemoryCache()
        self.disk_cache = DiskCache(self.config.get_cache_path())
        self._cleanup_timer = None
        self._start_cleanup_timer()
    
    def cache_result(self, ttl: int = 3600, use_disk: bool = False):
        """缓存装饰器"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                key = self.memory_cache._generate_key(func.__name__, args, kwargs)
                
                # 先尝试内存缓存
                result = self.memory_cache.get(key)
                if result is not None:
                    return result
                
                # 再尝试磁盘缓存
                if use_disk and self.config.cache.enable_data_cache:
                    result = self.disk_cache.get(key)
                    if result is not None:
                        # 将结果放回内存缓存
                        self.memory_cache.set(key, result, ttl)
                        return result
                
                # 缓存未命中，执行函数
                result = func(*args, **kwargs)
                
                # 保存到缓存
                self.memory_cache.set(key, result, ttl)
                if use_disk and self.config.cache.enable_data_cache:
                    self.disk_cache.set(key, result, ttl)
                
                return result
            return wrapper
        return decorator
    
    def _start_cleanup_timer(self):
        """启动定期清理任务"""
        import threading
        
        def cleanup_task():
            while True:
                time.sleep(self.config.cache.cache_cleanup_interval)
                self.cleanup()
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    def cleanup(self):
        """清理过期缓存"""
        try:
            # 清理磁盘缓存
            self.disk_cache.cleanup_expired()
            
            # 检查内存使用率
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > self.config.performance.memory_threshold * 100:
                # 内存使用率过高，清理部分内存缓存
                self.memory_cache._evict_entries(self.memory_cache.current_size // 4)
                gc.collect()  # 强制垃圾回收
                
        except Exception as e:
            print(f"缓存清理失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        memory_stats = self.memory_cache.stats()
        
        # 磁盘缓存统计
        disk_files = list(self.disk_cache.cache_dir.glob("*.cache"))
        disk_size = sum(f.stat().st_size for f in disk_files)
        
        system_memory = psutil.virtual_memory()
        
        return {
            "memory_cache": memory_stats,
            "disk_cache": {
                "total_files": len(disk_files),
                "total_size_mb": round(disk_size / (1024 * 1024), 2)
            },
            "system_memory": {
                "total_gb": round(system_memory.total / (1024**3), 2),
                "available_gb": round(system_memory.available / (1024**3), 2),
                "used_percent": system_memory.percent
            }
        }
    
    def clear_all(self):
        """清空所有缓存"""
        self.memory_cache.clear()
        self.disk_cache.clear()

# 全局缓存管理器实例
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

# 便捷装饰器
def cache_result(ttl: int = 3600, use_disk: bool = False):
    """缓存结果装饰器"""
    return get_cache_manager().cache_result(ttl, use_disk)

if __name__ == "__main__":
    # 缓存系统测试
    cache_mgr = get_cache_manager()
    
    @cache_result(ttl=60, use_disk=True)
    def expensive_calculation(n: int) -> int:
        """模拟耗时计算"""
        time.sleep(2)
        return sum(range(n))
    
    print("🧪 测试缓存系统...")
    
    start_time = time.time()
    result1 = expensive_calculation(1000)
    first_time = time.time() - start_time
    print(f"首次调用: {result1}, 耗时: {first_time:.2f}s")
    
    start_time = time.time()
    result2 = expensive_calculation(1000)
    second_time = time.time() - start_time
    print(f"缓存调用: {result2}, 耗时: {second_time:.2f}s")
    
    print(f"性能提升: {first_time/second_time:.2f}x")
    print(f"缓存统计: {cache_mgr.get_stats()}") 
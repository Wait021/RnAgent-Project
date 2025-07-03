#!/usr/bin/env python3
"""
RNA项目优化版本 - 执行环境管理器
解决Python REPL重复初始化问题，提升代码执行效率
"""

import os
import sys
import time
import threading
import traceback
import json
from io import StringIO
from typing import Dict, Any, Optional, List, Tuple
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt

class ExecutionManager:
    """优化的执行管理器"""
    
    def __init__(self):
        self.initialized = False
        self.lock = threading.Lock()
        self.globals_dict = {}
        self.stats = {
            "total_executions": 0,
            "total_execution_time": 0.0,
            "cache_hits": 0
        }
        self._init_environment()
    
    def _init_environment(self):
        """初始化执行环境"""
        if self.initialized:
            return
            
        with self.lock:
            if self.initialized:
                return
                
            print("🔧 [执行环境] 初始化Python REPL环境...")
            start_time = time.time()
            
            init_code = """
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import scanpy as sc
import warnings
warnings.filterwarnings('ignore')

sc.settings.verbosity = 1
sc.settings.set_figure_params(dpi=80, dpi_save=150)
plt.rcParams['figure.figsize'] = (8, 6)
plt.ioff()

print("✅ RNA分析环境初始化完成")
"""
            
            try:
                exec(init_code, self.globals_dict)
                self.initialized = True
                init_time = time.time() - start_time
                print(f"✅ [执行环境] 初始化完成，耗时: {init_time:.2f}s")
            except Exception as e:
                print(f"❌ [执行环境] 初始化失败: {e}")
                raise
    
    def execute_code(self, code: str) -> Dict[str, Any]:
        """执行代码"""
        with self.lock:
            return self._execute_with_capture(code)
    
    def _execute_with_capture(self, code: str) -> Dict[str, Any]:
        """执行代码并捕获输出"""
        start_time = time.time()
        
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        plot_paths = []
        error_msg = None
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, self.globals_dict)
            plot_paths = self._save_plots()
        except Exception as e:
            error_msg = str(e)
            stderr_capture.write(f"\nError: {error_msg}\n")
            stderr_capture.write(traceback.format_exc())
        
        execution_time = time.time() - start_time
        self.stats["total_executions"] += 1
        self.stats["total_execution_time"] += execution_time
        
        return {
            "success": error_msg is None,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "error": error_msg,
            "plots": plot_paths,
            "execution_time": execution_time
        }
    
    def _save_plots(self) -> List[str]:
        """保存matplotlib图表"""
        plot_paths = []
        
        try:
            fig_nums = plt.get_fignums()
            if fig_nums:
                os.makedirs("tmp/plots", exist_ok=True)
                for i, fig_num in enumerate(fig_nums):
                    fig = plt.figure(fig_num)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                    filename = f"plot_{timestamp}_{i}.png"
                    file_path = f"tmp/plots/{filename}"
                    
                    fig.set_size_inches(10.0, 6.0)
                    fig.savefig(file_path, bbox_inches='tight', dpi=150)
                    plot_paths.append(file_path)
                
                plt.close('all')
        except Exception as e:
            print(f"保存图表时出错: {e}")
        
        return plot_paths
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "initialized": self.initialized,
            "globals_count": len(self.globals_dict),
            "has_adata": 'adata' in self.globals_dict,
            "execution_stats": self.stats,
            "avg_execution_time": (
                self.stats["total_execution_time"] / max(self.stats["total_executions"], 1)
            )
        }

# 全局实例
_execution_manager = None

def get_execution_manager() -> ExecutionManager:
    """获取全局执行管理器实例"""
    global _execution_manager
    if _execution_manager is None:
        _execution_manager = ExecutionManager()
    return _execution_manager

if __name__ == "__main__":
    # 测试
    manager = get_execution_manager()
    result = manager.execute_code("print('Hello, optimized RNA Analysis!')")
    print("测试结果:", result["success"])
    print("统计信息:", manager.get_stats()) 
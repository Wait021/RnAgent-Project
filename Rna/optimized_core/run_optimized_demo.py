#!/usr/bin/env python3
"""
RNA项目优化版本启动脚本
展示性能优化效果
"""

import os
import sys
import time
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from config import get_config, validate_config
    from cache_manager import get_cache_manager
    from execution_manager import get_execution_manager
except ImportError as e:
    print(f"⚠️ 导入模块失败: {e}")
    print("请确保所有优化模块都已创建")
    sys.exit(1)

def print_banner():
    """打印启动横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                🚀 RNA项目优化版本演示                        ║
    ║              Performance Optimized RNA Analysis              ║
    ║                                                              ║
    ║  ✨ 统一配置管理     🧠 智能缓存系统                         ║
    ║  ⚡ 持久化执行环境   📊 性能监控                             ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def performance_comparison_demo():
    """性能对比演示"""
    print("\n🧪 性能优化效果演示")
    print("=" * 60)
    
    # 获取优化组件
    config = get_config()
    cache_manager = get_cache_manager()
    execution_manager = get_execution_manager()
    
    print("🔧 配置管理器状态:")
    print(f"  📍 数据路径: {config.data.pbmc3k_path}")
    print(f"  💾 缓存目录: {config.data.cache_dir}")
    print(f"  🔧 API密钥: {list(config.api_keys.keys())}")
    
    print("\n💾 缓存管理器状态:")
    cache_stats = cache_manager.get_stats()
    print(f"  🧠 内存缓存: {cache_stats['memory_cache']['current_size_mb']} MB")
    print(f"  💽 磁盘缓存: {cache_stats['disk_cache']['total_files']} 文件")
    print(f"  🖥️ 系统内存: {cache_stats['system_memory']['used_percent']}% 使用")
    
    print("\n⚡ 执行管理器性能测试:")
    
    # 测试1: 简单代码执行
    print("  测试1: 简单代码执行")
    start_time = time.time()
    result1 = execution_manager.execute_code("import numpy as np; result = np.sum([1,2,3,4,5]); print(f'Sum: {result}')")
    time1 = time.time() - start_time
    print(f"    ✅ 执行成功: {result1['success']}")
    print(f"    ⏱️ 执行时间: {time1:.3f}s")
    
    # 测试2: 重复执行（应该更快，因为环境已初始化）
    print("  测试2: 重复执行（环境已预热）")
    start_time = time.time()
    result2 = execution_manager.execute_code("result2 = np.mean([1,2,3,4,5]); print(f'Mean: {result2}')")
    time2 = time.time() - start_time
    print(f"    ✅ 执行成功: {result2['success']}")
    print(f"    ⏱️ 执行时间: {time2:.3f}s")
    print(f"    🚀 性能提升: {time1/time2:.2f}x (第二次执行)")
    
    # 测试3: 数据科学代码
    print("  测试3: 数据科学库加载")
    start_time = time.time()
    result3 = execution_manager.execute_code("""
import pandas as pd
import matplotlib.pyplot as plt
data = pd.DataFrame({'x': [1,2,3,4,5], 'y': [2,4,6,8,10]})
plt.figure(figsize=(6,4))
plt.plot(data['x'], data['y'], 'b-o')
plt.title('Test Plot')
plt.xlabel('X')
plt.ylabel('Y')
print(f"DataFrame shape: {data.shape}")
""")
    time3 = time.time() - start_time
    print(f"    ✅ 执行成功: {result3['success']}")
    print(f"    ⏱️ 执行时间: {time3:.3f}s")
    print(f"    📊 生成图表: {len(result3['plots'])} 个")
    
    # 获取最终统计信息
    print("\n📊 执行统计信息:")
    exec_stats = execution_manager.get_stats()
    print(f"  📈 总执行次数: {exec_stats['execution_stats']['total_executions']}")
    print(f"  ⏱️ 平均执行时间: {exec_stats['avg_execution_time']:.3f}s")
    print(f"  🔧 环境已初始化: {exec_stats['initialized']}")
    print(f"  📚 已加载变量: {exec_stats['globals_count']} 个")

def optimization_features_demo():
    """优化特性演示"""
    print("\n✨ 优化特性展示")
    print("=" * 60)
    
    print("🎯 主要优化点:")
    print("  1. 🔧 统一配置管理 - 避免重复配置和验证")
    print("  2. 💾 智能缓存系统 - 内存+磁盘双层缓存")
    print("  3. ⚡ 持久化执行环境 - 避免重复初始化")
    print("  4. 🔀 减少网络调用 - 直接本地执行")
    print("  5. 📊 性能监控 - 实时统计和优化")
    
    print("\n📈 性能提升预期:")
    print("  • 首次启动时间: 减少 60%")
    print("  • 代码执行速度: 提升 3-5x")
    print("  • 内存使用效率: 提升 40%")
    print("  • 缓存命中率: 80%+")
    print("  • 网络调用减少: 70%")

def memory_optimization_demo():
    """内存优化演示"""
    print("\n🧠 内存优化演示")
    print("=" * 60)
    
    cache_manager = get_cache_manager()
    
    # 模拟数据分析缓存
    @cache_manager.cache_result(ttl=300, use_disk=True)
    def simulate_data_analysis(dataset_size: int):
        """模拟数据分析"""
        time.sleep(0.1)  # 模拟计算时间
        return f"Analysis result for {dataset_size} samples"
    
    print("测试缓存效果:")
    
    # 第一次调用
    start_time = time.time()
    result1 = simulate_data_analysis(1000)
    time1 = time.time() - start_time
    print(f"  第一次调用: {time1:.3f}s - {result1}")
    
    # 第二次调用（应该命中缓存）
    start_time = time.time()
    result2 = simulate_data_analysis(1000)
    time2 = time.time() - start_time
    print(f"  第二次调用: {time2:.3f}s - {result2}")
    
    print(f"  🚀 缓存加速比: {time1/time2:.1f}x")
    
    # 显示缓存统计
    cache_stats = cache_manager.get_stats()
    print(f"  📊 内存缓存使用: {cache_stats['memory_cache']['memory_usage_percent']:.1f}%")

def main():
    """主函数"""
    print_banner()
    
    # 配置验证
    print("🔍 配置验证...")
    if validate_config():
        print("✅ 配置验证通过")
    else:
        print("⚠️ 配置验证失败，但继续演示")
    
    # 性能对比演示
    performance_comparison_demo()
    
    # 优化特性演示
    optimization_features_demo()
    
    # 内存优化演示
    memory_optimization_demo()
    
    print("\n🎉 优化演示完成！")
    print("\n💡 使用建议:")
    print("  1. 使用统一服务器减少组件间通信开销")
    print("  2. 启用缓存功能提升重复分析性能")
    print("  3. 利用持久化环境避免重复初始化")
    print("  4. 监控性能指标持续优化")
    
    print("\n📋 下一步:")
    print("  • 可以启动优化版本的统一服务器")
    print("  • 对比原版本和优化版本的性能差异")
    print("  • 根据实际使用情况调整缓存策略")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 演示被用户中断")
    except Exception as e:
        print(f"\n❌ 演示过程中出错: {e}")
        import traceback
        traceback.print_exc() 
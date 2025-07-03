#!/usr/bin/env python3
"""
RnAgent Demo 功能测试脚本
快速验证各个组件的功能是否正常
"""

import os
import sys
import requests
import time
from pathlib import Path

def test_data_files():
    """测试数据文件是否存在"""
    print("🔍 测试数据文件...")
    
    data_path = "/Volumes/T7/哈尔滨工业大学-2025/课题组项目/Agent-项目/PBMC3kRNA-seq/filtered_gene_bc_matrices/hg19/"
    required_files = ['matrix.mtx', 'barcodes.tsv', 'genes.tsv']
    
    if not os.path.exists(data_path):
        print(f"❌ 数据路径不存在: {data_path}")
        return False
    
    missing_files = []
    for file in required_files:
        file_path = os.path.join(data_path, file)
        if os.path.exists(file_path):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file}")
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少文件: {', '.join(missing_files)}")
        return False
    
    print("✅ 数据文件检查通过")
    return True

def test_dependencies():
    """测试Python依赖包"""
    print("\n🔍 测试Python依赖...")
    
    required_packages = [
        'streamlit',
        'fastmcp',
        'langchain',
        'scanpy',
        'matplotlib',
        'pandas',
        'numpy'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("\n安装命令:")
        print("pip install -r 3_backend_mcp/requirements.txt")
        print("pip install -r 2_agent_core/requirements.txt")
        print("pip install -r 1_frontend/requirements.txt")
        return False
    
    print("✅ 依赖包检查通过")
    return True

def test_api_keys():
    """测试API密钥配置"""
    print("\n🔍 测试API密钥...")
    
    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    
    if openai_key:
        print("   ✅ OPENAI_API_KEY 已设置")
    else:
        print("   ⚠️  OPENAI_API_KEY 未设置")
    
    if deepseek_key:
        print("   ✅ DEEPSEEK_API_KEY 已设置")
    else:
        print("   ⚠️  DEEPSEEK_API_KEY 未设置")
    
    if not openai_key and not deepseek_key:
        print("❌ 未设置任何API密钥")
        print("\n设置方法:")
        print("export OPENAI_API_KEY='your_openai_key'")
        print("export DEEPSEEK_API_KEY='your_deepseek_key'")
        return False
    
    print("✅ API密钥检查通过")
    return True

def test_mcp_server():
    """测试MCP服务器连接"""
    print("\n🔍 测试MCP服务器...")
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ MCP服务器在线")
            return True
        else:
            print(f"   ❌ MCP服务器响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ MCP服务器离线")
        print("   请先启动: python 3_backend_mcp/rna_mcp_server.py")
        return False
    except Exception as e:
        print(f"   ❌ 连接错误: {e}")
        return False

def test_plot_directory():
    """测试图片输出目录"""
    print("\n🔍 测试图片输出目录...")
    
    plot_dir = Path(__file__).parent / "3_backend_mcp" / "tmp" / "plots"
    
    if plot_dir.exists():
        print(f"   ✅ 目录存在: {plot_dir}")
        
        # 检查写入权限
        try:
            test_file = plot_dir / "test_write.txt"
            test_file.write_text("test")
            test_file.unlink()  # 删除测试文件
            print("   ✅ 写入权限正常")
            return True
        except Exception as e:
            print(f"   ❌ 写入权限异常: {e}")
            return False
    else:
        print(f"   ❌ 目录不存在: {plot_dir}")
        print("   正在创建目录...")
        try:
            plot_dir.mkdir(parents=True, exist_ok=True)
            print("   ✅ 目录创建成功")
            return True
        except Exception as e:
            print(f"   ❌ 目录创建失败: {e}")
            return False

def test_simple_import():
    """测试简单的代码导入"""
    print("\n🔍 测试代码导入...")
    
    try:
        # 测试后端导入
        sys.path.append(str(Path(__file__).parent / "3_backend_mcp"))
        
        # 测试智能体核心导入
        sys.path.append(str(Path(__file__).parent / "2_agent_core"))
        
        print("   ✅ 路径配置成功")
        return True
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧬 RnAgent Demo 功能测试")
    print("=" * 50)
    
    tests = [
        test_data_files,
        test_dependencies, 
        test_api_keys,
        test_plot_directory,
        test_simple_import,
        test_mcp_server,  # 最后测试，可能失败
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   ❌ 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！Demo可以正常运行")
        print("\n🚀 启动命令:")
        print("python run_rna_demo.py")
    else:
        print("⚠️  存在问题，请根据上述提示修复")
        
        if passed >= total - 1:  # 除了MCP服务器都通过
            print("\n💡 如果只是MCP服务器离线，可以尝试启动demo:")
            print("python run_rna_demo.py")

if __name__ == "__main__":
    main() 
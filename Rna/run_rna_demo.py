#!/usr/bin/env python3
"""
RnAgent Demo 启动脚本
自动启动后端MCP服务器和前端Streamlit应用
"""

import threading
import signal
import os
import time
import subprocess
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# 导入配置管理器
try:
    # 确保能正确导入项目根目录的模块
    from config import get_config
except ImportError:
    print("❌ 无法导入config模块，请确保在正确的目录运行脚本")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"项目根目录: {project_root}")
    print(f"Python路径: {sys.path}")
    sys.exit(1)

# 导入日志清理模块
try:
    from log_management import cleanup_logs_on_startup
except ImportError:
    print("⚠️ 日志管理模块未找到，跳过日志清理")
    cleanup_logs_on_startup = None

# 获取配置
config = get_config()


def clean_generated_plots():
    """清理之前生成的图片文件"""
    print("\n🧹 启动前清理图片文件...")
    
    # 图片存储路径
    plots_dir = Path(__file__).parent / "3_backend_mcp" / "tmp" / "plots"
    
    if plots_dir.exists():
        # 删除所有PNG文件
        png_files = list(plots_dir.glob("*.png"))
        if png_files:
            deleted_count = 0
            for png_file in png_files:
                try:
                    png_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️ 删除文件失败 {png_file.name}: {e}")
            
            if deleted_count > 0:
                print(f"✅ 已清理 {deleted_count} 个历史图片文件")
            else:
                print("⚠️ 清理图片文件时出错")
        else:
            print("✅ 无需清理，图片目录干净")
    else:
        print("✅ 图片目录不存在，无需清理")


def print_banner():
    """打印启动横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                     🧬 RnAgent Demo v2.1                    ║
    ║              单细胞RNA分析智能体演示程序                       ║
    ║                                                              ║
    ║  基于MCP架构 | 支持DEEPSEEK/OpenAI | 自然语言交互            ║
    ║  🆕 新增功能：对话记忆 | 历史管理 | 智能摘要                  ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 9):
        print("❌ 错误: 需要Python 3.9或更高版本")
        sys.exit(1)
    print(f"✅ Python版本: {sys.version.split()[0]}")


def check_api_keys():
    """检查API密钥配置"""
    print("\n🔑 检查API密钥配置...")

    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    if openai_key:
        print("✅ OpenAI API密钥: 已设置")
    else:
        print("⚠️  OpenAI API密钥: 未设置")

    if deepseek_key:
        print("✅ DeepSeek API密钥: 已设置")
    else:
        print("⚠️  DeepSeek API密钥: 未设置")

    if not openai_key and not deepseek_key:
        print("\n⚠️  警告: 未设置任何API密钥")
        print("请设置以下环境变量之一:")
        print("export OPENAI_API_KEY='your_key_here'")
        print("export DEEPSEEK_API_KEY='your_key_here'")

        response = input("\n是否继续启动demo? (y/N): ")
        if response.lower() != 'y':
            return False

    return True


def check_data_path():
    """检查数据路径"""
    print("\n📁 检查数据路径...")

    # 使用相对路径，从当前文件位置向上一级到项目根目录
    current_dir = Path(__file__).parent  # Rna目录
    project_root = current_dir.parent    # RnAgent-Project目录
    data_path = project_root / "PBMC3kRNA-seq" / "filtered_gene_bc_matrices" / "hg19"
    data_path = str(data_path)

    if os.path.exists(data_path):
        files = ['matrix.mtx', 'barcodes.tsv', 'genes.tsv']
        missing_files = [f for f in files if not os.path.exists(
            os.path.join(data_path, f))]

        if not missing_files:
            print("✅ PBMC3K数据集: 完整")
            print(f"   - matrix.mtx: ✓")
            print(f"   - barcodes.tsv: ✓")
            print(f"   - genes.tsv: ✓")
            return True
        else:
            print(f"❌ 缺少文件: {', '.join(missing_files)}")
            existing_files = [f for f in files if os.path.exists(
                os.path.join(data_path, f))]
            if existing_files:
                print(f"   已存在: {', '.join(existing_files)}")
    else:
        print("❌ PBMC3K数据路径不存在")

    print(f"数据路径: {data_path}")
    print("请确保数据文件存在或修改后端代码中的路径")

    response = input("\n是否继续启动demo? (y/N): ")
    return response.lower() == 'y'


def start_backend_server():
    """启动后端MCP服务器"""
    print("\n🚀 启动后端MCP服务器...")

    backend_dir = Path(__file__).parent / "3_backend_mcp"
    server_script = backend_dir / "rna_mcp_server.py"

    if not server_script.exists():
        print(f"❌ 未找到服务器脚本: {server_script}")
        return None

    try:
        process = subprocess.Popen([
            sys.executable, str(server_script)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(backend_dir))

        # 等待服务器启动
        time.sleep(3)

        if process.poll() is None:
            print("✅ 后端MCP服务器已启动 (端口 8000)")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ 后端服务器启动失败:")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return None

    except Exception as e:
        print(f"❌ 启动后端服务器时出错: {e}")
        return None


def start_frontend_app():
    """启动前端Streamlit应用"""
    print("\n🌐 启动前端Streamlit应用...")

    frontend_dir = Path(__file__).parent / "1_frontend"
    app_script = frontend_dir / "rna_streamlit_app.py"

    if not app_script.exists():
        print(f"❌ 未找到应用脚本: {app_script}")
        return None

    try:
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", str(app_script),
            "--server.port", str(config.frontend_port),
            "--server.address", config.host,
            "--server.headless", "true"
        ], cwd=str(frontend_dir))

        time.sleep(2)

        if process.poll() is None:
            print("✅ 前端应用已启动 (端口 8501)")
            return process
        else:
            print("❌ 前端应用启动失败")
            return None

    except Exception as e:
        print(f"❌ 启动前端应用时出错: {e}")
        return None


def start_agent_core():
    """启动智能体核心HTTP服务器"""
    print("\n🤖 启动Agent Core服务...")
    agent_dir = Path(__file__).parent / "2_agent_core"
    server_script = agent_dir / "agent_server.py"

    if not server_script.exists():
        print(f"❌ 未找到Agent Core脚本: {server_script}")
        return None

    try:
        # 使用 DEVNULL 避免阻塞
        process = subprocess.Popen([
            sys.executable, str(server_script)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, cwd=str(agent_dir))

        # 等待服务器启动
        time.sleep(3)

        if process.poll() is None:
            print("✅ Agent Core已启动 (端口 8002)")
            return process
        else:
            print("❌ Agent Core启动失败")
            return None
    except Exception as e:
        print(f"❌ 启动Agent Core时出错: {e}")
        return None


def signal_handler(signum, frame):
    """信号处理器"""
    print("\n\n🛑 接收到停止信号，正在关闭服务...")
    cleanup_processes()
    sys.exit(0)


backend_process = None
frontend_process = None
agent_process = None


def cleanup_processes():
    """清理进程"""
    global backend_process, frontend_process, agent_process

    if backend_process:
        print("停止后端服务器...")
        backend_process.terminate()
        backend_process.wait()

    if frontend_process:
        print("停止前端应用...")
        frontend_process.terminate()
        frontend_process.wait()

    if agent_process:
        print("停止Agent Core...")
        agent_process.terminate()
        agent_process.wait()


def main():
    """主函数"""
    global backend_process, frontend_process, agent_process

    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print_banner()

    # 启动时清理日志
    if cleanup_logs_on_startup:
        print("\n🧹 启动前清理日志文件...")
        try:
            current_dir = Path(__file__).parent
            stats = cleanup_logs_on_startup(base_dir=str(
                current_dir), action="delete", dry_run=False)
            if stats["processed"] > 0:
                print(
                    f"✅ 清理了 {stats['processed']} 个日志文件，释放 {stats['total_size_freed']/1024:.1f} KB")
            else:
                print("✅ 无需清理，日志目录干净")
        except Exception as e:
            print(f"⚠️ 日志清理出错: {e}")

    # 清理历史生成的图片
    clean_generated_plots()

    print("\n📋 系统检查...")

    # 检查Python版本
    check_python_version()

    # 检查API密钥
    if not check_api_keys():
        sys.exit(1)

    # 检查数据路径
    if not check_data_path():
        sys.exit(1)

    print("\n🎯 启动服务...")

    # 启动后端服务器
    backend_process = start_backend_server()
    if not backend_process:
        print("❌ 无法启动后端服务器，退出")
        sys.exit(1)

    # 启动Agent Core服务器
    agent_process = start_agent_core()
    if not agent_process:
        print("❌ 无法启动Agent Core服务器，正在清理...")
        cleanup_processes()
        sys.exit(1)

    # 启动前端应用
    frontend_process = start_frontend_app()
    if not frontend_process:
        print("❌ 无法启动前端应用，正在清理...")
        cleanup_processes()
        sys.exit(1)

    print("\n🎉 RnAgent Demo启动成功!")
    print("=" * 30)
    print(f"📱 前端地址: http://{config.host}:{config.frontend_port}")
    print(f"🔧 后端服务: http://{config.host}:{config.mcp_port}")
    print(f"🤖 Agent Core: http://{config.host}:{config.agent_port}")
    print("=" * 30)
    print("\n💡 使用提示:")
    if config.host == "0.0.0.0":
        print("1. 在浏览器中访问 http://你的服务器IP:8501")
    else:
        print(f"1. 在浏览器中访问 http://{config.host}:{config.frontend_port}")
    print("2. 选择您偏好的AI模型 (OpenAI/DeepSeek)")
    print("3. 开始与RnAgent对话分析PBMC3K数据")
    print("4. 💭 享受对话记忆功能 - 我会记住您的对话历史")
    print("5. 按 Ctrl+C 停止所有服务")
    print("\n🆕 新功能:")
    print("• 🧠 对话记忆：智能体会记住上下文")
    print("• 📚 历史管理：查看和管理过往对话")
    print("• 🗂️ 智能摘要：自动生成对话摘要")
    print("• 🔄 多轮对话：更自然的交互体验")
    print("\n示例问题:")
    print("• '请加载PBMC3K数据并进行完整分析'")
    print("• '显示质量控制指标'")
    print("• '基于前面的分析结果，进行进一步的聚类'")
    print("• '总结一下我们的分析结果'")

    try:
        # 保持运行状态
        while True:
            time.sleep(1)

            # 检查进程状态
            if backend_process.poll() is not None:
                print("❌ 后端服务器意外停止")
                break

            if frontend_process.poll() is not None:
                print("❌ 前端应用意外停止")
                break

    except KeyboardInterrupt:
        pass
    finally:
        cleanup_processes()
        print("\n✅ 所有服务已停止，再见!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
RNA项目增强日志系统测试脚本
演示如何查看完整的LLM调用和Agent执行日志
"""

import requests
import json
import time
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 服务地址
AGENT_CORE_URL = "http://localhost:8002"
MCP_SERVER_URL = "http://localhost:8000"

def test_health_checks():
    """测试服务健康检查"""
    logger.info("🏥 [健康检查] 开始检查各服务状态")
    
    # 检查Agent Core
    try:
        response = requests.get(f"{AGENT_CORE_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ [Agent Core] 服务正常")
            data = response.json()
            logger.info(f"   API密钥状态: {data.get('api_keys', {})}")
        else:
            logger.error(f"❌ [Agent Core] 服务异常: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ [Agent Core] 连接失败: {e}")
    
    # MCP服务器健康检查通过Agent Core
    logger.info("🔍 [健康检查] 完成")

def test_simple_chat():
    """测试简单的聊天交互"""
    logger.info("💬 [聊天测试] 开始测试聊天功能")
    
    test_message = "你好，请介绍一下你的功能"
    
    try:
        logger.info(f"📤 [发送消息] {test_message}")
        
        response = requests.post(
            f"{AGENT_CORE_URL}/chat",
            json={"message": test_message},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✅ [聊天成功] 收到响应")
            logger.info(f"📥 [响应内容] {data.get('final_response', '')[:200]}...")
            logger.info(f"💬 [消息数量] {len(data.get('messages', []))}")
        else:
            logger.error(f"❌ [聊天失败] HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ [聊天异常] {e}")

def test_data_analysis():
    """测试数据分析功能"""
    logger.info("🧬 [分析测试] 开始测试RNA数据分析")
    
    test_message = "请加载PBMC3K数据并显示基本信息"
    
    try:
        logger.info(f"📤 [发送消息] {test_message}")
        start_time = time.time()
        
        response = requests.post(
            f"{AGENT_CORE_URL}/chat",
            json={"message": test_message},
            timeout=120  # 数据分析可能需要更长时间
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ [分析成功] 耗时: {elapsed_time:.2f}s")
            logger.info(f"📥 [响应内容] {data.get('final_response', '')[:300]}...")
            
            # 检查是否有工具调用
            messages = data.get('messages', [])
            tool_calls = 0
            for msg in messages:
                if hasattr(msg, 'tool_calls') or 'tool' in str(msg).lower():
                    tool_calls += 1
            
            logger.info(f"🔧 [工具调用] 检测到 {tool_calls} 次工具相关操作")
            
        else:
            logger.error(f"❌ [分析失败] HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ [分析异常] {e}")

def main():
    """主函数"""
    logger.info("🚀 开始RNA项目增强日志系统测试")
    logger.info("=" * 80)
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║                  🧬 RNA项目日志系统测试                       ║
║                                                              ║
║  本脚本将测试RNA项目的各个组件，演示增强的日志输出功能        ║
║                                                              ║
║  请确保以下服务已启动：                                       ║
║  • Agent Core服务器 (端口 8002)                              ║
║  • MCP后端服务器 (端口 8000)                                ║
║                                                              ║
║  运行后请查看各个服务的日志文件：                              ║
║  • agent_server.log                                         ║
║  • rna_agent_graph.log                                      ║
║  • rna_mcp_server.log                                       ║
║  • rna_streamlit_app.log                                    ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 等待用户确认
    input("按回车键开始测试...")
    
    # 1. 健康检查
    test_health_checks()
    time.sleep(2)
    
    # 2. 简单聊天测试
    test_simple_chat()
    time.sleep(3)
    
    # 3. 数据分析测试
    test_data_analysis()
    
    logger.info("=" * 80)
    logger.info("🏁 测试完成！")
    logger.info("💡 请查看以下日志文件以了解详细的执行过程：")
    logger.info("   📄 agent_server.log - Agent核心服务器日志")
    logger.info("   📄 rna_agent_graph.log - LLM调用和工具执行日志")
    logger.info("   📄 rna_mcp_server.log - MCP后端工具执行日志")
    logger.info("   📄 rna_streamlit_app.log - 前端应用日志")
    logger.info("=" * 80)

if __name__ == "__main__":
    main() 
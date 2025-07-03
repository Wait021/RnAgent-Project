#!/usr/bin/env python3
"""
测试MCP连接的简单脚本
用于验证前端和后端的连接是否正常
"""

import asyncio
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), "1_frontend"))

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

MCP_SERVER_URL = "http://localhost:8000/sse"

def parse_mcp_result(result):
    """解析MCP工具返回的结果"""
    try:
        # 检查是否有content字段
        if hasattr(result, 'content') and result.content:
            # 获取第一个TextContent的文本内容
            text_content = result.content[0].text
            # 尝试解析JSON
            try:
                parsed = json.loads(text_content)
                return parsed
            except json.JSONDecodeError:
                # 如果不是JSON，直接返回文本
                return {"content": text_content}
        else:
            return {"error": "No content in result"}
    except Exception as e:
        return {"error": f"解析结果失败: {e}"}

async def test_mcp_connection():
    """测试MCP连接"""
    print("🔍 测试MCP服务器连接...")
    
    try:
        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                print("✅ 成功连接到MCP服务器")
                
                # 初始化会话
                await session.initialize()
                print("✅ 会话初始化成功")
                
                # 测试健康检查
                print("\n🏥 测试健康检查...")
                result = await session.call_tool("health_check", {})
                parsed_result = parse_mcp_result(result)
                
                if "error" not in parsed_result:
                    print("✅ 健康检查正常")
                    if "status" in parsed_result:
                        print(f"   状态: {parsed_result['status']}")
                        print(f"   消息: {parsed_result.get('message', 'N/A')}")
                else:
                    print(f"❌ 健康检查异常: {parsed_result['error']}")
                
                # 测试加载数据工具
                print("\n📊 测试数据加载工具...")
                result = await session.call_tool("load_pbmc3k_data", {})
                parsed_result = parse_mcp_result(result)
                
                if "content" in parsed_result and parsed_result["content"]:
                    print("✅ 数据加载工具正常")
                    code_length = len(parsed_result["content"])
                    print(f"   返回代码长度: {code_length} 字符")
                    # 检查是否包含关键的分析代码
                    if "import scanpy" in parsed_result["content"]:
                        print("   ✓ 包含scanpy导入")
                    if "sc.read_10x_mtx" in parsed_result["content"]:
                        print("   ✓ 包含数据读取代码")
                else:
                    print(f"❌ 数据加载工具异常: {parsed_result}")
                
                # 测试Python执行工具
                print("\n🐍 测试Python执行工具...")
                test_code = "print('Hello from Python REPL!')\nimport numpy as np\nprint(f'NumPy版本: {np.__version__}')"
                result = await session.call_tool("python_repl_tool", {"query": test_code})
                parsed_result = parse_mcp_result(result)
                
                if "content" in parsed_result and parsed_result["content"]:
                    print("✅ Python执行工具正常")
                    print(f"   执行结果: {parsed_result['content']}")
                    # 检查是否有图片生成
                    if "artifact" in parsed_result and parsed_result["artifact"]:
                        print(f"   ✓ 生成了 {len(parsed_result['artifact'])} 个图片")
                else:
                    print(f"❌ Python执行工具异常: {parsed_result}")
                
                print("\n✅ 所有测试通过！MCP连接正常工作")
                
    except Exception as e:
        print(f"❌ MCP连接测试失败: {e}")
        print("请确保后端服务器正在运行: python Rna/3_backend_mcp/rna_mcp_server.py")

def main():
    """主函数"""
    print("=" * 60)
    print("           RNA Agent MCP连接测试")
    print("=" * 60)
    
    try:
        asyncio.run(test_mcp_connection())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试过程中出现错误: {e}")

if __name__ == "__main__":
    main() 
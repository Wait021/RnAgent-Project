#!/usr/bin/env python3
"""
RNA分析智能体核心 - LangGraph实现
负责自然语言处理、工具调用和对话管理
"""

import logging
import os
import asyncio
import json
import time
from typing import Dict, Any, List, Annotated, TypedDict, Literal
from datetime import datetime

# LangChain和LangGraph相关导入
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from pydantic import SecretStr

# MCP客户端导入
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# 设置详细的日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('rna_agent_graph.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# MCP服务器配置
MCP_SERVER_URL = "http://localhost:8000/sse"


class AgentState(TypedDict):
    """智能体状态定义"""
    messages: Annotated[List[BaseMessage], add_messages]


class RNAAnalysisAgent:
    """RNA分析智能体核心类"""

    def __init__(self):
        logger.info("🧬 [Agent初始化] 开始初始化RNA分析智能体")
        self.graph = self._create_graph()
        logger.info("✅ [Agent初始化] RNA分析智能体初始化完成")

    def _create_graph(self):
        """创建LangGraph工作流"""
        logger.info("🔧 [图构建] 开始创建LangGraph工作流")

        # 创建状态图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("llm", self._call_model)
        workflow.add_node("tools", ToolNode(self._get_tools()))

        # 设置边
        workflow.add_edge(START, "llm")
        workflow.add_conditional_edges(
            "llm",
            self._should_continue,
            {"continue": "tools", "end": "__end__"}
        )
        workflow.add_edge("tools", "llm")

        logger.info("✅ [图构建] LangGraph工作流创建完成")
        return workflow.compile()

    def _get_tools(self):
        """获取可用工具列表"""
        tools = [
            load_pbmc3k_data_tool,
            quality_control_analysis_tool,
            preprocessing_analysis_tool,
            dimensionality_reduction_analysis_tool,
            clustering_analysis_tool,
            marker_genes_analysis_tool,
            generate_analysis_report_tool,
            python_repl_tool
        ]
        logger.info(
            f"🛠️ [工具列表] 加载了 {len(tools)} 个工具: {[tool.name for tool in tools]}")
        return tools

    def _call_model(self, state: AgentState):
        """调用语言模型"""
        start_time = time.time()
        messages = state["messages"]

        logger.info("🧠 [LLM调用] 开始调用语言模型")
        logger.info(f"📨 [输入消息] 消息数量: {len(messages)}")

        # 记录输入消息详情
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            msg_content = getattr(msg, 'content', '')[:100] if hasattr(
                msg, 'content') else str(msg)[:100]
            logger.info(f"   [{i+1}] {msg_type}: {msg_content}...")

        try:
            # 获取LLM客户端
            llm = self._get_llm_client()

            # 绑定工具
            llm_with_tools = llm.bind_tools(self._get_tools())

            logger.info("🚀 [LLM调用] 发送请求到语言模型...")

            # 调用模型
            response = llm_with_tools.invoke(messages)

            call_time = time.time() - start_time

            logger.info(f"✅ [LLM响应] 模型调用完成，耗时: {call_time:.2f}s")
            logger.info(f"📝 [响应内容] {response.content[:200]}...")

            # 检查是否有工具调用 - 修复新版LangChain兼容性
            if isinstance(response, AIMessage) and hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"🔧 [工具调用] 模型请求调用 {len(response.tool_calls)} 个工具:")
                for i, tool_call in enumerate(response.tool_calls):
                    logger.info(f"   [{i+1}] 工具: {tool_call['name']}")
                    logger.info(f"       参数: {tool_call.get('args', {})}")

            return {"messages": [response]}

        except Exception as e:
            call_time = time.time() - start_time
            logger.error(f"❌ [LLM错误] 模型调用失败，耗时: {call_time:.2f}s")
            logger.error(f"🔥 [错误详情] {str(e)}")
            raise e

    def _should_continue(self, state: AgentState):
        """判断是否继续执行工具"""
        last_message = state["messages"][-1]

        # 修复新版LangChain兼容性
        if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info("🔄 [流程判断] 需要执行工具，继续到工具节点")
            return "continue"
        else:
            logger.info("🏁 [流程判断] 无需执行工具，流程结束")
            return "end"

    def _get_llm_client(self):
        """获取LLM客户端"""
        # 优先使用DeepSeek API
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        if deepseek_key:
            logger.info("🔑 [LLM配置] 使用DeepSeek API")
            return ChatOpenAI(
                model="deepseek-chat",
                temperature=0,
                api_key=SecretStr(deepseek_key),  # 修复类型安全问题
                base_url="https://www.chataiapi.com/v1"
            )
        # 备用OpenAI API
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            logger.info("🔑 [LLM配置] 使用OpenAI API")
            return ChatOpenAI(
                model="gpt-4o",
                temperature=0,
                api_key=SecretStr(openai_key)  # 修复类型安全问题
            )
        else:
            logger.error("❌ [LLM配置] 未找到API密钥")
            raise ValueError(
                "No API key found. Please set DEEPSEEK_API_KEY or OPENAI_API_KEY.")

    def process_message(self, message: str) -> Dict[str, Any]:
        """处理用户消息"""
        start_time = time.time()

        try:
            logger.info("🎯 [消息处理] 开始处理用户消息")
            logger.info(f"📝 [输入消息] {message}")

            # 创建输入状态
            initial_state = {
                "messages": [HumanMessage(content=message)]
            }

            logger.info("🚀 [图执行] 开始执行LangGraph工作流")

            # 运行图
            result = self.graph.invoke(initial_state)

            process_time = time.time() - start_time

            logger.info(f"✅ [图执行] 工作流执行完成，耗时: {process_time:.2f}s")
            logger.info(f"💬 [输出消息] 生成了 {len(result['messages'])} 条消息")

            # 记录最终响应
            final_response = result["messages"][-1].content if result["messages"] else ""
            logger.info(f"📤 [最终响应] {final_response[:200]}...")

            return {
                "success": True,
                "messages": result["messages"],
                "final_response": final_response
            }

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"❌ [消息处理] 处理失败，耗时: {process_time:.2f}s")
            logger.error(f"🔥 [错误详情] {str(e)}")

            import traceback
            logger.error(f"📋 [错误栈] {traceback.format_exc()}")

            return {
                "success": False,
                "error": str(e),
                "messages": []
            }

# MCP工具调用函数


async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """异步调用MCP工具"""
    start_time = time.time()

    try:
        logger.info(f"🔌 [MCP连接] 连接到MCP服务器: {MCP_SERVER_URL}")
        logger.info(f"🛠️ [工具调用] 调用工具: {tool_name}")
        logger.info(f"📋 [调用参数] {arguments}")

        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

                call_time = time.time() - start_time

                # 解析结果 - 修复MCP内容解析兼容性
                if hasattr(result, 'content') and result.content:
                    # 处理不同类型的内容
                    content_item = result.content[0]
                    try:
                        # 安全地获取文本内容
                        if hasattr(content_item, 'text'):
                            text_content = getattr(content_item, 'text', '')
                        elif hasattr(content_item, 'content'):
                            text_content = getattr(content_item, 'content', '')
                        else:
                            # 如果没有预期属性，尝试直接转换为字符串
                            text_content = str(content_item)
                    except Exception as content_error:
                        logger.warning(f"⚠️ [内容提取] 内容提取失败: {content_error}")
                        text_content = str(content_item)

                    try:
                        parsed = json.loads(text_content)
                        logger.info(
                            f"✅ [工具响应] {tool_name} 调用成功，耗时: {call_time:.2f}s")
                        logger.info(f"📋 [响应内容] {str(parsed)[:200]}...")
                        return parsed
                    except json.JSONDecodeError:
                        logger.info(
                            f"✅ [工具响应] {tool_name} 调用成功，耗时: {call_time:.2f}s (文本响应)")
                        return {"content": text_content}
                else:
                    logger.warning(f"⚠️ [工具响应] {tool_name} 返回空内容")
                    return {"error": "No content in result"}

    except Exception as e:
        call_time = time.time() - start_time
        logger.error(f"❌ [MCP错误] {tool_name} 调用失败，耗时: {call_time:.2f}s")
        logger.error(f"🔥 [错误详情] {str(e)}")
        return {"error": str(e)}


def call_mcp_tool_sync(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """同步调用MCP工具"""
    return asyncio.run(call_mcp_tool(tool_name, arguments))

# 定义工具 - 这些工具会被LangGraph自动调用


@tool
def load_pbmc3k_data_tool() -> str:
    """加载PBMC3K数据集的工具"""
    logger.info("🧬 [工具执行] 开始执行加载PBMC3K数据工具")
    result = call_mcp_tool_sync("load_pbmc3k_data", {})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"加载数据工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


@tool
def quality_control_analysis_tool() -> str:
    """质量控制分析工具"""
    logger.info("📊 [工具执行] 开始执行质量控制分析工具")
    result = call_mcp_tool_sync("quality_control_analysis", {})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"质量控制分析工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


@tool
def preprocessing_analysis_tool() -> str:
    """数据预处理分析工具"""
    logger.info("🔄 [工具执行] 开始执行数据预处理分析工具")
    result = call_mcp_tool_sync("preprocessing_analysis", {})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"数据预处理分析工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


@tool
def dimensionality_reduction_analysis_tool() -> str:
    """降维分析工具"""
    logger.info("📉 [工具执行] 开始执行降维分析工具")
    result = call_mcp_tool_sync("dimensionality_reduction_analysis", {})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"降维分析工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


@tool
def clustering_analysis_tool() -> str:
    """聚类分析工具"""
    logger.info("🎯 [工具执行] 开始执行聚类分析工具")
    result = call_mcp_tool_sync("clustering_analysis", {})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"聚类分析工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


@tool
def marker_genes_analysis_tool() -> str:
    """标记基因分析工具"""
    logger.info("🧬 [工具执行] 开始执行标记基因分析工具")
    result = call_mcp_tool_sync("marker_genes_analysis", {})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"标记基因分析工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


@tool
def generate_analysis_report_tool() -> str:
    """生成分析报告工具"""
    logger.info("📋 [工具执行] 开始执行生成分析报告工具")
    result = call_mcp_tool_sync("generate_analysis_report", {})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"生成分析报告工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


@tool
def python_repl_tool(query: str) -> str:
    """Python代码执行工具"""
    logger.info("🐍 [工具执行] 开始执行Python代码工具")
    logger.info(f"💻 [代码输入] {query[:100]}...")

    result = call_mcp_tool_sync("python_repl_tool", {"query": query})

    if "content" in result:
        # 检查是否有图片生成
        if "artifact" in result and result["artifact"]:
            logger.info(f"🖼️ [图片生成] 生成了 {len(result['artifact'])} 个图片文件")
            # 在返回的内容中添加图片信息标记
            content = result["content"] + \
                f"\n[ARTIFACTS]{json.dumps(result['artifact'])}[/ARTIFACTS]"
            return content
        return result["content"]
    else:
        error_msg = f"Python代码执行工具调用失败: {result.get('error', 'Unknown error')}"
        logger.error(f"❌ [工具错误] {error_msg}")
        return error_msg


# 创建全局智能体实例
logger.info("🏗️ [系统初始化] 创建全局RNA智能体实例")
rna_agent = RNAAnalysisAgent()


def process_user_message(message: str) -> Dict[str, Any]:
    """处理用户消息的主入口函数"""
    logger.info(f"📨 [入口函数] 收到用户消息: {message}")
    result = rna_agent.process_message(message)
    logger.info(f"📤 [入口函数] 返回处理结果: success={result['success']}")
    return result


if __name__ == "__main__":
    # 测试代码
    print("🧬 RNA分析智能体核心启动")

    # 测试消息处理
    test_message = "请加载PBMC3K数据"
    result = process_user_message(test_message)

    if result["success"]:
        print("✅ 智能体处理成功")
        print(f"响应: {result['final_response']}")
    else:
        print(f"❌ 处理失败: {result['error']}")

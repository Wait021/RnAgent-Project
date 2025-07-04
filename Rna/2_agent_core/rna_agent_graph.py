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
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from pydantic import SecretStr

# MCP Adapters 导入
from langchain_mcp_adapters.client import MultiServerMCPClient

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

# 强化的系统提示
SYSTEM_PROMPT = """你是一个专业的RNA单细胞分析智能体。

核心规则：
1. 对于任何需要执行Python代码的请求，你必须使用 mcp_Rnagent-MCP_python_repl_tool 工具
2. 不要直接给出计算结果，而是必须通过工具执行代码来获得结果
3. 如果用户要求计算、绘图、数据分析等，都必须调用相应的工具
4. 即使是简单的数学计算（如99*99），也必须使用 python_repl_tool 执行 print() 语句
5. 对于RNA分析相关的任务，优先使用专门的分析工具（如load_pbmc3k_data、quality_control_analysis等）

可用工具：
- mcp_Rnagent-MCP_python_repl_tool: 执行Python代码
- mcp_Rnagent-MCP_load_pbmc3k_data: 加载PBMC3K数据
- mcp_Rnagent-MCP_quality_control_analysis: 质量控制分析
- mcp_Rnagent-MCP_preprocessing_analysis: 数据预处理
- mcp_Rnagent-MCP_dimensionality_reduction_analysis: 降维分析
- mcp_Rnagent-MCP_clustering_analysis: 聚类分析
- mcp_Rnagent-MCP_marker_genes_analysis: 标记基因分析
- mcp_Rnagent-MCP_generate_analysis_report: 生成分析报告
- mcp_Rnagent-MCP_complete_analysis_pipeline: 完整分析流程

记住：绝不直接回答计算结果，必须通过工具执行！"""


class AgentState(TypedDict):
    """智能体状态定义"""
    messages: Annotated[List[BaseMessage], add_messages]


class RNAAnalysisAgent:
    """RNA分析智能体核心类"""

    def __init__(self):
        logger.info("🧬 [Agent初始化] 开始初始化RNA分析智能体")
        self.mcp_client = None
        self.tools = None
        self.graph = None
        # 异步初始化
        asyncio.run(self._async_init())
        logger.info("✅ [Agent初始化] RNA分析智能体初始化完成")

    async def _async_init(self):
        """异步初始化MCP客户端和工具"""
        logger.info("🔌 [MCP初始化] 开始初始化MCP客户端")
        
        # 创建MCP客户端
        self.mcp_client = MultiServerMCPClient({
            "rna_analysis": {
                "url": MCP_SERVER_URL,
                "transport": "sse",
            }
        })
        
        # 获取工具列表
        logger.info("🛠️ [工具获取] 从MCP服务器动态获取工具列表")
        tools = await self.mcp_client.get_tools()
        
        # 设置 return_direct=True 避免 LangGraph 无限循环
        for tool in tools:
            tool.return_direct = True
            
        self.tools = tools
        logger.info(f"✅ [工具加载] 成功加载 {len(self.tools)} 个工具: {[tool.name for tool in self.tools]}")
        
        # 创建图
        self.graph = self._create_graph()

    def _create_graph(self):
        """创建LangGraph工作流"""
        logger.info("🔧 [图构建] 开始创建LangGraph工作流")

        # 创建状态图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("llm", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))

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

    def _call_model(self, state: AgentState):
        """调用语言模型"""
        start_time = time.time()
        messages = state["messages"]

        logger.info("🧠 [LLM调用] 开始调用语言模型")
        logger.info(f"📨 [输入消息] 消息数量: {len(messages)}")

        # 确保系统提示存在
        has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
        if not has_system_message:
            # 在消息列表开头插入系统提示
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
            logger.info("📋 [系统提示] 已添加强化的系统提示")

        # 记录输入消息详情
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            msg_content = getattr(msg, 'content', '')[:100] if hasattr(
                msg, 'content') else str(msg)[:100]
            logger.info(f"   [{i+1}] {msg_type}: {msg_content}...")

        # 检查消息数量，如果超过阈值则进行截断或摘要
        if len(messages) > 100:  # 设置最大消息数量阈值
            logger.info(f"📏 [消息截断] 消息数量 {len(messages)} 超过阈值，保留最近的50条")
            # 保留系统消息和最近的49条消息
            system_msg = messages[0] if isinstance(messages[0], SystemMessage) else SystemMessage(content=SYSTEM_PROMPT)
            messages = [system_msg] + messages[-49:]
            # 更新state
            state["messages"] = messages

        try:
            # 获取LLM客户端
            llm = self._get_llm_client()

            # 绑定工具
            llm_with_tools = llm.bind_tools(self.tools)

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
                
                # 检查是否有Python REPL工具调用，如果有则立即添加占位符ToolMessage
                messages_to_return = [response]
                has_python_repl = any(tool_call.get('name', '').endswith('python_repl_tool') 
                                    for tool_call in response.tool_calls)
                
                if has_python_repl:
                    logger.info("📝 [占位符] 检测到Python REPL工具调用，立即添加占位符消息")
                    for tool_call in response.tool_calls:
                        if tool_call.get('name', '').endswith('python_repl_tool'):
                            placeholder_tool_msg = ToolMessage(
                                content="[等待用户确认执行]",
                                tool_call_id=tool_call.get('id', ''),
                                name=tool_call.get('name', '')
                            )
                            messages_to_return.append(placeholder_tool_msg)
                            logger.info(f"📝 [占位符] 为工具 {tool_call.get('name', '')} 添加占位符消息")
                
                return {"messages": messages_to_return}
            else:
                logger.info("✅ [直接响应] 模型生成了直接回答，无需调用工具")

            return {"messages": [response]}

        except Exception as e:
            call_time = time.time() - start_time
            logger.error(f"❌ [LLM错误] 模型调用失败，耗时: {call_time:.2f}s")
            logger.error(f"🔥 [错误详情] {str(e)}")
            raise e

    def _should_force_tool_call(self, content: str) -> bool:
        """判断是否应该强制调用工具"""
        if not content:
            return False
        
        content_lower = content.lower()
        force_indicators = [
            "计算", "执行", "运行", "print", "代码", 
            "分析", "绘图", "plot", "数据", "结果",
            "*", "+", "-", "/", "=", "99", "9999"
        ]
        
        return any(indicator in content_lower for indicator in force_indicators)

    def _should_continue(self, state: AgentState):
        """判断是否继续执行工具"""
        last_message = state["messages"][-1]

        # 检查是否有工具调用
        if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # 检查是否有Python REPL工具调用，如果有则不自动执行，等待用户确认
            has_python_repl = any(tool_call.get('name', '').endswith('python_repl_tool') 
                                for tool_call in last_message.tool_calls)
            
            if has_python_repl:
                logger.info("⏸️ [流程判断] 检测到Python REPL工具调用，添加占位符工具消息以保持序列完整性")
                
                # 为每个Python REPL工具调用添加占位符ToolMessage，以保持消息序列的完整性
                for tool_call in last_message.tool_calls:
                    if tool_call.get('name', '').endswith('python_repl_tool'):
                        placeholder_tool_msg = ToolMessage(
                            content="[等待用户确认执行]",
                            tool_call_id=tool_call.get('id', ''),
                            name=tool_call.get('name', '')
                        )
                        state["messages"].append(placeholder_tool_msg)
                        logger.info(f"📝 [占位符] 为工具 {tool_call.get('name', '')} 添加占位符消息")
                
                return "end"
            else:
                logger.info("🔄 [流程判断] 需要执行其他工具，继续到工具节点")
                return "continue"
        else:
            logger.info("🏁 [流程判断] 无需执行工具，流程结束")
            return "end"

    def _get_llm_client(self):
        """获取LLM客户端"""
        # 优先使用OpenAI API（更稳定）
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key and openai_key != "your_openai_api_key_here":
            logger.info("🔑 [LLM配置] 使用OpenAI API")
            return ChatOpenAI(
                model="gpt-4o",  # 使用完整版gpt-4o，function calling更稳定
                temperature=0,
                api_key=SecretStr(openai_key)
            )
        # 备用DeepSeek API
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        deepseek_base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        if deepseek_key and deepseek_key != "your_deepseek_api_key_here":
            logger.info(f"🔑 [LLM配置] 使用DeepSeek API, Base URL: {deepseek_base_url}")
            return ChatOpenAI(
                model="deepseek-chat",
                temperature=0,  # 设置为0提高确定性
                api_key=SecretStr(deepseek_key),
                base_url=deepseek_base_url
            )
        else:
            logger.error("❌ [LLM配置] 未找到有效的API密钥")
            logger.error("   请在env.template中设置真实的API密钥")
            raise ValueError(
                "No valid API key found. Please set a real OPENAI_API_KEY or DEEPSEEK_API_KEY in env.template")

    async def process_message_async(self, message: str, history: List[BaseMessage] = None) -> Dict[str, Any]:
        """异步处理用户消息，支持历史消息"""
        start_time = time.time()

        try:
            logger.info("🎯 [消息处理] 开始处理用户消息")
            logger.info(f"📝 [输入消息] {message}")
            
            # 准备消息列表
            messages = []
            
            # 添加历史消息
            if history:
                messages.extend(history)
                logger.info(f"📚 [历史加载] 加载了 {len(history)} 条历史消息")
            
            # 添加新的用户消息
            messages.append(HumanMessage(content=message))

            # 创建输入状态
            initial_state = {
                "messages": messages
            }

            logger.info("🚀 [图执行] 开始执行LangGraph工作流")
            logger.info(f"📊 [初始状态] 总消息数: {len(messages)}")

            # 运行图 - 使用异步调用，设置递归限制
            config = {"recursion_limit": 15}
            result = await self.graph.ainvoke(initial_state, config=config)

            process_time = time.time() - start_time

            # 获取最终消息
            final_messages = result.get("messages", [])
            final_response = ""

            # 查找最后一条AI消息作为最终响应
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage):
                    final_response = msg.content
                    break

            if not final_response:
                final_response = "抱歉，处理完成但没有生成响应。"

            logger.info(f"✅ [处理完成] 消息处理成功，耗时: {process_time:.2f}s")
            logger.info(f"📊 [最终状态] 总消息数: {len(final_messages)}")
            logger.info(f"📤 [最终响应] {final_response[:200]}...")

            return {
                "success": True,
                "final_response": final_response,
                "messages": final_messages,
                "process_time": process_time
            }

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"❌ [处理错误] 消息处理失败，耗时: {process_time:.2f}s")
            logger.error(f"🔥 [错误详情] {str(e)}")

            import traceback
            logger.error(f"📋 [错误栈] {traceback.format_exc()}")

            return {
                "success": False,
                "error": f"处理消息时发生错误: {str(e)}",
                "messages": [],
                "process_time": process_time
            }

    def process_message(self, message: str, history: List[BaseMessage] = None) -> Dict[str, Any]:
        """同步包装的消息处理函数"""
        # 检查是否已经在事件循环中
        try:
            loop = asyncio.get_running_loop()
            # 如果已经在事件循环中，创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.process_message_async(message, history))
                return future.result()
        except RuntimeError:
            # 没有运行的事件循环，可以直接使用asyncio.run
            return asyncio.run(self.process_message_async(message, history))


# 创建全局智能体实例
logger.info("🏗️ [系统初始化] 创建全局RNA智能体实例")
rna_agent = RNAAnalysisAgent()


def process_user_message(message: str) -> Dict[str, Any]:
    """处理用户消息的主入口函数"""
    logger.info(f"📨 [入口函数] 收到用户消息: {message}")
    result = rna_agent.process_message(message)
    logger.info(f"📤 [入口函数] 返回处理结果: success={result['success']}")
    return result

def process_user_message_with_history(message: str, history: List[BaseMessage] = None) -> Dict[str, Any]:
    """处理用户消息的主入口函数，支持历史记忆"""
    logger.info(f"📨 [入口函数] 收到用户消息: {message}")
    logger.info(f"📚 [入口函数] 历史消息数量: {len(history) if history else 0}")
    
    result = rna_agent.process_message(message, history)
    logger.info(f"📤 [入口函数] 返回处理结果: success={result['success']}")
    logger.info(f"💬 [入口函数] 最终消息数量: {len(result.get('messages', []))}")
    
    return result


if __name__ == "__main__":
    # 测试代码
    print("🧬 RNA分析智能体核心启动")

    # 测试消息处理
    test_message = "请计算99*99"
    result = process_user_message(test_message)

    if result["success"]:
        print("✅ 智能体处理成功")
        print(f"响应: {result['final_response']}")
    else:
        print(f"❌ 处理失败: {result['error']}")

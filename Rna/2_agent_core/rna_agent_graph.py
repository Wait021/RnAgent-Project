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

        # 记录输入消息详情
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            msg_content = getattr(msg, 'content', '')[:100] if hasattr(
                msg, 'content') else str(msg)[:100]
            logger.info(f"   [{i+1}] {msg_type}: {msg_content}...")

        # 检查消息数量，如果超过阈值则进行截断或摘要
        if len(messages) > 100:  # 设置最大消息数量阈值
            logger.info(f"📏 [消息截断] 消息数量 {len(messages)} 超过阈值，保留最近的50条")
            # 保留最近的50条消息
            messages = messages[-50:]
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

            # 运行图 - 使用异步调用
            result = await self.graph.ainvoke(initial_state)

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
    test_message = "请加载PBMC3K数据"
    result = process_user_message(test_message)

    if result["success"]:
        print("✅ 智能体处理成功")
        print(f"响应: {result['final_response']}")
    else:
        print(f"❌ 处理失败: {result['error']}")

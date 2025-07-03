#!/usr/bin/env python3
"""
对话管理工具函数
提供对话摘要、历史管理等功能
"""

import logging
from typing import List, Tuple, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr
import os

logger = logging.getLogger(__name__)

class ConversationSummary(BaseModel):
    """对话摘要结构"""
    title: str = Field(description="对话的标题")
    summary: str = Field(description="对话的简要摘要")

def get_llm_for_summary():
    """获取用于摘要的LLM客户端"""
    # 优先使用DeepSeek API
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        return ChatOpenAI(
            model="deepseek-chat",
            temperature=0,
            api_key=SecretStr(deepseek_key),
            base_url="https://www.chataiapi.com/v1"
        )
    
    # 备用OpenAI API
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=SecretStr(openai_key)
        )
    
    raise ValueError("No API key found for conversation summary")

def get_conversation_summary(messages: List[BaseMessage]) -> Tuple[str, str]:
    """
    生成对话的标题和摘要
    
    Args:
        messages: 对话消息列表
        
    Returns:
        Tuple[str, str]: (标题, 摘要)
    """
    try:
        # 过滤出有效的对话消息（去除工具消息）
        conversation_messages = []
        for msg in messages:
            if isinstance(msg, (HumanMessage, AIMessage)):
                conversation_messages.append(msg)
        
        if not conversation_messages:
            return "空对话", "没有有效的对话内容"
        
        # 如果消息很少，直接基于内容生成简单摘要
        if len(conversation_messages) <= 2:
            first_human_msg = None
            for msg in conversation_messages:
                if isinstance(msg, HumanMessage):
                    first_human_msg = msg
                    break
            
            if first_human_msg:
                content = first_human_msg.content[:100]
                return f"关于{content[:20]}...", f"用户询问: {content}"
            else:
                return "简短对话", "简短的对话交流"
        
        # 获取LLM并生成摘要
        llm = get_llm_for_summary()
        
        prompt_template = ChatPromptTemplate.from_messages([
            MessagesPlaceholder("msgs"),
            ("human", "根据上述对话内容，生成一个简洁的标题和摘要。标题应该控制在10个字以内，摘要应该控制在50个字以内。")
        ])
        
        structured_llm = llm.with_structured_output(ConversationSummary)
        summarized_chain = prompt_template | structured_llm
        
        # 限制传入的消息数量以控制token使用
        limited_messages = conversation_messages[-10:] if len(conversation_messages) > 10 else conversation_messages
        
        response = summarized_chain.invoke({"msgs": limited_messages})
        return response.title, response.summary
        
    except Exception as e:
        logger.error(f"生成对话摘要失败: {e}")
        # 返回基于第一条消息的简单摘要
        if messages:
            first_msg = messages[0]
            if hasattr(first_msg, 'content'):
                content = str(first_msg.content)[:50]
                return "对话摘要", f"对话内容: {content}..."
        
        return "对话记录", "无法生成摘要"

def truncate_conversation(messages: List[BaseMessage], max_length: int = 50) -> List[BaseMessage]:
    """
    截断对话历史，保留最重要的消息
    
    Args:
        messages: 原始消息列表
        max_length: 最大保留消息数量
        
    Returns:
        List[BaseMessage]: 截断后的消息列表
    """
    if len(messages) <= max_length:
        return messages
    
    logger.info(f"对话消息过长({len(messages)}条)，截断到{max_length}条")
    
    # 策略1：保留最近的消息
    if max_length <= 20:
        return messages[-max_length:]
    
    # 策略2：保留开头几条和最近的消息
    keep_start = max_length // 4  # 保留开头25%
    keep_end = max_length - keep_start  # 其余保留最近的
    
    result = messages[:keep_start] + messages[-keep_end:]
    
    # 在中间插入一条摘要消息
    try:
        middle_messages = messages[keep_start:-keep_end]
        if middle_messages:
            title, summary = get_conversation_summary(middle_messages)
            summary_msg = AIMessage(content=f"[对话摘要] {title}: {summary}")
            result = messages[:keep_start] + [summary_msg] + messages[-keep_end:]
    except Exception as e:
        logger.warning(f"生成中间摘要失败: {e}")
    
    return result

def format_conversation_preview(messages: List[BaseMessage], max_chars: int = 100) -> str:
    """
    格式化对话预览文本
    
    Args:
        messages: 消息列表
        max_chars: 最大字符数
        
    Returns:
        str: 预览文本
    """
    if not messages:
        return "空对话"
    
    # 查找第一条有效的人类消息
    for msg in messages:
        if isinstance(msg, HumanMessage) and msg.content:
            content = str(msg.content).strip()
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
            return content
    
    # 如果没有人类消息，查找AI消息
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.content:
            content = str(msg.content).strip()
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
            return f"[AI回复] {content}"
    
    return "无有效内容"

def get_conversation_stats(messages: List[BaseMessage]) -> Dict[str, Any]:
    """
    获取对话统计信息
    
    Args:
        messages: 消息列表
        
    Returns:
        Dict[str, Any]: 统计信息
    """
    stats = {
        "total_messages": len(messages),
        "human_messages": 0,
        "ai_messages": 0,
        "tool_messages": 0,
        "total_chars": 0
    }
    
    for msg in messages:
        if isinstance(msg, HumanMessage):
            stats["human_messages"] += 1
        elif isinstance(msg, AIMessage):
            stats["ai_messages"] += 1
        elif isinstance(msg, ToolMessage):
            stats["tool_messages"] += 1
        
        if hasattr(msg, 'content') and msg.content:
            stats["total_chars"] += len(str(msg.content))
    
    return stats 
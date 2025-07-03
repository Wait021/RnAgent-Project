#!/usr/bin/env python3
"""
RNA智能体核心HTTP服务器
提供RESTful API接口供前端调用
"""

import uvicorn
import logging
import time
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import os
import sys
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
from config import get_config
from rna_agent_graph import process_user_message_with_history
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage

# 获取配置
config = get_config()

# 设置详细的日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('agent_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 全局对话存储 - 在生产环境中应使用Redis或数据库
conversation_store: Dict[str, List[BaseMessage]] = {}

# 创建FastAPI应用
app = FastAPI(
    title="RNA智能体核心服务",
    description="处理自然语言请求，调用MCP工具，管理对话流程",
    version="2.1.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型定义
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    conversation_id: str
    final_response: str = ""
    error: str = ""
    messages: list = []
    message_count: int = 0

class ConversationListResponse(BaseModel):
    conversations: List[Dict[str, Any]]

def serialize_message(message: BaseMessage) -> Dict[str, Any]:
    """将BaseMessage序列化为字典"""
    result = {
        "type": type(message).__name__,
        "content": message.content,
    }
    
    if hasattr(message, "tool_call_id"):
        result["tool_call_id"] = message.tool_call_id
    if hasattr(message, "name"):
        result["name"] = message.name
    if hasattr(message, "artifact"):
        result["artifact"] = message.artifact
    if hasattr(message, "tool_calls"):
        result["tool_calls"] = message.tool_calls
        
    return result

def deserialize_message(data: Dict[str, Any]) -> BaseMessage:
    """将字典反序列化为BaseMessage"""
    msg_type = data["type"]
    content = data["content"]
    
    if msg_type == "HumanMessage":
        return HumanMessage(content=content)
    elif msg_type == "AIMessage":
        msg = AIMessage(content=content)
        if "tool_calls" in data:
            msg.tool_calls = data["tool_calls"]
        return msg
    elif msg_type == "ToolMessage":
        return ToolMessage(
            content=content,
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", ""),
            artifact=data.get("artifact", [])
        )
    else:
        # 默认返回HumanMessage
        return HumanMessage(content=content)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """HTTP请求日志中间件"""
    start_time = time.time()

    # 记录请求开始
    logger.info(f"🔄 [HTTP请求] {request.method} {request.url}")
    logger.info(f"📋 [请求头] {dict(request.headers)}")

    # 如果是POST请求，尝试记录body
    if request.method == "POST":
        try:
            body = await request.body()
            if body:
                logger.info(f"📝 [请求体] {body.decode('utf-8')}")
        except Exception as e:
            logger.warning(f"⚠️ [请求体读取失败] {e}")

    response = await call_next(request)

    # 记录响应
    process_time = time.time() - start_time
    logger.info(
        f"✅ [HTTP响应] 状态码: {response.status_code}, 耗时: {process_time:.2f}s")

    return response


@app.get("/health")
async def health_check():
    """健康检查接口"""
    logger.info("🏥 [健康检查] 收到健康检查请求")

    # 检查环境变量
    api_keys_status = {
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "deepseek": bool(os.environ.get("DEEPSEEK_API_KEY"))
    }

    result = {
        "status": "healthy",
        "service": "RNA智能体核心服务",
        "version": "2.0.0",
        "api_keys": api_keys_status,
        "timestamp": time.time()
    }

    logger.info(f"✅ [健康检查] 返回结果: {result}")
    return result


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理聊天消息"""
    start_time = time.time()

    try:
        logger.info("="*80)
        logger.info(f"🤖 [聊天开始] 收到用户消息")
        logger.info(f"📝 [用户消息] {request.message}")
        logger.info(f"🆔 [对话ID] {request.conversation_id}")
        logger.info(f"📏 [消息长度] {len(request.message)} 字符")
        logger.info("="*80)

        # 获取或创建conversation_id
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # 获取历史消息
        history = conversation_store.get(conversation_id, [])
        logger.info(f"📚 [历史消息] 找到 {len(history)} 条历史消息")

        # 调用智能体处理消息
        logger.info("🚀 [Agent调用] 开始调用智能体处理消息...")
        result = process_user_message_with_history(request.message, history)

        # 更新对话存储
        if result["success"]:
            conversation_store[conversation_id] = result.get("messages", [])
            logger.info(f"💾 [存储更新] 对话 {conversation_id} 已更新，共 {len(result.get('messages', []))} 条消息")

        process_time = time.time() - start_time

        if result["success"]:
            logger.info(f"✅ [处理成功] 智能体处理完成")
            logger.info(f"⏱️ [处理时间] {process_time:.2f}s")
            logger.info(f"📤 [最终响应] {result['final_response'][:200]}...")
            logger.info(f"💬 [消息数量] {len(result.get('messages', []))}")

            # 记录消息类型统计
            messages = result.get('messages', [])
            message_types = {}
            for msg in messages:
                msg_type = type(msg).__name__
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
            logger.info(f"📊 [消息类型统计] {message_types}")

            return ChatResponse(
                success=True,
                conversation_id=conversation_id,
                final_response=result["final_response"],
                messages=[serialize_message(msg) for msg in result.get("messages", [])],
                message_count=len(result.get("messages", []))
            )
        else:
            logger.error(f"❌ [处理失败] 智能体处理出错")
            logger.error(f"⏱️ [处理时间] {process_time:.2f}s")
            logger.error(f"🔥 [错误信息] {result['error']}")

            return ChatResponse(
                success=False,
                conversation_id=conversation_id,
                error=result["error"]
            )

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"💥 [聊天接口异常] 发生未预期错误")
        logger.error(f"⏱️ [处理时间] {process_time:.2f}s")
        logger.error(f"🔥 [异常详情] {str(e)}")
        logger.error(f"📍 [异常类型] {type(e).__name__}")

        import traceback
        logger.error(f"📋 [异常栈] {traceback.format_exc()}")

        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations", response_model=ConversationListResponse)
async def list_conversations():
    """获取所有对话列表"""
    logger.info("📋 [对话列表] 获取所有对话")
    
    conversations = []
    for conv_id, messages in conversation_store.items():
        if messages:
            # 获取第一条和最后一条消息
            first_msg = messages[0] if messages else None
            last_msg = messages[-1] if messages else None
            
            conversations.append({
                "id": conv_id,
                "message_count": len(messages),
                "first_message": first_msg.content[:100] if first_msg else "",
                "last_message": last_msg.content[:100] if last_msg else "",
                "created_at": "unknown",  # 在实际应用中应该记录时间戳
                "updated_at": "unknown"
            })
    
    logger.info(f"📋 [对话列表] 返回 {len(conversations)} 个对话")
    return ConversationListResponse(conversations=conversations)

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取特定对话的详细信息"""
    logger.info(f"🔍 [获取对话] 对话ID: {conversation_id}")
    
    if conversation_id not in conversation_store:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    messages = conversation_store[conversation_id]
    return {
        "conversation_id": conversation_id,
        "message_count": len(messages),
        "messages": [serialize_message(msg) for msg in messages]
    }

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除特定对话"""
    logger.info(f"🗑️ [删除对话] 对话ID: {conversation_id}")
    
    if conversation_id not in conversation_store:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    del conversation_store[conversation_id]
    logger.info(f"✅ [删除成功] 对话 {conversation_id} 已删除")
    
    return {"message": f"对话 {conversation_id} 已删除"}

@app.post("/conversations/{conversation_id}/clear")
async def clear_conversation(conversation_id: str):
    """清空特定对话的消息"""
    logger.info(f"🧹 [清空对话] 对话ID: {conversation_id}")
    
    conversation_store[conversation_id] = []
    logger.info(f"✅ [清空成功] 对话 {conversation_id} 已清空")
    
    return {"message": f"对话 {conversation_id} 已清空"}

@app.get("/")
async def root():
    """根路径"""
    logger.info("🏠 [根路径] 收到根路径请求")
    return {
        "message": "RNA智能体核心服务",
        "version": "2.0.0",
        "status": "running",
        "timestamp": time.time()
    }

if __name__ == "__main__":
    logger.info("🚀 启动RNA智能体核心HTTP服务器...")
    logger.info("=" * 60)

    # 检查环境变量
    openai_key = os.environ.get("OPENAI_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

    if openai_key:
        logger.info("✅ OpenAI API密钥: 已设置")
    else:
        logger.warning("⚠️ OpenAI API密钥: 未设置")

    if deepseek_key:
        logger.info("✅ DeepSeek API密钥: 已设置")
    else:
        logger.warning("⚠️ DeepSeek API密钥: 未设置")

    if not openai_key and not deepseek_key:
        logger.error("❌ 未检测到任何API密钥，请设置OPENAI_API_KEY或DEEPSEEK_API_KEY")

    logger.info("=" * 60)
    logger.info(f"🌐 服务器地址: http://{config.host}:{config.agent_port}")
    logger.info(f"📚 API文档: http://{config.host}:{config.agent_port}/docs")
    logger.info(f"💚 健康检查: http://{config.host}:{config.agent_port}/health")
    logger.info("=" * 60)

    # 启动服务器
    uvicorn.run(
        app,
        host=config.host,
        port=config.agent_port,
        log_level="info",
        access_log=True
    )

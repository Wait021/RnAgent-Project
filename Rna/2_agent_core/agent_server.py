#!/usr/bin/env python3
"""
RNA智能体核心HTTP服务器
提供RESTful API接口供前端调用
"""

import uvicorn
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import os
import sys
import json

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(__file__))

# 导入智能体核心
from rna_agent_graph import process_user_message

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

# 创建FastAPI应用
app = FastAPI(
    title="RNA智能体核心服务",
    description="处理自然语言请求，调用MCP工具，管理对话流程",
    version="2.0.0"
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

class ChatResponse(BaseModel):
    success: bool
    final_response: str = ""
    error: str = ""
    messages: list = []

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
    logger.info(f"✅ [HTTP响应] 状态码: {response.status_code}, 耗时: {process_time:.2f}s")
    
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
        logger.info(f"📏 [消息长度] {len(request.message)} 字符")
        logger.info("="*80)
        
        # 调用智能体处理消息
        logger.info("🚀 [Agent调用] 开始调用智能体处理消息...")
        result = process_user_message(request.message)
        
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
                final_response=result["final_response"],
                messages=result.get("messages", [])
            )
        else:
            logger.error(f"❌ [处理失败] 智能体处理出错")
            logger.error(f"⏱️ [处理时间] {process_time:.2f}s")
            logger.error(f"🔥 [错误信息] {result['error']}")
            
            return ChatResponse(
                success=False,
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
    logger.info("🌐 服务器地址: http://localhost:8002")
    logger.info("📚 API文档: http://localhost:8002/docs")
    logger.info("💚 健康检查: http://localhost:8002/health")
    logger.info("=" * 60)
    
    # 启动服务器
    uvicorn.run(
        app,
        host="localhost",
        port=8002,
        log_level="info",
        access_log=True
    ) 
#!/usr/bin/env python3
"""
RnAgent 前端应用 v2.0 - 完全解耦版本
只负责用户界面交互，通过HTTP调用智能体核心
"""

import streamlit as st
import requests
import json
import os
import re
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="RnAgent - 单细胞RNA分析智能体",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS样式
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #2E86AB;
        font-size: 3em;
        margin-bottom: 0.5em;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-online {
        background-color: #00ff00;
        box-shadow: 0 0 10px #00ff00;
    }
    
    .status-offline {
        background-color: #ff0000;
        box-shadow: 0 0 10px #ff0000;
    }
    
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .user-message {
        background-color: #e6f3ff;
        border-left: 4px solid #0066cc;
    }
    
    .assistant-message {
        background-color: #f0f8e6;
        border-left: 4px solid #00cc66;
    }
    
    .tool-message {
        background-color: #fff5e6;
        border-left: 4px solid #ff9900;
    }
</style>
""", unsafe_allow_html=True)

# 主标题
st.markdown('<h1 class="main-title">🧬 RnAgent - 单细胞RNA分析智能体</h1>', unsafe_allow_html=True)

# 智能体核心服务配置
AGENT_CORE_URL = "http://localhost:8002"

class FrontendService:
    """前端服务类 - 负责与智能体核心通信"""
    
    @staticmethod
    def check_agent_health() -> bool:
        """检查智能体核心服务状态"""
        try:
            response = requests.get(f"{AGENT_CORE_URL}/health", timeout=3)
            return response.status_code == 200
        except:
            return False
    
    @staticmethod
    def send_message(message: str) -> Dict[str, Any]:
        """发送消息到智能体核心"""
        try:
            response = requests.post(
                f"{AGENT_CORE_URL}/chat",
                json={"message": message},
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"连接智能体服务失败: {str(e)}"
            }
    
    @staticmethod
    def trigger_quick_action(action_name: str) -> Dict[str, Any]:
        """触发快速操作"""
        action_messages = {
            "load_data": "请加载PBMC3K数据并显示基本信息",
            "quality_control": "请进行质量控制分析",
            "preprocessing": "请进行数据预处理分析",
            "dimensionality_reduction": "请进行降维分析",
            "clustering": "请进行聚类分析",
            "marker_genes": "请进行标记基因分析",
            "generate_report": "请生成完整的分析报告",
            "full_analysis": "请执行完整的PBMC3K分析流程：从数据加载到报告生成"
        }
        
        message = action_messages.get(action_name, action_name)
        return FrontendService.send_message(message)

def is_python_code(text: str) -> bool:
    """判断文本是否为Python代码"""
    if not text or not isinstance(text, str):
        return False
    
    text = text.strip()
    python_indicators = [
        "import ", "from ", "def ", "class ", "plt.show()", "plt.figure",
        "sc.pl.", "adata = ", "pd.DataFrame", "np.", "matplotlib", "scanpy"
    ]
    
    if text.startswith("import ") or text.startswith("from "):
        return True
    
    if "plt.show()" in text or "plt.figure" in text:
        return True
    
    indicator_count = sum(1 for indicator in python_indicators if indicator in text)
    return indicator_count >= 2

def display_chat_messages():
    """显示聊天消息"""
    for i, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            st.markdown('<div class="chat-message user-message">', unsafe_allow_html=True)
            st.markdown("**👤 用户:**")
            st.write(message["content"])
            st.markdown('</div>', unsafe_allow_html=True)
            
        elif message["role"] == "assistant":
            st.markdown('<div class="chat-message assistant-message">', unsafe_allow_html=True)
            st.markdown("**🤖 助手:**")
            st.write(message["content"])
            
            # 如果包含Python代码，提供运行按钮
            if is_python_code(message["content"]):
                run_key = f"run_code_{i}_{hash(message['content'])}"
                if st.button("▶️ 运行代码", key=run_key):
                    with st.spinner("正在执行代码..."):
                        result = FrontendService.send_message(f"请执行以下代码：\n\n{message['content']}")
                        if result.get("success"):
                            st.success("代码执行完成！")
                            # 添加执行结果到聊天历史
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": result.get("final_response", "代码执行完成"),
                                "timestamp": datetime.now().isoformat()
                            })
                            st.rerun()
                        else:
                            st.error(f"代码执行失败: {result.get('error', 'Unknown error')}")
            
            st.markdown('</div>', unsafe_allow_html=True)

def get_available_models():
    """根据API密钥自动检测可用的模型"""
    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    
    available_models = {}
    
    # 检查OpenAI API
    if openai_key:
        available_models.update({
            "OpenAI GPT-4o": "gpt-4o",
            "OpenAI GPT-4 Turbo": "gpt-4-turbo"
        })
    
    # 检查DeepSeek API  
    if deepseek_key:
        available_models.update({
            "DeepSeek Chat": "deepseek-chat"
        })
    
    return available_models, openai_key, deepseek_key

# 初始化会话状态
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 侧边栏
with st.sidebar:
    st.title("⚙️ 设置")
    
    # 获取可用模型
    available_models, openai_key, deepseek_key = get_available_models()
    
    # API密钥状态
    st.subheader("🔑 API状态")
    
    if openai_key:
        st.markdown('<span class="status-indicator status-online"></span>OpenAI API: 已配置', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-indicator status-offline"></span>OpenAI API: 未配置', unsafe_allow_html=True)
    
    if deepseek_key:
        st.markdown('<span class="status-indicator status-online"></span>DeepSeek API: 已配置', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-indicator status-offline"></span>DeepSeek API: 未配置', unsafe_allow_html=True)
    
    # 服务状态
    st.subheader("🖥️ 服务状态")
    
    # 检查智能体核心服务状态
    if FrontendService.check_agent_health():
        st.markdown('<span class="status-indicator status-online"></span>智能体服务: 在线', unsafe_allow_html=True)
        agent_online = True
    else:
        st.markdown('<span class="status-indicator status-offline"></span>智能体服务: 离线', unsafe_allow_html=True)
        agent_online = False
        st.warning("⚠️ 智能体核心服务离线，请启动服务")
    
    # 快速操作
    st.subheader("🚀 快速操作")
    
    if not agent_online:
        st.error("❌ 智能体服务离线，无法使用快速操作功能")
        st.info("💡 请启动智能体核心服务")
    else:
        # 快速操作按钮
        if st.button("📊 加载PBMC3K数据", use_container_width=True):
            with st.spinner("正在处理..."):
                result = FrontendService.trigger_quick_action("load_data")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请加载PBMC3K数据并显示基本信息",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": result.get("final_response", "数据加载完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
        
        if st.button("🔍 质量控制分析", use_container_width=True):
            with st.spinner("正在处理..."):
                result = FrontendService.trigger_quick_action("quality_control")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请进行质量控制分析",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.get("final_response", "质量控制分析完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
        
        if st.button("⚙️ 数据预处理", use_container_width=True):
            with st.spinner("正在处理..."):
                result = FrontendService.trigger_quick_action("preprocessing")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请进行数据预处理分析", 
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.get("final_response", "数据预处理完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
        
        if st.button("📈 降维分析", use_container_width=True):
            with st.spinner("正在处理..."):
                result = FrontendService.trigger_quick_action("dimensionality_reduction")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请进行降维分析",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.get("final_response", "降维分析完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
        
        if st.button("🎯 聚类分析", use_container_width=True):
            with st.spinner("正在处理..."):
                result = FrontendService.trigger_quick_action("clustering")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请进行聚类分析",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.get("final_response", "聚类分析完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
        
        if st.button("🧬 标记基因分析", use_container_width=True):
            with st.spinner("正在处理..."):
                result = FrontendService.trigger_quick_action("marker_genes")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请进行标记基因分析",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.get("final_response", "标记基因分析完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
        
        if st.button("📋 生成分析报告", use_container_width=True):
            with st.spinner("正在处理..."):
                result = FrontendService.trigger_quick_action("generate_report")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请生成完整的分析报告",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.get("final_response", "分析报告生成完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
        
        st.divider()
        
        if st.button("🚀 完整分析流程", use_container_width=True, type="primary"):
            with st.spinner("正在执行完整分析流程..."):
                result = FrontendService.trigger_quick_action("full_analysis")
                if result.get("success"):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "请执行完整的PBMC3K分析流程",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.get("final_response", "完整分析流程执行完成"),
                        "timestamp": datetime.now().isoformat()
                    })
                    st.rerun()
                else:
                    st.error(f"操作失败: {result.get('error', 'Unknown error')}")
    
    st.divider()
    
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# 主聊天界面
st.subheader("💬 对话界面")

# 显示聊天历史
if st.session_state.chat_history:
    display_chat_messages()
else:
            st.info("👋 欢迎使用RnAgent！您可以：\n\n"
           "• 使用侧边栏的快速操作按钮\n"
           "• 在下方输入自然语言问题\n"
           "• 询问关于PBMC3K数据分析的任何问题")

# 聊天输入
if prompt := st.chat_input("请输入您的问题或分析需求..."):
    if not agent_online:
        st.error("❌ 智能体服务离线，请先启动服务")
    else:
        # 添加用户消息到历史
        st.session_state.chat_history.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().isoformat()
        })
        
        # 显示用户消息
        with st.chat_message("user"):
            st.write(prompt)
        
        # 处理消息并显示响应
        with st.chat_message("assistant"):
            with st.spinner("正在思考..."):
                result = FrontendService.send_message(prompt)
                
                if result.get("success"):
                    response = result.get("final_response", "处理完成")
                    st.write(response)
                    
                    # 添加助手响应到历史
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": response,
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    error_msg = f"处理失败: {result.get('error', 'Unknown error')}"
                    st.error(error_msg)
                    
                    # 添加错误信息到历史
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg,
                        "timestamp": datetime.now().isoformat()
                    })

# 页脚
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>🧬 RnAgent v2.0 - 完全解耦架构</p>
        <p>前端 (8501) ← → 智能体核心 (8002) ← → MCP后端 (8000)</p>
    </div>
    """,
    unsafe_allow_html=True
) 
#!/usr/bin/env python3
"""
RnAgent 前端应用 - 重构美化版本
模块化设计，保持逻辑不变，提升视觉体验
"""

import streamlit as st
import os
import sys
import asyncio
import json
import requests
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from uuid import uuid4

# 设置详细的日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('rna_streamlit_app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# MCP服务器URL
MCP_SERVER_URL = "http://localhost:8000/sse"
# Agent Core HTTP API
AGENT_CORE_CHAT_URL = "http://localhost:8002/chat"
AGENT_CORE_CONVERSATIONS_URL = "http://localhost:8002/conversations"

# 加载环境变量
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="RnAgent - 单细胞RNA分析智能体",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "### 🧬 RnAgent v2.1\n基于MCP架构的单细胞RNA分析智能体\n\n✨ 支持对话记忆 | 自然语言交互 | 可视化分析",
        "Get Help": "https://github.com/your-repo/RnAgent",
        "Report a Bug": "https://github.com/your-repo/RnAgent/issues"
    }
)

# ========= UI 组件函数 =========

def inject_global_style():
    """注入全局样式和主题"""
    st.markdown(
        """
        <style>
            /* CSS变量定义 */
            :root {
                --primary-color: #667eea;
                --secondary-color: #764ba2;
                --success-color: #4caf50;
                --error-color: #f44336;
                --warning-color: #ff9800;
                --info-color: #2196f3;
                --text-primary: #1a1a1a;
                --text-secondary: #666;
                --bg-primary: #ffffff;
                --bg-secondary: #f8fafc;
                --border-radius: 12px;
                --shadow-sm: 0 2px 8px rgba(0,0,0,0.1);
                --shadow-md: 0 4px 16px rgba(0,0,0,0.15);
                --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }

            /* 深色模式适配 */
            @media (prefers-color-scheme: dark) {
                :root {
                    --text-primary: #ffffff;
                    --text-secondary: #b0b0b0;
                    --bg-primary: #1a1a1a;
                    --bg-secondary: #2d2d2d;
                }
                
                /* 深色模式下的侧边栏 */
                .stSidebar {
                    background: linear-gradient(180deg, #1e1e2d 0%, #2d2d3a 100%) !important;
                }
                
                /* 深色模式下的消息样式 */
                .user-message {
                    background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
                    color: #bfdbfe;
                }
                
                .assistant-message {
                    background: linear-gradient(135deg, #166534 0%, #15803d 100%);
                    color: #bbf7d0;
                }
                
                .assistant-message-with-tools {
                    background: linear-gradient(135deg, #6b21a8 0%, #7c3aed 100%);
                    color: #e9d5ff;
                }
                
                .tool-message {
                    background: linear-gradient(135deg, #b45309 0%, #d97706 100%);
                    color: #fed7aa;
                }
                
                /* 深色模式下的标签样式 */
                .user-label { color: #93c5fd; }
                .assistant-label { color: #86efac; }
                .assistant-label-with-tools { color: #d8b4fe; }
                .tool-label { color: #fdba74; }
                
                /* 深色模式下的工具调用状态 */
                .tool-pending {
                    background: linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%);
                }
                
                .tool-executed {
                    background: linear-gradient(135deg, #14532d 0%, #166534 100%);
                }
            }

            /* 主标题样式 */
            .main-title {
                text-align: center;
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-size: 2.5rem;
                font-weight: 800;
                margin: 2rem 0;
                animation: title-glow 3s ease-in-out infinite alternate;
            }

            @keyframes title-glow {
                from { filter: drop-shadow(0 0 20px rgba(102, 126, 234, 0.5)); }
                to { filter: drop-shadow(0 0 30px rgba(118, 75, 162, 0.7)); }
            }

        /* 状态指示器 */
            .status-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 6px;
                animation: pulse 2s infinite;
            }
            .status-online { background: var(--success-color); }
            .status-offline { background: var(--error-color); }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            /* 聊天消息样式 */
            .chat-message {
                padding: 16px 20px;
                border-radius: var(--border-radius);
                margin-bottom: 16px;
                border-left: 4px solid;
                box-shadow: var(--shadow-sm);
                transition: var(--transition);
                position: relative;
                overflow: hidden;
        }
        
        .chat-message:hover {
            transform: translateY(-2px);
                box-shadow: var(--shadow-md);
            }

            .chat-message::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
                animation: shimmer 2s infinite;
            }

            @keyframes shimmer {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }

            /* 消息类型样式 */
            .user-message {
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border-left-color: #1976d2;
            color: #0d47a1;
        }

            .assistant-message {
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
            border-left-color: #388e3c;
            color: #1b5e20;
        }

            .assistant-message-with-tools {
            background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
            border-left-color: #7b1fa2;
            color: #4a148c;
        }

            .assistant-message-with-tools::after {
            content: "🔧";
            position: absolute;
                top: 12px;
                right: 16px;
                font-size: 18px;
            opacity: 0.7;
        }

            .tool-message {
            background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
            border-left-color: #f57c00;
            color: #e65100;
        }

            /* 工具调用状态 */
            .tool-pending {
            background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
            border: 2px dashed #9c27b0;
                padding: 20px;
                border-radius: var(--border-radius);
                margin: 16px 0;
            animation: pulse-border 2s infinite;
        }

        @keyframes pulse-border {
            0% { border-color: #9c27b0; }
            50% { border-color: #e91e63; }
            100% { border-color: #9c27b0; }
        }

            .tool-executed {
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
                border: 2px solid var(--success-color);
                padding: 20px;
                border-radius: var(--border-radius);
                margin: 16px 0;
            }

            /* 标签样式 */
            .message-label {
                font-weight: 700;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
                margin-bottom: 8px;
                display: block;
            }

            .user-label { color: #1976d2; }
            .assistant-label { color: #388e3c; }
            .assistant-label-with-tools { color: #7b1fa2; }
            .tool-label { color: #f57c00; }

            /* 按钮增强 */
            .stButton > button {
            border-radius: 8px;
            font-weight: 600;
                transition: var(--transition);
                border: none;
                box-shadow: var(--shadow-sm);
        }

            .stButton > button:hover {
            transform: translateY(-2px);
                box-shadow: var(--shadow-md);
            }

            /* 图片增强 */
            .stImage > img {
                border-radius: 8px;
                box-shadow: var(--shadow-sm);
                transition: var(--transition);
            }

            .stImage:hover > img {
                transform: scale(1.02);
                box-shadow: var(--shadow-md);
            }

            /* 侧边栏样式 - 浅色模式 */
            .stSidebar {
                background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
            }
            
            /* 深色模式下的侧边栏样式覆盖 */
            @media (prefers-color-scheme: dark) {
                .stSidebar {
                    background: linear-gradient(180deg, #1e1e2d 0%, #2d2d3a 100%) !important;
                }
            }

            /* 隐藏默认元素 */
            .stDeployButton { display: none; }
            footer { visibility: hidden; }
            .stDecoration { display: none; }

            /* 响应式设计 */
            @media (max-width: 768px) {
                .main-title { font-size: 2rem; }
                .chat-message { padding: 12px 16px; }
            }
        </style>
        """,
        unsafe_allow_html=True
    )

def build_header():
    """构建页面头部"""
    st.markdown('<h1 class="main-title">🧬 RnAgent - 单细胞RNA分析智能体</h1>',
                unsafe_allow_html=True)

def build_sidebar():
    """构建侧边栏"""
    with st.sidebar:
        st.title("⚙️ 设置")

        # 获取可用模型
        available_models, openai_key, deepseek_key = get_available_models()

        # API密钥状态
        st.subheader("🔑 API状态")
        
        if openai_key:
            st.markdown('<span class="status-indicator status-online"></span>OpenAI API: 已配置', 
                       unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-indicator status-offline"></span>OpenAI API: 未配置', 
                       unsafe_allow_html=True)

        if deepseek_key:
            st.markdown('<span class="status-indicator status-online"></span>DeepSeek API: 已配置', 
                       unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-indicator status-offline"></span>DeepSeek API: 未配置', 
                       unsafe_allow_html=True)

        # 模型选择
        st.subheader("🤖 模型选择")
        
        if available_models:
            model_keys = list(available_models.keys())
            default_index = 0
            if "OpenAI GPT-4o" in model_keys:
                default_index = model_keys.index("OpenAI GPT-4o")
            elif "OpenAI GPT-4 Turbo" in model_keys:
                default_index = model_keys.index("OpenAI GPT-4 Turbo")
            elif "DeepSeek Chat" in model_keys:
                default_index = model_keys.index("DeepSeek Chat")

            selected_model_name = st.selectbox(
                "选择模型",
                options=model_keys,
                index=default_index,
                help="自动根据您的API密钥筛选可用模型"
            )
            selected_model = available_models[selected_model_name]

            if selected_model.startswith("gpt"):
                st.info("🔸 使用OpenAI模型，需要稳定的网络连接")
            elif selected_model.startswith("deepseek"):
                st.info("🔸 使用DeepSeek模型，经济实惠的选择")
        else:
            st.error("❌ 未检测到可用的API密钥")
            st.markdown("""
            **请设置以下环境变量之一：**
            ```bash
            # OpenAI API
            export OPENAI_API_KEY="your_key"
            # DeepSeek API  
            export DEEPSEEK_API_KEY="your_key"
            ```
            """)
            selected_model = "gpt-4o"
            selected_model_name = "OpenAI GPT-4o (未配置)"

        # 服务状态
        st.subheader("🖥️ 服务状态")
        
        server_online = check_mcp_server_health()
        agent_online = check_agent_core_health()
        
        if server_online:
            st.markdown('<span class="status-indicator status-online"></span>MCP服务器: 在线', 
                       unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-indicator status-offline"></span>MCP服务器: 离线', 
                       unsafe_allow_html=True)
            st.warning("⚠️ MCP服务器离线，请确保后端服务器正在运行")

        if agent_online:
            st.markdown('<span class="status-indicator status-online"></span>Agent Core: 在线', 
                       unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-indicator status-offline"></span>Agent Core: 离线', 
                       unsafe_allow_html=True)
            st.warning("⚠️ Agent Core离线，聊天功能将不可用")

        # 显示设置
        st.subheader("🖼️ 显示设置")
        image_width = st.slider(
            "图表显示宽度 (像素)",
            min_value=400,
            max_value=1200,
            value=700,
            step=50,
            help="调整生成图表的显示宽度"
        )
        st.session_state.image_width = image_width

        # 快速操作
        with st.expander("🚀 快速操作", expanded=True):
            if not server_online:
                st.error("❌ MCP服务器离线，无法使用快速操作功能")
                st.info("💡 请运行 `python run_rna_demo.py` 启动后端服务器")
            else:
                _render_quick_actions()

        # 对话管理
        with st.expander("💬 对话管理", expanded=False):
            _render_conversation_management(agent_online)

        # 数据集信息
        with st.expander("📁 数据集信息", expanded=False):
            _render_dataset_info()

        return selected_model, selected_model_name, server_online, agent_online

def _render_quick_actions():
    """渲染快速操作按钮"""
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 加载数据", use_container_width=True):
            _execute_mcp_tool("load_pbmc3k_data", "正在获取数据加载代码...")
        if st.button("🔍 质量控制", use_container_width=True):
            _execute_mcp_tool("quality_control_analysis", "正在获取质量控制代码...")
        if st.button("⚙️ 预处理", use_container_width=True):
            _execute_mcp_tool("preprocessing_analysis", "正在获取预处理代码...")
        if st.button("📈 降维分析", use_container_width=True):
            _execute_mcp_tool("dimensionality_reduction_analysis", "正在获取降维分析代码...")
    
    with col2:
        if st.button("🎯 聚类分析", use_container_width=True):
            _execute_mcp_tool("clustering_analysis", "正在获取聚类分析代码...")
        if st.button("🧬 标记基因", use_container_width=True):
            _execute_mcp_tool("marker_genes_analysis", "正在获取标记基因分析代码...")
        if st.button("📋 生成报告", use_container_width=True):
            _execute_mcp_tool("generate_analysis_report", "正在生成分析报告...")
        if st.button("🔄 清空对话", use_container_width=True):
            _clear_conversation()

    st.divider()
    
    if st.button("🚀 完整分析流程", use_container_width=True, type="primary"):
        _execute_full_analysis()

def _execute_mcp_tool(tool_name: str, spinner_text: str):
    """执行MCP工具"""
    with st.spinner(spinner_text):
        result = call_mcp_tool_sync(tool_name, {})
        if isinstance(result, dict) and "content" in result:
            tool_message = build_tool_message(tool_name, result)
            st.session_state.messages.append(tool_message)
            st.rerun()

def _clear_conversation():
    """清空对话"""
    if st.session_state.conversation_id:
        if clear_conversation(st.session_state.conversation_id):
            st.success("✅ 对话已清空")
        else:
            st.error("❌ 清空对话失败")
    
    st.session_state.messages = []
    st.session_state.conversation_id = None
    st.session_state.conversation_history = []
    st.session_state.pending_tool_calls = {}
    
    # 清理工具调用状态
    keys_to_remove = [key for key in st.session_state.keys() if key.startswith('executed_tool_')]
    for key in keys_to_remove:
        del st.session_state[key]
    
    st.rerun()

def _execute_full_analysis():
    """执行完整分析流程"""
    analysis_steps = [
        ("load_pbmc3k_data", "📊 加载数据"),
        ("quality_control_analysis", "🔍 质量控制"),
        ("preprocessing_analysis", "⚙️ 数据预处理"),
        ("dimensionality_reduction_analysis", "📈 降维分析"),
        ("clustering_analysis", "🎯 聚类分析"),
        ("marker_genes_analysis", "🧬 标记基因分析"),
        ("generate_analysis_report", "📋 生成报告")
    ]

    with st.spinner("正在执行完整分析流程..."):
        for tool_name, description in analysis_steps:
            st.info(f"正在执行: {description}")
            result = call_mcp_tool_sync(tool_name, {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message(tool_name, result)
                st.session_state.messages.append(tool_message)
            else:
                st.error(f"执行 {description} 时出错")
                break
        st.success("✅ 完整分析流程执行完毕！")
        st.rerun()

def _render_conversation_management(agent_online: bool):
    """渲染对话管理"""
    if st.session_state.conversation_id:
        st.info(f"🆔 当前对话: {st.session_state.conversation_id[:8]}...")
        if st.button("🗑️ 删除当前对话", use_container_width=True):
            if delete_conversation(st.session_state.conversation_id):
                st.success("✅ 对话已删除")
                st.session_state.conversation_id = None
                st.session_state.messages = []
                st.session_state.conversation_history = []
                st.session_state.pending_tool_calls = {}
                st.rerun()
            else:
                st.error("❌ 删除对话失败")
    else:
        st.info("💭 当前没有活跃对话")
    
    if agent_online:
        st.subheader("📋 历史对话")
        conversations = get_conversations()
        if conversations:
            for conv in conversations[:5]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    preview = conv.get("first_message", "无消息")[:30]
                    if len(preview) == 30:
                        preview += "..."
                    st.text(f"💬 {preview}")
                    st.caption(f"消息数: {conv.get('message_count', 0)}")
                with col2:
                    if st.button("📖", key=f"load_{conv['id']}", help="加载此对话"):
                        st.session_state.conversation_id = conv['id']
                        st.session_state.messages = []
                        st.success(f"✅ 已切换到对话 {conv['id'][:8]}...")
                        st.rerun()
        else:
            st.info("📭 暂无历史对话")

def _render_dataset_info():
    """渲染数据集信息"""
    current_file_path = Path(__file__).resolve()
    frontend_dir = current_file_path.parent
    rna_dir = frontend_dir.parent
    project_root = rna_dir.parent
    data_path = project_root / "PBMC3kRNA-seq" / "filtered_gene_bc_matrices" / "hg19"
    relative_path = os.path.relpath(str(data_path), str(project_root))
    
    st.info(f"""
    **PBMC3K数据集**
    - 细胞类型: 外周血单核细胞
    - 平台: 10X Genomics
    - 相对路径: `{relative_path}/`
    """)

def build_chat_area():
    """构建聊天区域"""
    # 显示欢迎信息
    if not st.session_state.messages:
        _show_welcome_message()
    
    # 显示对话历史
    for i, message in enumerate(st.session_state.messages):
        display_message(message, i)

def _show_welcome_message():
    """显示欢迎信息"""
    current_models, current_openai, current_deepseek = get_available_models()
    
    welcome_msg = """
    ### 👋 欢迎使用RnAgent！
    
    我是您的单细胞RNA分析助手，现在支持**对话记忆功能**！您可以：
    
    1. **使用侧边栏快速操作**：点击按钮执行预定义的分析步骤
    2. **在下方输入自然语言问题**：我会为您生成相应的分析代码  
    3. **运行代码并查看结果**：生成的图表会自动显示
    4. **📚 对话记忆**：我会记住您的对话历史，提供更好的上下文理解
    
    **推荐开始方式**：
    - 点击侧边栏的"🚀 完整分析流程"按钮进行端到端分析
    - 或者逐步点击各个分析步骤
    - 也可以直接在下方提问，如"请加载PBMC3K数据并显示基本信息"
    """

    if current_models:
        available_model_names = list(current_models.keys())
        welcome_msg += f"""
    **🤖 AI模型状态**：
    - ✅ 已自动检测并配置可用模型：{', '.join(available_model_names)}
    - 🎯 当前选择：已自动为您选择最佳模型
    - 💭 对话记忆：已启用，我会记住我们的对话历史
    """
    else:
        welcome_msg += """
    **⚠️ AI模型状态**：
    - ❌ 未检测到API密钥，自然语言对话功能不可用
    - 💡 您仍可使用所有快速操作按钮进行分析
    - 🔧 请在侧边栏查看API配置说明
    """

    st.markdown(welcome_msg)

def build_main_content():
    """构建主要内容区域"""
    # 使用双栏布局
    col_chat, col_result = st.columns([0.6, 0.4], gap="large")
    
    with col_chat:
        st.subheader("💬 对话区域")
        build_chat_area()
    
    with col_result:
        st.subheader("📊 结果展示")
        build_result_tabs()

def build_result_tabs():
    """构建结果标签页"""
    # 创建标签页
    tab_overview, tab_qc, tab_preprocess, tab_reduce, tab_cluster, tab_marker = st.tabs([
        "📋 概览", "🩺 质控", "⚙️ 预处理", "📉 降维", "🎯 聚类", "🧬 标记基因"
    ])
    
    with tab_overview:
        _render_overview_tab()
    
    with tab_qc:
        _render_filtered_messages("quality_control")
    
    with tab_preprocess:
        _render_filtered_messages("preprocessing")
    
    with tab_reduce:
        _render_filtered_messages("dimensionality_reduction")
    
    with tab_cluster:
        _render_filtered_messages("clustering")
    
    with tab_marker:
        _render_filtered_messages("marker_genes")

def _render_overview_tab():
    """渲染概览标签页"""
    if st.session_state.messages:
        st.info(f"💬 当前对话包含 {len(st.session_state.messages)} 条消息")
        
        # 统计不同类型的消息
        user_msgs = sum(1 for msg in st.session_state.messages if isinstance(msg, HumanMessage))
        ai_msgs = sum(1 for msg in st.session_state.messages if isinstance(msg, AIMessage))
        tool_msgs = sum(1 for msg in st.session_state.messages if isinstance(msg, ToolMessage))
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("用户消息", user_msgs, help="您发送的消息数量")
        with col2:
            st.metric("AI回复", ai_msgs, help="AI助手的回复数量")
        with col3:
            st.metric("工具执行", tool_msgs, help="执行的工具数量")
        
        # 显示最近的图片
        recent_images = []
        for msg in reversed(st.session_state.messages):
            if isinstance(msg, ToolMessage):
                content = msg.content
                if isinstance(content, str):
                    clean_content, artifacts = extract_artifacts_from_content(content)
                    if artifacts:
                        recent_images.extend(artifacts)
                        if len(recent_images) >= 4:  # 最多显示4张图片
                            break
        
        if recent_images:
            st.write("**最近生成的图表：**")
            cols = st.columns(2)
            for i, rel_path in enumerate(recent_images[:4]):
                if rel_path.endswith(".png"):
                    abs_path = os.path.join(
                        os.path.dirname(os.path.dirname(__file__)),
                        "3_backend_mcp",
                        rel_path
                    )
                    if os.path.exists(abs_path):
                        with cols[i % 2]:
                            st.image(abs_path, caption=os.path.basename(rel_path), width=200)
    else:
        st.info("🚀 开始您的分析之旅！使用侧边栏的快速操作或在下方输入问题。")

def _render_filtered_messages(filter_type: str):
    """渲染过滤后的消息"""
    filtered_messages = []
    
    for msg in st.session_state.messages:
        if isinstance(msg, ToolMessage):
            tool_name = getattr(msg, 'name', '').lower()
            if filter_type in tool_name:
                filtered_messages.append(msg)
    
    if filtered_messages:
        for i, msg in enumerate(filtered_messages):
            display_message(msg, i)
    else:
        st.info(f"暂无 {filter_type} 相关的结果。请先执行相应的分析步骤。")

# ========= 业务逻辑函数 =========

# 构建 ToolMessage 辅助函数


def build_tool_message(tool_name: str, result: Dict[str, Any]) -> ToolMessage:
    """根据MCP返回结果构造包含随机tool_call_id的ToolMessage"""
    return ToolMessage(
        content=result.get("content", ""),
        tool_call_id=str(uuid4()),
        name=tool_name,
        artifact=result.get("artifact", [])
    )

# MCP工具调用函数


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


def call_mcp_tool_sync(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """同步调用MCP工具 - 使用正确的SSE客户端连接方式"""
    try:
        logger.info(f"[MCP调用] 工具: {tool_name}, 参数: {arguments}")
        result = asyncio.run(call_mcp_tool(tool_name, arguments))
        logger.info(f"[MCP返回] 工具: {tool_name}, 返回类型: {type(result)}")

        # 解析MCP结果
        parsed_result = parse_mcp_result(result)
        logger.info(f"[MCP解析] 工具: {tool_name}, 解析后: {parsed_result}")
        return parsed_result
    except Exception as e:
        logger.error(f"调用MCP工具失败: {e}")
        return {"error": f"连接MCP服务器失败: {str(e)}"}


async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """异步调用MCP工具"""
    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result


def check_mcp_server_health() -> bool:
    """检查MCP服务器健康状态"""
    try:
        result = call_mcp_tool_sync("health_check", {})
        # 检查解析后的结果
        return isinstance(result, dict) and not result.get("error") and result.get("status") == "healthy"
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return False


def get_llm_client(model_name: str = "gpt-4o"):
    """根据模型名称返回相应的LLM客户端"""
    if model_name.startswith("deepseek"):
        deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")

        base_url = "https://www.chataiapi.com/v1"

        return ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=SecretStr(deepseek_api_key),
            base_url=base_url
        )
    else:
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        return ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=SecretStr(openai_api_key)
        )


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

    indicator_count = sum(
        1 for indicator in python_indicators if indicator in text)
    return indicator_count >= 2


def extract_artifacts_from_content(content: str) -> tuple[str, list]:
    """从内容中提取图片路径信息"""
    import re

    # 查找[ARTIFACTS]标记
    pattern = r'\[ARTIFACTS\](.*?)\[/ARTIFACTS\]'
    match = re.search(pattern, content)

    if match:
        try:
            artifacts_json = match.group(1)
            artifacts = json.loads(artifacts_json)
            # 移除标记，返回清洁的内容
            clean_content = re.sub(pattern, '', content).strip()
            return clean_content, artifacts
        except json.JSONDecodeError:
            return content, []

    return content, []


def display_message(message: BaseMessage, index: int):
    """显示单条消息 - 美化版本，不同类型消息使用不同颜色"""
    # 获取用户设置的图片宽度，默认为700
    img_width = getattr(st.session_state, 'image_width', 700)

    with st.container():
        if isinstance(message, HumanMessage):
            st.markdown('<div class="chat-message user-message">',
                        unsafe_allow_html=True)
            st.markdown('<p class="message-label user-label">👤 用户:</p>', unsafe_allow_html=True)
            
            # 正确处理HumanMessage的内容
            if isinstance(message.content, str):
                st.write(message.content)
            elif isinstance(message.content, list):
                # 处理包含文本和图片的列表内容
                for item in message.content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            st.write(item["text"])
                        elif item.get("type") == "image_url":
                            if "image_url" in item and "url" in item["image_url"]:
                                st.image(item["image_url"]["url"], caption="用户上传的图片")
                    elif isinstance(item, str):
                        st.write(item)
            else:
                # 如果内容是其他类型，直接显示
                st.write(str(message.content))
            
            st.markdown('</div>', unsafe_allow_html=True)

        elif isinstance(message, AIMessage):
            # 判断是否有工具调用
            has_tool_calls = hasattr(message, 'tool_calls') and message.tool_calls
            
            # 根据是否有工具调用选择不同的CSS类
            if has_tool_calls:
                st.markdown('<div class="chat-message assistant-message-with-tools">',
                            unsafe_allow_html=True)
                st.markdown('<p class="message-label assistant-label-with-tools">🤖 助手 (准备调用工具):</p>', 
                           unsafe_allow_html=True)
            else:
                st.markdown('<div class="chat-message assistant-message">',
                            unsafe_allow_html=True)
                st.markdown('<p class="message-label assistant-label">🤖 助手:</p>', unsafe_allow_html=True)

            # 正确处理AIMessage的内容
            content = message.content
            if isinstance(content, str):
                # 解析内容中的图片路径信息
                clean_content, artifacts = extract_artifacts_from_content(content)
                
                if clean_content:
                    # 处理LaTeX格式
                    modified_content = clean_content.replace("\\(", "$").replace("\\)", "$")
                    modified_content = modified_content.replace("\\[", "$$").replace("\\]", "$$")
                    st.markdown(modified_content)
                
                # 显示图片（如果有）
                if artifacts:
                    st.write("**生成的图表:**")
                    for rel_path in artifacts:
                        if rel_path.endswith(".png"):
                            abs_path = os.path.join(
                                os.path.dirname(os.path.dirname(__file__)),
                                "3_backend_mcp",
                                rel_path
                            )
                            if os.path.exists(abs_path):
                                st.image(
                                    abs_path,
                                    caption=f"生成的图表: {os.path.basename(rel_path)}",
                                    width=img_width
                                )
                            else:
                                st.error(f"图片文件未找到: {rel_path}")
                                
            elif isinstance(content, list):
                # 处理列表内容
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text" and "text" in item:
                            modified_text = item["text"].replace("\\(", "$").replace("\\)", "$")
                            modified_text = modified_text.replace("\\[", "$$").replace("\\]", "$$")
                            st.markdown(modified_text)
                        elif "url" in item:
                            st.image(item["url"], caption="助手生成的图片")
                    elif isinstance(item, str):
                        modified_content = item.replace("\\(", "$").replace("\\)", "$")
                        modified_content = modified_content.replace("\\[", "$$").replace("\\]", "$$")
                        st.markdown(modified_content)
            else:
                # 处理其他类型的内容
                st.write(str(content))

            # 检查是否有工具调用请求
            if has_tool_calls:
                st.markdown("**🔧 工具调用请求:**")
                for i, tool_call in enumerate(message.tool_calls):
                    # 检查是否是Python REPL工具，确保需要用户确认
                    if "python_repl_tool" in tool_call.get("name", ""):
                        # 确保工具调用有requires_confirmation标记
                        tool_call["requires_confirmation"] = True
                    render_tool_call_pending(tool_call, index, i)

            st.markdown('</div>', unsafe_allow_html=True)

        elif isinstance(message, ToolMessage):
            st.markdown('<div class="chat-message tool-message">',
                        unsafe_allow_html=True)
            tool_name = getattr(message, 'name', 'Unknown Tool')
            st.markdown(f'<p class="message-label tool-label">🔧 工具: {tool_name}</p>', unsafe_allow_html=True)

            content = message.content

            if isinstance(content, str):
                # 解析内容中的图片路径信息
                clean_content, artifacts = extract_artifacts_from_content(content)

                if is_python_code(clean_content):
                    st.markdown("**执行的代码:**")
                    st.code(clean_content, language="python")
                    
                    # 显示执行结果
                    st.markdown("**执行结果:**")
                    # 如果内容看起来像错误信息，用错误样式显示
                    if "Error:" in clean_content or "Exception:" in clean_content:
                        st.error(clean_content)
                    else:
                        st.text(clean_content)
                        
                else:
                    st.write(clean_content)

                # 显示工具返回的图片
                if artifacts:
                    st.write("**生成的图表:**")
                    for rel_path in artifacts:
                        if rel_path.endswith(".png"):
                            abs_path = os.path.join(
                                os.path.dirname(os.path.dirname(__file__)),
                                "3_backend_mcp",
                                rel_path
                            )
                            if os.path.exists(abs_path):
                                st.image(
                                    abs_path,
                                    caption=f"生成的图表: {os.path.basename(rel_path)}",
                                    width=img_width
                                )
                            else:
                                st.error(f"图片文件未找到: {rel_path}")
                                st.info(f"预期路径: {abs_path}")
            else:
                st.write(str(content))

            # 显示工具返回的图片（保留原有逻辑作为备用）
            tool_artifacts = getattr(message, 'artifact', [])
            if tool_artifacts:
                st.write("**生成的图表:**")
                for rel_path in tool_artifacts:
                    if rel_path.endswith(".png"):
                        abs_path = os.path.join(
                            os.path.dirname(os.path.dirname(__file__)),
                            "3_backend_mcp",
                            rel_path
                        )
                        if os.path.exists(abs_path):
                            st.image(
                                abs_path,
                                caption=f"生成的图表: {os.path.basename(rel_path)}",
                                width=img_width
                            )
                        else:
                            st.error(f"图片文件未找到: {rel_path}")

            st.markdown('</div>', unsafe_allow_html=True)


# 序列化和反序列化函数
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
    elif msg_type == "SystemMessage":
        return SystemMessage(content=content)
    else:
        # 默认返回HumanMessage
        return HumanMessage(content=content)

# 初始化session state
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "run_counter" not in st.session_state:
    st.session_state.run_counter = 0
if "pending_tool_calls" not in st.session_state:
    st.session_state.pending_tool_calls = {}
if "image_width" not in st.session_state:
    st.session_state.image_width = 700


def get_available_models():
    """根据API密钥自动检测可用模型"""
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


# 如果前面没有定义 call_agent_core_sync / check_agent_core_health，则补充定义
if 'call_agent_core_sync' not in globals():
    def call_agent_core_sync(message: str, conversation_id: str = None) -> Dict[str, Any]:
        """调用Agent Core处理消息，支持对话记忆"""
        try:
            payload = {"message": message}
            if conversation_id:
                payload["conversation_id"] = conversation_id
                
            resp = requests.post(AGENT_CORE_CHAT_URL, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"调用 Agent Core 失败: {e}")
            return {"success": False, "error": str(e)}

if 'check_agent_core_health' not in globals():
    def check_agent_core_health() -> bool:
        try:
            resp = requests.get("http://localhost:8002/health", timeout=10)
            return resp.status_code == 200 and resp.json().get("status") == "healthy"
        except Exception:
            return False

def get_conversations() -> List[Dict[str, Any]]:
    """获取所有对话列表"""
    try:
        resp = requests.get(AGENT_CORE_CONVERSATIONS_URL, timeout=10)
        resp.raise_for_status()
        return resp.json().get("conversations", [])
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}")
        return []

def delete_conversation(conversation_id: str) -> bool:
    """删除对话"""
    try:
        resp = requests.delete(f"{AGENT_CORE_CONVERSATIONS_URL}/{conversation_id}", timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"删除对话失败: {e}")
        return False

def clear_conversation(conversation_id: str) -> bool:
    """清空对话"""
    try:
        resp = requests.post(f"{AGENT_CORE_CONVERSATIONS_URL}/{conversation_id}/clear", timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"清空对话失败: {e}")
        return False

# ========= 主程序入口 =========

def main():
    """主程序入口"""
    # 注入样式
    inject_global_style()
    
    # 构建页面头部
    build_header()
    
    # 构建侧边栏并获取配置
    selected_model, selected_model_name, server_online, agent_online = build_sidebar()
    
    # 构建主要内容区域
    build_main_content()
    
    # 聊天输入处理
    handle_chat_input(selected_model, selected_model_name, server_online, agent_online)
    
    # 页面底部信息
    build_footer()

def handle_chat_input(selected_model, selected_model_name, server_online, agent_online):
    """处理聊天输入"""
    if prompt := st.chat_input("请输入您的问题，比如'请分析PBMC3K数据的聚类结果'..."):
        # 添加用户消息
        st.session_state.messages.append(HumanMessage(content=prompt))

        # 简单的意图识别和MCP工具调用
        prompt_lower = prompt.lower()
        direct_mcp_call = False
        
        # 检查是否为直接MCP工具调用的简单问题
        if "加载" in prompt and ("数据" in prompt or "pbmc" in prompt_lower):
            _execute_mcp_tool("load_pbmc3k_data", "正在获取数据加载代码...")
            direct_mcp_call = True
        elif "质量控制" in prompt or "质控" in prompt:
            _execute_mcp_tool("quality_control_analysis", "正在获取质量控制分析代码...")
            direct_mcp_call = True
        elif "预处理" in prompt:
            _execute_mcp_tool("preprocessing_analysis", "正在获取数据预处理代码...")
            direct_mcp_call = True
        elif "降维" in prompt or "pca" in prompt_lower or "umap" in prompt_lower:
            _execute_mcp_tool("dimensionality_reduction_analysis", "正在获取降维分析代码...")
            direct_mcp_call = True
        elif "聚类" in prompt or "clustering" in prompt_lower:
            _execute_mcp_tool("clustering_analysis", "正在获取聚类分析代码...")
            direct_mcp_call = True
        elif "标记基因" in prompt or "marker" in prompt_lower:
            _execute_mcp_tool("marker_genes_analysis", "正在获取标记基因分析代码...")
            direct_mcp_call = True
        elif "报告" in prompt or "总结" in prompt:
            _execute_mcp_tool("generate_analysis_report", "正在生成分析报告...")
            direct_mcp_call = True

        # 如果不是直接MCP调用，则使用Agent Core处理（支持对话记忆）
        if not direct_mcp_call:
            if agent_online:
                with st.spinner("🤖 Agent正在思考您的问题..."):
                    result = call_agent_core_sync(prompt, st.session_state.conversation_id)
                    if result.get("success"):
                        # 更新conversation_id
                        st.session_state.conversation_id = result.get("conversation_id")

                        # 处理Agent Core返回的完整消息列表
                        returned_messages = result.get("messages", [])

                        if returned_messages:
                            # 智能处理Agent Core返回的消息，避免重复
                            current_messages = st.session_state.messages.copy()
                            
                            # 只添加Agent返回的新消息
                            for msg_data in returned_messages:
                                try:
                                    msg_obj = deserialize_message(msg_data)
                                    
                                    # 跳过用户消息，因为用户消息已经在前端添加了
                                    if isinstance(msg_obj, HumanMessage):
                                        continue
                                    
                                    # 检查是否为需要用户确认的工具调用消息
                                    if (isinstance(msg_obj, AIMessage) and 
                                        hasattr(msg_obj, 'tool_calls') and 
                                        msg_obj.tool_calls and
                                        any(tool.get('name', '').endswith('python_repl_tool') for tool in msg_obj.tool_calls)):
                                        
                                        # 标记需要用户确认的工具调用
                                        for tool_call in msg_obj.tool_calls:
                                            if tool_call.get('name', '').endswith('python_repl_tool'):
                                                tool_call['requires_confirmation'] = True
                                    
                                    # 智能去重：检查是否已经存在相同的消息
                                    is_duplicate = False
                                    for existing_msg in current_messages:
                                        if (isinstance(existing_msg, type(msg_obj)) and 
                                            getattr(existing_msg, 'content', '') == getattr(msg_obj, 'content', '')):
                                            
                                            # 对于AIMessage，还要检查tool_calls是否相同
                                            if isinstance(msg_obj, AIMessage) and hasattr(msg_obj, 'tool_calls'):
                                                if (hasattr(existing_msg, 'tool_calls') and 
                                                    existing_msg.tool_calls == msg_obj.tool_calls):
                                                    is_duplicate = True
                                                    break
                                            else:
                                                is_duplicate = True
                                                break
                                    
                                    # 只有非重复的消息才添加
                                    if not is_duplicate:
                                        current_messages.append(msg_obj)
                                        
                                except Exception as e:
                                    # 回退到纯文本
                                    logger.error(f"消息反序列化失败: {e}")
                                    current_messages.append(AIMessage(content=str(msg_data)))
                            
                            # 更新session state
                            st.session_state.messages = current_messages
                        else:
                            # 兼容旧版：仅有final_response
                            ai_message = AIMessage(content=result.get("final_response", ""))
                            st.session_state.messages.append(ai_message)
                    else:
                        error_msg = result.get("error", "未知错误")
                        st.session_state.messages.append(
                            AIMessage(content=f"Agent Core错误: {error_msg}"))
            else:
                st.session_state.messages.append(
                    AIMessage(content="⚠️ Agent Core未启动，无法处理该请求。"))

        st.rerun()

def render_tool_call_pending(tool_call, message_index: int, tool_index: int):
    """渲染待确认的工具调用 - 美化版本"""
    tool_name = tool_call.get("name", "unknown_tool")
    args = tool_call.get("args", {})
    tool_id = tool_call.get("id", f"tool_{message_index}_{tool_index}")
    requires_confirmation = tool_call.get("requires_confirmation", False)
    
    # 创建更唯一的键，包含工具调用的完整信息
    tool_signature = f"{tool_name}_{tool_id}_{hash(str(args))}"
    unique_key = f"tool_{message_index}_{tool_index}_{tool_signature}"
    
    # 检查是否已经执行过
    executed_key = f"executed_{unique_key}"
    
    # 检查是否已经执行过（通过session state或消息历史）
    is_executed = False
    if executed_key in st.session_state and st.session_state[executed_key]:
        is_executed = True
    else:
        # 检查消息历史中是否有对应的ToolMessage（排除占位符消息）
        for msg in st.session_state.messages:
            if (isinstance(msg, ToolMessage) and 
                getattr(msg, 'tool_call_id', '') == tool_id and
                getattr(msg, 'name', '') == tool_name):
                
                # 检查是否是占位符消息
                content = getattr(msg, 'content', '')
                if content == "[等待用户确认执行]":
                    # 这是占位符消息，不算作已执行
                    continue
                else:
                    # 这是真正的执行结果
                    is_executed = True
                    # 更新session state以保持一致性
                    st.session_state[executed_key] = True
                    break
    
    if is_executed:
        # 使用执行完成的样式，但仍然显示代码
        st.markdown('<div class="tool-executed">', unsafe_allow_html=True)
        st.markdown(f'<h4 style="color: #2e7d32; margin-bottom: 12px;">✅ 工具已执行: {tool_name}</h4>', 
                    unsafe_allow_html=True)
        
        # 显示执行的代码
        if args and "query" in args:
            st.markdown("**已执行的代码:**")
            st.code(args["query"], language="python")
        elif args:
            st.markdown("**执行参数:**")
            st.json(args)
        
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # 使用工具调用等待状态的样式
    st.markdown('<div class="tool-pending">', unsafe_allow_html=True)
    st.markdown(f'<h4 style="color: #7b1fa2; margin-bottom: 12px;">🔧 工具调用: {tool_name}</h4>', 
                unsafe_allow_html=True)
    
    # 显示参数
    if args:
        st.markdown("**参数:**")
        if "query" in args:
            st.markdown("**要执行的代码:**")
            st.code(args["query"], language="python")
        else:
            st.json(args)
    
    # 创建按钮列
    col1, col2, col3 = st.columns([1, 1, 4])
    
    # 使用更稳定的按钮键，基于工具调用的唯一标识
    run_key = f"run_{unique_key}"
    cancel_key = f"cancel_{unique_key}"
    
    # 对于python_repl_tool，必须要求用户确认
    is_python_repl = "python_repl_tool" in tool_name
    
    # 执行按钮
    if col1.button("▶️ 执行", key=run_key, help="执行此工具调用", 
                   type="primary", use_container_width=True):
        with st.spinner("🔄 正在执行工具..."):
            start_time = time.time()
            
            try:
                # 执行工具
                result = call_mcp_tool_sync(tool_name, args)
                exec_time = time.time() - start_time
                
                # 生成ToolMessage
                tool_msg = build_tool_message(tool_name, result)
                
                # 添加到消息列表
                st.session_state.messages.append(tool_msg)
                
                # 标记为已执行
                st.session_state[executed_key] = True
                
                # 显示执行结果
                st.success(f"✅ 工具执行完成 (耗时: {exec_time:.2f}s)")
                
                # 如果有错误，显示错误
                if isinstance(result, dict) and result.get("error"):
                    st.error(f"❌ 执行错误: {result['error']}")
                else:
                    result_preview = str(result.get('content', '无输出') if isinstance(result, dict) else result)[:100]
                    st.info(f"📤 执行结果: {result_preview}...")
                
                # 重新运行以刷新界面
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ 执行失败: {str(e)}")
                logger.error(f"工具执行失败: {e}")
    
    # 取消按钮
    if col2.button("❌ 取消", key=cancel_key, help="取消此工具调用", 
                   use_container_width=True):
        # 创建取消消息
        cancel_msg = ToolMessage(
            content="用户取消了工具执行",
            tool_call_id=tool_id,
            name=tool_name
        )
        st.session_state.messages.append(cancel_msg)
        st.session_state[executed_key] = True
        st.warning("⚠️ 工具调用已取消")
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def build_footer():
    """构建页面底部信息"""
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        conv_id = st.session_state.conversation_id
        conv_id_display = conv_id[:8] + "..." if conv_id else "未设置"
        st.caption(f"🆔 对话ID: {conv_id_display}")
    with col2:
        st.caption(f"💬 消息数: {len(st.session_state.messages)}")
    with col3:
        st.caption("🧬 RnAgent v2.1.0")

# 运行主程序
main()

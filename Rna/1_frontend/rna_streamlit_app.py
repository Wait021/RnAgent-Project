#!/usr/bin/env python3
"""
RnAgent 前端应用 - 基于STAgent_MCP的优化版本
直接调用MCP工具，简化架构
"""

import streamlit as st
import os
import sys
import asyncio
import json
import requests
import logging
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
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

# 加载环境变量
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="RnAgent - 单细胞RNA分析智能体",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 全局样式 =====
st.markdown(
    """
    <style>
    .status-indicator {display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;}
    .status-online{background:#4caf50;}
    .status-offline{background:#f44336;}

    .chat-message{padding:8px 12px;border-radius:6px;margin-bottom:10px;}
    .user-message{background:#e1f5fe;}
    .assistant-message{background:#f1f8e9;}
    .tool-message{background:#fff3e0;}
    </style>
    """,
    unsafe_allow_html=True
)

# 主标题
st.markdown('<h1 class="main-title">🧬 RnAgent - 单细胞RNA分析智能体</h1>', unsafe_allow_html=True)

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
            temperature=0
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
    
    indicator_count = sum(1 for indicator in python_indicators if indicator in text)
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
    """显示单条消息"""
    # 获取用户设置的图片宽度，默认为700
    img_width = getattr(st.session_state, 'image_width', 700)
    
    with st.container():
        if isinstance(message, HumanMessage):
            st.markdown('<div class="chat-message user-message">', unsafe_allow_html=True)
            st.markdown("**👤 用户:**")
            st.write(message.content)
            st.markdown('</div>', unsafe_allow_html=True)
            
        elif isinstance(message, AIMessage):
            st.markdown('<div class="chat-message assistant-message">', unsafe_allow_html=True)
            st.markdown("**🤖 助手:**")
            
            # 解析内容中的图片路径信息
            content_str = str(message.content) if message.content else ""
            clean_content, artifacts = extract_artifacts_from_content(content_str)
            st.write(clean_content)
            
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
                                width=img_width  # 使用用户设置的宽度
                            )
                        else:
                            st.error(f"图片文件未找到: {rel_path}")
                            st.info(f"预期路径: {abs_path}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
        elif isinstance(message, ToolMessage):
            st.markdown('<div class="chat-message tool-message">', unsafe_allow_html=True)
            tool_name = getattr(message, 'name', 'Unknown Tool')
            st.markdown(f"**🔧 工具: {tool_name}**")
            
            content = message.content
            
            if isinstance(content, str):
                # 解析内容中的图片路径信息
                clean_content, artifacts = extract_artifacts_from_content(content)
                
                if is_python_code(clean_content):
                    st.code(clean_content, language="python")
                    
                    # 添加运行按钮
                    run_key = f"run_{tool_name}_{index}_{hash(clean_content)}"
                    if st.button("▶️ 运行代码", key=run_key):
                        with st.spinner("正在执行代码..."):
                            result = call_mcp_tool_sync("python_repl_tool", {"query": clean_content})
                            
                            if isinstance(result, dict):
                                st.write("**执行结果:**")
                                st.write(result.get("content", ""))
                                
                                # 显示生成的图片
                                exec_artifacts = result.get("artifact", [])
                                if exec_artifacts:
                                    st.write("**生成的图表:**")
                                    for img_path in exec_artifacts:
                                        abs_path = os.path.join(
                                            os.path.dirname(os.path.dirname(__file__)), 
                                            "3_backend_mcp", 
                                            img_path
                                        )
                                        if os.path.exists(abs_path):
                                            st.image(
                                                abs_path, 
                                                caption=f"生成的图表: {os.path.basename(img_path)}", 
                                                width=img_width  # 使用用户设置的宽度
                                            )
                                        else:
                                            st.error(f"图片文件未找到: {img_path}")
                            else:
                                st.write("**执行结果:**")
                                st.write(str(result))
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
                                    width=img_width  # 使用用户设置的宽度
                                )
                            else:
                                st.error(f"图片文件未找到: {rel_path}")
                                st.info(f"预期路径: {abs_path}")
            else:
                st.write(content)
            
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
                                width=img_width  # 使用用户设置的宽度
                            )
                        else:
                            st.error(f"图片文件未找到: {rel_path}")
            
            st.markdown('</div>', unsafe_allow_html=True)

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

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
    def call_agent_core_sync(message: str) -> Dict[str, Any]:
        try:
            resp = requests.post(AGENT_CORE_CHAT_URL, json={"message": message}, timeout=120)
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
    
    # 模型选择
    st.subheader("🤖 模型选择")
    
    if available_models:
        # 自动选择最佳默认模型
        model_keys = list(available_models.keys())
        
        # 优先级：OpenAI GPT-4o > OpenAI GPT-4 Turbo > DeepSeek Chat
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
        
        # 显示选择的模型信息
        if selected_model.startswith("gpt"):
            st.info("🔸 使用OpenAI模型，需要稳定的网络连接")
        elif selected_model.startswith("deepseek"):
            st.info("🔸 使用DeepSeek模型，经济实惠的选择")
            
    else:
        # 没有可用的API密钥
        st.error("❌ 未检测到可用的API密钥")
        st.markdown("""
        **请设置以下环境变量之一：**
        
        ```bash
        # OpenAI API
        export OPENAI_API_KEY="your_key"
        
        # DeepSeek API
        export DEEPSEEK_API_KEY="your_key"
        ```
        
        设置后请重启应用。
        """)
        
        # 提供一个默认选择以避免错误
        selected_model = "gpt-4o"
        selected_model_name = "OpenAI GPT-4o (未配置)"
    
    # 服务状态
    st.subheader("🖥️ 服务状态")
    
    # 检查MCP服务器状态
    if check_mcp_server_health():
        st.markdown('<span class="status-indicator status-online"></span>MCP服务器: 在线', unsafe_allow_html=True)
        server_online = True
    else:
        st.markdown('<span class="status-indicator status-offline"></span>MCP服务器: 离线', unsafe_allow_html=True)
        server_online = False
        st.warning("⚠️ MCP服务器离线，请确保后端服务器正在运行")

    # 检查Agent Core状态
    if check_agent_core_health():
        st.markdown('<span class="status-indicator status-online"></span>Agent Core: 在线', unsafe_allow_html=True)
        agent_online = True
    else:
        st.markdown('<span class="status-indicator status-offline"></span>Agent Core: 离线', unsafe_allow_html=True)
        agent_online = False
        st.warning("⚠️ Agent Core离线，聊天功能将不可用")
    
    # 显示设置
    st.subheader("🖼️ 显示设置")
    
    # 图片显示大小设置
    image_width = st.slider(
        "图表显示宽度 (像素)",
        min_value=400,
        max_value=1200,
        value=700,
        step=50,
        help="调整生成图表的显示宽度，让图片大小更符合您的喜好"
    )
    
    # 将图片宽度保存到session state
    st.session_state.image_width = image_width
    
    # 快速操作
    st.subheader("🚀 快速操作")
    
    if not server_online:
        st.error("❌ MCP服务器离线，无法使用快速操作功能")
        st.info("💡 请运行 `python run_rna_demo.py` 启动后端服务器")
    else:
        # MCP工具按钮
        if st.button("📊 加载PBMC3K数据", use_container_width=True):
            with st.spinner("正在获取数据加载代码..."):
                result = call_mcp_tool_sync("load_pbmc3k_data", {})
                if isinstance(result, dict) and "content" in result:
                    tool_message = build_tool_message("load_pbmc3k_data", result)
                    st.session_state.messages.append(tool_message)
                    st.rerun()
        
        if st.button("🔍 质量控制分析", use_container_width=True):
            with st.spinner("正在获取质量控制代码..."):
                result = call_mcp_tool_sync("quality_control_analysis", {})
                if isinstance(result, dict) and "content" in result:
                    tool_message = build_tool_message("quality_control_analysis", result)
                    st.session_state.messages.append(tool_message)
                    st.rerun()
        
        if st.button("⚙️ 数据预处理", use_container_width=True):
            with st.spinner("正在获取预处理代码..."):
                result = call_mcp_tool_sync("preprocessing_analysis", {})
                if isinstance(result, dict) and "content" in result:
                    tool_message = build_tool_message("preprocessing_analysis", result)
                    st.session_state.messages.append(tool_message)
                    st.rerun()
        
        if st.button("📈 降维分析", use_container_width=True):
            with st.spinner("正在获取降维分析代码..."):
                result = call_mcp_tool_sync("dimensionality_reduction_analysis", {})
                if isinstance(result, dict) and "content" in result:
                    tool_message = build_tool_message("dimensionality_reduction_analysis", result)
                    st.session_state.messages.append(tool_message)
                    st.rerun()
        
        if st.button("🎯 聚类分析", use_container_width=True):
            with st.spinner("正在获取聚类分析代码..."):
                result = call_mcp_tool_sync("clustering_analysis", {})
                if isinstance(result, dict) and "content" in result:
                    tool_message = build_tool_message("clustering_analysis", result)
                    st.session_state.messages.append(tool_message)
                    st.rerun()
        
        if st.button("🧬 标记基因分析", use_container_width=True):
            with st.spinner("正在获取标记基因分析代码..."):
                result = call_mcp_tool_sync("marker_genes_analysis", {})
                if isinstance(result, dict) and "content" in result:
                    tool_message = build_tool_message("marker_genes_analysis", result)
                    st.session_state.messages.append(tool_message)
                    st.rerun()
        
        if st.button("📋 生成分析报告", use_container_width=True):
            with st.spinner("正在生成分析报告..."):
                result = call_mcp_tool_sync("generate_analysis_report", {})
                if isinstance(result, dict) and "content" in result:
                    tool_message = build_tool_message("generate_analysis_report", result)
                    st.session_state.messages.append(tool_message)
                    st.rerun()
        
        st.divider()
        
        if st.button("🚀 完整分析流程", use_container_width=True, type="primary"):
            # 依次执行所有分析步骤
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
    
    if st.button("🔄 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    # 数据集信息
    st.subheader("📁 数据集信息")
    st.info("""
    **PBMC3K数据集**
    - 细胞类型: 外周血单核细胞
    - 平台: 10X Genomics
    - 路径: `/Volumes/T7/哈尔滨工业大学-2025/课题组项目/Agent-项目/PBMC3kRNA-seq/filtered_gene_bc_matrices/hg19/`
    """)

# 主要内容区域
chat_container = st.container()

with chat_container:
    # 显示欢迎信息
    if not st.session_state.messages:
        # 获取当前可用模型信息用于欢迎信息
        current_models, current_openai, current_deepseek = get_available_models()
        
        welcome_msg = """
        ### 👋 欢迎使用RnAgent！
        
        我是您的单细胞RNA分析助手。您可以：
        
        1. **使用侧边栏快速操作**：点击按钮执行预定义的分析步骤
        2. **在下方输入自然语言问题**：我会为您生成相应的分析代码  
        3. **运行代码并查看结果**：生成的图表会自动显示
        
        **推荐开始方式**：
        - 点击侧边栏的"🚀 完整分析流程"按钮进行端到端分析
        - 或者逐步点击各个分析步骤
        - 也可以直接在下方提问，如"请加载PBMC3K数据并显示基本信息"
        
        """
        
        # 根据API密钥状态添加相应信息
        if current_models:
            available_model_names = list(current_models.keys())
            welcome_msg += f"""
        **🤖 AI模型状态**：
        - ✅ 已自动检测并配置可用模型：{', '.join(available_model_names)}
        - 🎯 当前选择：已自动为您选择最佳模型
        """
        else:
            welcome_msg += """
        **⚠️ AI模型状态**：
        - ❌ 未检测到API密钥，自然语言对话功能不可用
        - 💡 您仍可使用所有快速操作按钮进行分析
        - 🔧 请在侧边栏查看API配置说明
        """
        
        st.markdown(welcome_msg)
    
    # 显示对话历史
    for i, message in enumerate(st.session_state.messages):
        display_message(message, i)

# 聊天输入
if prompt := st.chat_input("请输入您的问题，比如'请分析PBMC3K数据的聚类结果'..."):
    # 添加用户消息
    st.session_state.messages.append(HumanMessage(content=prompt))
    
    # 重新获取可用模型信息（确保在聊天输入部分也能访问）
    available_models, _, _ = get_available_models()
    
    # 简单的意图识别和MCP工具调用
    prompt_lower = prompt.lower()
    
    if "加载" in prompt and ("数据" in prompt or "pbmc" in prompt_lower):
        with st.spinner("正在获取数据加载代码..."):
            result = call_mcp_tool_sync("load_pbmc3k_data", {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message("load_pbmc3k_data", result)
                st.session_state.messages.append(tool_message)
    
    elif "质量控制" in prompt or "质控" in prompt:
        with st.spinner("正在获取质量控制分析代码..."):
            result = call_mcp_tool_sync("quality_control_analysis", {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message("quality_control_analysis", result)
                st.session_state.messages.append(tool_message)
    
    elif "预处理" in prompt:
        with st.spinner("正在获取数据预处理代码..."):
            result = call_mcp_tool_sync("preprocessing_analysis", {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message("preprocessing_analysis", result)
                st.session_state.messages.append(tool_message)
    
    elif "降维" in prompt or "pca" in prompt_lower or "umap" in prompt_lower:
        with st.spinner("正在获取降维分析代码..."):
            result = call_mcp_tool_sync("dimensionality_reduction_analysis", {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message("dimensionality_reduction_analysis", result)
                st.session_state.messages.append(tool_message)
    
    elif "聚类" in prompt or "clustering" in prompt_lower:
        with st.spinner("正在获取聚类分析代码..."):
            result = call_mcp_tool_sync("clustering_analysis", {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message("clustering_analysis", result)
                st.session_state.messages.append(tool_message)
    
    elif "标记基因" in prompt or "marker" in prompt_lower:
        with st.spinner("正在获取标记基因分析代码..."):
            result = call_mcp_tool_sync("marker_genes_analysis", {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message("marker_genes_analysis", result)
                st.session_state.messages.append(tool_message)
    
    elif "报告" in prompt or "总结" in prompt:
        with st.spinner("正在生成分析报告..."):
            result = call_mcp_tool_sync("generate_analysis_report", {})
            if isinstance(result, dict) and "content" in result:
                tool_message = build_tool_message("generate_analysis_report", result)
                st.session_state.messages.append(tool_message)
    
    else:
        # 对于其他问题，转交Agent Core处理
        if agent_online:
            with st.spinner("Agent Core处理中..."):
                result = call_agent_core_sync(prompt)
                if result.get("success"):
                    ai_message = AIMessage(content=result.get("final_response", ""))
                    st.session_state.messages.append(ai_message)
                else:
                    error_msg = result.get("error", "未知错误")
                    st.session_state.messages.append(AIMessage(content=f"Agent Core错误: {error_msg}"))
        else:
            st.session_state.messages.append(AIMessage(content="⚠️ Agent Core未启动，无法处理该请求。"))
    
    st.rerun() 
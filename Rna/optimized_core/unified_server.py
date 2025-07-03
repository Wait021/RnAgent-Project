#!/usr/bin/env python3
"""
RNA项目优化版本 - 统一服务器
整合前端、Agent核心和MCP后端功能，减少网络调用开销
"""

import os
import sys
import time
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# FastAPI和依赖
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

# 导入优化的核心组件
from config import get_config, validate_config
from cache_manager import get_cache_manager
from execution_manager import get_execution_manager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('unified_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "gpt-4o"

class ChatResponse(BaseModel):
    success: bool
    response: str = ""
    plots: List[str] = []
    execution_time: float = 0.0
    error: str = ""

class UnifiedRNAServer:
    """统一RNA分析服务器"""
    
    def __init__(self):
        self.config = get_config()
        self.cache_manager = get_cache_manager()
        self.execution_manager = get_execution_manager()
        self.app = FastAPI(
            title="RNA分析统一服务器",
            description="整合前端、Agent核心和MCP后端的优化版本",
            version="2.0.0"
        )
        self._setup_middleware()
        self._setup_routes()
        self._connected_clients = set()
        
        logger.info("🚀 RNA分析统一服务器初始化完成")
    
    def _setup_middleware(self):
        """设置中间件"""
        # CORS中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 请求日志中间件
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            
            logger.info(f"📥 [请求] {request.method} {request.url.path}")
            
            response = await call_next(request)
            
            process_time = time.time() - start_time
            logger.info(f"📤 [响应] {response.status_code} - {process_time:.2f}s")
            
            return response
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.get("/")
        async def root():
            """主页"""
            return HTMLResponse(self._get_frontend_html())
        
        @self.app.get("/health")
        async def health_check():
            """健康检查"""
            stats = {
                "server": "RNA分析统一服务器",
                "version": "2.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "config_valid": validate_config(),
                "api_keys": list(self.config.api_keys.keys()),
                "cache_stats": self.cache_manager.get_stats(),
                "execution_stats": self.execution_manager.get_stats()
            }
            
            logger.info(f"🏥 [健康检查] 返回系统状态")
            return stats
        
        @self.app.post("/api/chat", response_model=ChatResponse)
        async def chat_endpoint(request: ChatRequest):
            """聊天接口"""
            start_time = time.time()
            
            try:
                logger.info(f"💬 [聊天] 收到消息: {request.message[:100]}...")
                
                # 分析用户意图并执行相应操作
                response_data = await self._process_chat_message(request.message, request.model)
                
                execution_time = time.time() - start_time
                response_data["execution_time"] = execution_time
                
                logger.info(f"✅ [聊天] 处理完成 - {execution_time:.2f}s")
                
                # 通过WebSocket推送更新
                await self._broadcast_update({
                    "type": "chat_response",
                    "data": response_data
                })
                
                return ChatResponse(**response_data)
                
            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e)
                
                logger.error(f"❌ [聊天] 处理失败: {error_msg}")
                
                return ChatResponse(
                    success=False,
                    error=error_msg,
                    execution_time=execution_time
                )
        
        @self.app.get("/api/tools")
        async def list_tools():
            """获取可用工具列表"""
            tools = [
                {
                    "name": "load_pbmc3k_data",
                    "description": "加载PBMC3K数据集",
                    "category": "data"
                },
                {
                    "name": "quality_control_analysis", 
                    "description": "质量控制分析",
                    "category": "analysis"
                },
                {
                    "name": "preprocessing_analysis",
                    "description": "数据预处理", 
                    "category": "analysis"
                },
                {
                    "name": "dimensionality_reduction_analysis",
                    "description": "降维分析",
                    "category": "analysis"
                },
                {
                    "name": "clustering_analysis",
                    "description": "聚类分析",
                    "category": "analysis"
                },
                {
                    "name": "marker_genes_analysis",
                    "description": "标记基因分析",
                    "category": "analysis"
                },
                {
                    "name": "generate_analysis_report",
                    "description": "生成分析报告",
                    "category": "report"
                }
            ]
            
            return {"tools": tools}
        
        @self.app.post("/api/execute")
        async def execute_code(request: dict):
            """执行代码接口"""
            try:
                code = request.get("code", "")
                if not code:
                    raise HTTPException(status_code=400, detail="代码不能为空")
                
                logger.info(f"🐍 [代码执行] 执行自定义代码")
                
                result = self.execution_manager.execute_code(code)
                
                return {
                    "success": result["success"],
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "plots": result["plots"],
                    "execution_time": result["execution_time"],
                    "error": result.get("error")
                }
                
            except Exception as e:
                logger.error(f"❌ [代码执行] 失败: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stats")
        async def get_system_stats():
            """获取系统统计信息"""
            return {
                "cache_stats": self.cache_manager.get_stats(),
                "execution_stats": self.execution_manager.get_stats(),
                "server_stats": {
                    "connected_clients": len(self._connected_clients),
                    "uptime": time.time() - self._start_time if hasattr(self, '_start_time') else 0
                }
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket连接"""
            await websocket.accept()
            self._connected_clients.add(websocket)
            
            logger.info(f"🔌 [WebSocket] 新客户端连接, 总连接: {len(self._connected_clients)}")
            
            try:
                while True:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # 处理WebSocket消息
                    await self._handle_websocket_message(websocket, message)
                    
            except WebSocketDisconnect:
                self._connected_clients.discard(websocket)
                logger.info(f"🔌 [WebSocket] 客户端断开连接, 剩余连接: {len(self._connected_clients)}")
        
        # 静态文件服务
        plots_dir = Path("tmp/plots")
        plots_dir.mkdir(parents=True, exist_ok=True)
        self.app.mount("/plots", StaticFiles(directory=str(plots_dir)), name="plots")
    
    async def _process_chat_message(self, message: str, model: str) -> Dict[str, Any]:
        """处理聊天消息"""
        # 简化的意图识别
        message_lower = message.lower()
        
        # 根据关键词识别意图并执行相应操作
        if "加载" in message_lower or "load" in message_lower:
            return await self._execute_analysis_step("load_data")
        elif "质量控制" in message_lower or "quality" in message_lower:
            return await self._execute_analysis_step("quality_control")
        elif "预处理" in message_lower or "preprocess" in message_lower:
            return await self._execute_analysis_step("preprocessing")
        elif "降维" in message_lower or "dimension" in message_lower or "pca" in message_lower or "umap" in message_lower:
            return await self._execute_analysis_step("dimensionality_reduction")
        elif "聚类" in message_lower or "cluster" in message_lower:
            return await self._execute_analysis_step("clustering")
        elif "标记基因" in message_lower or "marker" in message_lower:
            return await self._execute_analysis_step("marker_genes")
        elif "报告" in message_lower or "report" in message_lower:
            return await self._execute_analysis_step("generate_report")
        elif "完整分析" in message_lower or "全部" in message_lower:
            return await self._execute_full_analysis()
        else:
            # 默认返回帮助信息
            return {
                "success": True,
                "response": """
🧬 RNA分析助手为您服务！

可用的分析步骤：
📊 数据加载：'请加载PBMC3K数据'
🔍 质量控制：'进行质量控制分析'
⚙️ 数据预处理：'执行数据预处理'
📈 降维分析：'进行PCA和UMAP降维'  
🎯 聚类分析：'执行Leiden聚类'
🧬 标记基因：'分析各聚类的标记基因'
📋 生成报告：'生成完整分析报告'

💡 试试说："请进行完整的PBMC3K分析"
""",
                "plots": []
            }
    
    async def _execute_analysis_step(self, step_name: str) -> Dict[str, Any]:
        """执行分析步骤"""
        # 预定义的分析代码
        analysis_codes = {
            "load_data": f"""
# 加载PBMC3K数据集
import scanpy as sc
data_path = "{self.config.get_data_path()}"
print(f"正在加载数据: {{data_path}}")
adata = sc.read_10x_mtx(data_path, var_names='gene_symbols', cache=True)
adata.var_names_make_unique()
print(f"数据加载完成: {{adata.shape}}")
""",
            
            "quality_control": """
# 质量控制分析
print("开始质量控制分析...")
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
axes[0].hist(adata.obs['n_genes_by_counts'], bins=50, alpha=0.7, color='blue')
axes[0].set_xlabel('Number of genes')
axes[0].set_ylabel('Number of cells')
axes[0].set_title('Genes per cell')

axes[1].hist(adata.obs['total_counts'], bins=50, alpha=0.7, color='green')
axes[1].set_xlabel('Total counts')  
axes[1].set_ylabel('Number of cells')
axes[1].set_title('UMI counts per cell')

axes[2].hist(adata.obs['pct_counts_mt'], bins=50, alpha=0.7, color='red')
axes[2].set_xlabel('Mitochondrial gene %')
axes[2].set_ylabel('Number of cells')
axes[2].set_title('Mitochondrial gene %')

plt.tight_layout()
print("✅ 质量控制分析完成!")
""",
            
            "preprocessing": """
# 数据预处理
print("开始数据预处理...")
print(f"过滤前 - 细胞: {adata.n_obs}, 基因: {adata.n_vars}")

sc.pp.filter_genes(adata, min_cells=3)
sc.pp.filter_cells(adata, min_genes=200)
adata = adata[adata.obs.n_genes_by_counts < 5000, :]
adata = adata[adata.obs.pct_counts_mt < 20, :]

print(f"过滤后 - 细胞: {adata.n_obs}, 基因: {adata.n_vars}")

adata.raw = adata
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)

fig, ax = plt.subplots(figsize=(10, 6))
sc.pl.highly_variable_genes(adata, ax=ax, show=False)
plt.title('Highly Variable Genes')
print("✅ 数据预处理完成!")
""",
            
            "dimensionality_reduction": """
# 降维分析
print("开始降维分析...")
adata.raw = adata
adata = adata[:, adata.var.highly_variable]

sc.tl.pca(adata, svd_solver='arpack')
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=40)
sc.tl.umap(adata)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
sc.pl.pca_variance_ratio(adata, log=True, n_top_genes=50, ax=axes[0], show=False)
axes[0].set_title('PCA Variance Ratio')

sc.pl.umap(adata, ax=axes[1], show=False)
axes[1].set_title('UMAP')
plt.tight_layout()
print("✅ 降维分析完成!")
""",
            
            "clustering": """
# 聚类分析
print("开始聚类分析...")
sc.tl.leiden(adata, resolution=0.5)

fig, axes = plt.subplots(2, 2, figsize=(12, 10))
sc.pl.umap(adata, color='leiden', ax=axes[0,0], show=False)
axes[0,0].set_title('Leiden Clustering')

sc.pl.umap(adata, color='total_counts', ax=axes[0,1], show=False)
axes[0,1].set_title('Total Counts')

sc.pl.umap(adata, color='n_genes_by_counts', ax=axes[1,0], show=False)
axes[1,0].set_title('Number of Genes')

sc.pl.umap(adata, color='pct_counts_mt', ax=axes[1,1], show=False)
axes[1,1].set_title('Mitochondrial Gene %')

plt.tight_layout()

cluster_counts = adata.obs['leiden'].value_counts().sort_index()
print(f"识别出 {len(cluster_counts)} 个聚类")
print("✅ 聚类分析完成!")
"""
        }
        
        if step_name not in analysis_codes:
            return {
                "success": False,
                "response": f"未知的分析步骤: {step_name}",
                "plots": []
            }
        
        # 执行代码
        result = self.execution_manager.execute_code(analysis_codes[step_name])
        
        return {
            "success": result["success"],
            "response": result["stdout"] if result["success"] else result["error"],
            "plots": result["plots"]
        }
    
    async def _execute_full_analysis(self) -> Dict[str, Any]:
        """执行完整分析流程"""
        steps = ["load_data", "quality_control", "preprocessing", "dimensionality_reduction", "clustering"]
        all_plots = []
        all_output = []
        
        for step in steps:
            logger.info(f"📊 [完整分析] 执行步骤: {step}")
            result = await self._execute_analysis_step(step)
            
            if not result["success"]:
                return {
                    "success": False,
                    "response": f"在步骤 {step} 中失败: {result['response']}",
                    "plots": all_plots
                }
            
            all_plots.extend(result["plots"])
            all_output.append(f"--- {step} ---")
            all_output.append(result["response"])
        
        return {
            "success": True,
            "response": "🎉 完整分析流程执行完成！\n\n" + "\n".join(all_output),
            "plots": all_plots
        }
    
    async def _handle_websocket_message(self, websocket: WebSocket, message: dict):
        """处理WebSocket消息"""
        msg_type = message.get("type")
        
        if msg_type == "ping":
            await websocket.send_text(json.dumps({"type": "pong"}))
        elif msg_type == "get_stats":
            stats = await self.get_system_stats()
            await websocket.send_text(json.dumps({
                "type": "stats",
                "data": stats
            }))
    
    async def _broadcast_update(self, update: dict):
        """向所有连接的客户端广播更新"""
        if not self._connected_clients:
            return
        
        message = json.dumps(update)
        disconnected = []
        
        for client in self._connected_clients:
            try:
                await client.send_text(message)
            except:
                disconnected.append(client)
        
        # 清理断开的连接
        for client in disconnected:
            self._connected_clients.discard(client)
    
    def _get_frontend_html(self) -> str:
        """生成前端HTML页面"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RNA分析统一平台</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .chat-container { height: 400px; border: 1px solid #ddd; border-radius: 8px; overflow-y: auto; padding: 15px; margin-bottom: 20px; background: #fafafa; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        .input-group input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        .btn { padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
        .btn:hover { background: #0056b3; }
        .plots { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
        .plot img { width: 100%; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 20px; }
        .stat-card { padding: 15px; background: #f8f9fa; border-radius: 6px; border-left: 4px solid #007bff; }
        .message { margin-bottom: 15px; padding: 10px; border-radius: 6px; }
        .user-message { background: #e3f2fd; margin-left: 20%; }
        .bot-message { background: #f1f8e9; margin-right: 20%; }
        .quick-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 20px; }
        .quick-btn { padding: 10px; background: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }
        .quick-btn:hover { background: #1e7e34; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧬 RNA分析统一平台</h1>
            <p>基于优化架构的单细胞RNA分析系统</p>
        </div>
        
        <div class="quick-actions">
            <button class="quick-btn" onclick="sendMessage('请加载PBMC3K数据')">📊 加载数据</button>
            <button class="quick-btn" onclick="sendMessage('进行质量控制分析')">🔍 质量控制</button>
            <button class="quick-btn" onclick="sendMessage('执行数据预处理')">⚙️ 预处理</button>
            <button class="quick-btn" onclick="sendMessage('进行降维分析')">📈 降维分析</button>
            <button class="quick-btn" onclick="sendMessage('执行聚类分析')">🎯 聚类分析</button>
            <button class="quick-btn" onclick="sendMessage('请进行完整的PBMC3K分析')">🚀 完整分析</button>
        </div>
        
        <div class="chat-container" id="chatContainer"></div>
        
        <div class="input-group">
            <input type="text" id="messageInput" placeholder="输入您的分析需求..." onkeypress="handleKeyPress(event)">
            <button class="btn" onclick="sendMessage()">发送</button>
        </div>
        
        <div class="plots" id="plotsContainer"></div>
        
        <div class="stats" id="statsContainer"></div>
    </div>

    <script>
        let ws;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'chat_response') {
                    displayResponse(data.data);
                }
            };
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
        
        async function sendMessage(text) {
            const message = text || document.getElementById('messageInput').value;
            if (!message.trim()) return;
            
            document.getElementById('messageInput').value = '';
            
            // 显示用户消息
            addMessage(message, 'user');
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message})
                });
                
                const data = await response.json();
                displayResponse(data);
                
            } catch (error) {
                addMessage(`错误: ${error.message}`, 'bot');
            }
        }
        
        function displayResponse(data) {
            addMessage(data.response, 'bot');
            
            if (data.plots && data.plots.length > 0) {
                displayPlots(data.plots);
            }
        }
        
        function addMessage(text, type) {
            const container = document.getElementById('chatContainer');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}-message`;
            messageDiv.innerHTML = text.replace(/\\n/g, '<br>');
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
        }
        
        function displayPlots(plots) {
            const container = document.getElementById('plotsContainer');
            container.innerHTML = '';
            
            plots.forEach(plot => {
                const plotDiv = document.createElement('div');
                plotDiv.className = 'plot';
                plotDiv.innerHTML = `<img src="/${plot}" alt="Analysis Plot">`;
                container.appendChild(plotDiv);
            });
        }
        
        // 初始化
        connectWebSocket();
        
        // 定期更新统计信息
        setInterval(async () => {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                updateStats(stats);
            } catch (error) {
                console.error('获取统计信息失败:', error);
            }
        }, 5000);
        
        function updateStats(stats) {
            const container = document.getElementById('statsContainer');
            container.innerHTML = `
                <div class="stat-card">
                    <h4>缓存统计</h4>
                    <p>内存缓存: ${stats.cache_stats.memory_cache.current_size_mb} MB</p>
                    <p>缓存条目: ${stats.cache_stats.memory_cache.total_entries}</p>
                </div>
                <div class="stat-card">
                    <h4>执行统计</h4>
                    <p>总执行次数: ${stats.execution_stats.execution_stats.total_executions}</p>
                    <p>平均执行时间: ${stats.execution_stats.avg_execution_time.toFixed(2)}s</p>
                </div>
                <div class="stat-card">
                    <h4>系统状态</h4>
                    <p>连接客户端: ${stats.server_stats.connected_clients}</p>
                    <p>运行时间: ${Math.floor(stats.server_stats.uptime / 60)}分钟</p>
                </div>
            `;
        }
    </script>
</body>
</html>
        """
    
    def run(self, host: str = "localhost", port: int = 8080):
        """启动服务器"""
        self._start_time = time.time()
        
        logger.info("🚀 启动RNA分析统一服务器...")
        logger.info(f"🌐 服务地址: http://{host}:{port}")
        logger.info(f"📚 API文档: http://{host}:{port}/docs")
        logger.info(f"💚 健康检查: http://{host}:{port}/health")
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )

if __name__ == "__main__":
    # 验证配置
    if not validate_config():
        logger.error("❌ 配置验证失败，请检查配置")
        sys.exit(1)
    
    # 启动统一服务器
    server = UnifiedRNAServer()
    print("服务器创建完成") 
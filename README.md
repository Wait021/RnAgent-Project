# 🧬 RnAgent - 单细胞RNA分析智能体系统

基于3端分离架构的智能化单细胞RNA测序数据分析系统，支持自然语言交互和一键部署。

## 📁 项目结构

```
rna-agent-project/
├── Rna/                                # 主项目文件夹
│   ├── 1_frontend/                     # Streamlit前端界面
│   ├── 2_agent_core/                   # LangGraph智能体核心
│   ├── 3_backend_mcp/                  # FastMCP后端服务器
│   ├── optimized_core/                 # 性能优化版本
│   ├── log_management/                 # 日志管理
│   ├── utils/                          # 工具函数
│   └── run_rna_demo.py                # 启动脚本
├── PBMC3kRNA-seq/                      # 数据集
│   ├── filtered_gene_bc_matrices/      # 处理后的数据
│   │   └── hg19/                      # 人类基因组版本
│   │       ├── matrix.mtx             # 表达矩阵
│   │       ├── barcodes.tsv           # 细胞标识
│   │       └── genes.tsv              # 基因信息
│   └── pbmc3k_filtered_gene_bc_matrices.tar  # 压缩包
├── config.py                           # 统一配置管理
├── deploy.sh                           # 服务器部署脚本
├── .gitignore                          # Git忽略规则
├── .env.template                       # 环境变量模板
└── README.md                           # 项目说明
```

## 🚀 快速开始

### 本地开发环境

1. **克隆项目**

```bash
git clone https://github.com/<your-github-username>/RnAgent-Project.git
cd RnAgent-Project
```

2. **安装依赖**

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 根据需求选择安装方式：
# 完整安装（推荐）
pip install -r requirements.txt

# 或最小安装（仅核心功能）
pip install -r requirements-minimal.txt

# 或开发环境安装（包含开发工具）
pip install -r requirements-dev.txt
```

3. **配置环境变量**

```bash
# 复制环境变量模板
cp .env.template .env

# 编辑.env文件，填写API密钥
export OPENAI_API_KEY="your_openai_key"
export DEEPSEEK_API_KEY="your_deepseek_key"
```

4. **启动服务**

```bash
# 标准版本（3端分离，支持解耦合工具发现）
cd Rna/
python run_rna_demo.py

# 或优化版本（统一服务器）
cd Rna/optimized_core/
python run_optimized_demo.py
```

> 🆕 **解耦合架构**: Agent现在支持自动工具发现，会从MCP服务器动态获取工具列表，无需硬编码工具名称！

5. **访问系统**

- 前端界面：[http://localhost:8501](http://localhost:8501)
- Agent核心：[http://localhost:8002](http://localhost:8002)
- MCP后端：[http://localhost:8000](http://localhost:8000)

## 🔧 解耦合架构特性

### 自动工具发现

系统现在支持真正的解耦合架构，Agent能够从MCP服务器自动发现和加载工具：

```python
# 自动从MCP服务器发现工具（类似OpenAI Agents SDK）
from rna_agent_graph import create_agent

# 创建支持工具发现的Agent
agent = create_agent(enable_discovery=True, mcp_server_url="http://localhost:8000")

# Agent会自动获取工具列表，无需硬编码
tools_info = agent.get_tools_info()
print(f"发现了 {len(tools_info)} 个工具")
```

### 工具发现API

MCP服务器提供RESTful API用于工具发现：

```bash
# 获取所有工具列表
curl http://localhost:8000/api/tools

# 获取特定工具信息
curl http://localhost:8000/api/tools/load_pbmc3k_data

# 调用工具
curl -X POST http://localhost:8000/api/tools/health_check/call \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 测试解耦合功能

运行集成测试验证解耦合功能：

```bash
# 在项目根目录运行
python test_integration.py
```

这将测试：

- MCP服务器工具发现API
- Agent动态工具加载
- 回退模式（硬编码工具）

### 回退机制

如果MCP服务器不可用，系统会自动回退到硬编码工具：

```python
# 禁用工具发现（使用硬编码工具）
agent = create_agent(enable_discovery=False)

# 或者在MCP服务器不可用时自动回退
# Agent会检测连接失败并使用硬编码工具
```

## 🌐 服务器部署

### 自动化部署（推荐）

1. **在服务器上运行部署脚本**

```bash
# 下载部署脚本
wget https://raw.githubusercontent.com/<your-github-username>/RnAgent-Project/main/deploy.sh
chmod +x deploy.sh

# 编辑脚本，设置Git仓库地址（已预配置）
# 仓库地址: https://github.com/<your-github-username>/RnAgent-Project.git

# 运行部署
./deploy.sh
```

2. **配置API密钥**

```bash
# 编辑环境配置
cd /home/$USER/rna_project
nano .env

# 填写您的API密钥
OPENAI_API_KEY=your_actual_openai_key
DEEPSEEK_API_KEY=your_actual_deepseek_key
```

3. **启动服务**

```bash
./start_rna_agent.sh
```

4. **访问系统**

```
http://your_server_ip:8501
```

### 手动部署

1. **创建项目目录**

```bash
mkdir -p /workspace/rna_project
cd /workspace/rna_project
```

2. **克隆代码**

```bash
git clone https://github.com/<your-github-username>/RnAgent-Project.git .
```

3. **安装依赖**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **配置环境**

```bash
export RNA_ENV=server
export OPENAI_API_KEY="your_key"
export DEEPSEEK_API_KEY="your_key"
```

5. **启动服务**

```bash
cd Rna/
python run_rna_demo.py
```

## 🔄 Git工作流程

### 开发工作流

1. **本地开发**

```bash
# 创建功能分支
git checkout -b feature/new-analysis-tool

# 开发和测试
# ... 编辑代码 ...

# 本地测试
python Rna/run_rna_demo.py
```

2. **提交代码**

```bash
# 添加文件
git add .

# 提交更改
git commit -m "添加新的分析工具"

# 推送到远程
git push origin feature/new-analysis-tool
```

3. **部署到服务器**

```bash
# 合并到主分支
git checkout main
git merge feature/new-analysis-tool
git push origin main

# 在服务器上更新
ssh your_server
cd /home/$USER/rna_project
git pull origin main
./stop_rna_agent.sh
./start_rna_agent.sh
```

### 自动化部署（使用Git Hooks）

在服务器上设置Git hooks实现推送后自动部署：

```bash
# 在服务器上设置
cd /home/$USER/rna_project/.git/hooks
cat > post-receive << 'EOF'
#!/bin/bash
cd /home/$USER/rna_project
git --git-dir=/home/$USER/rna_project/.git --work-tree=/home/$USER/rna_project checkout -f
./stop_rna_agent.sh
./start_rna_agent.sh
EOF
chmod +x post-receive
```

## 📊 数据管理

### 大文件处理

对于大型数据文件，建议使用Git LFS：

1. **安装Git LFS**

```bash
git lfs install
```

2. **跟踪大文件**

```bash
git lfs track "*.tar"
git lfs track "*.h5ad"
git lfs track "*.pkl"
```

3. **添加.gitattributes**

```bash
git add .gitattributes
git commit -m "配置Git LFS"
```

### 数据同步策略

1. **小于100MB的数据**：直接提交到Git
2. **大于100MB的数据**：使用Git LFS
3. **超大数据集**：使用rsync单独同步

```bash
# 单独同步数据
rsync -avz --progress PBMC3kRNA-seq/ user@server:/home/user/rna_project/PBMC3kRNA-seq/
```

## 🔧 配置管理

### 环境配置

项目使用 `config.py`进行统一配置管理，自动检测运行环境：

- **本地环境** (macOS)：使用本地路径和调试级别日志
- **服务器环境** (Linux)：使用服务器路径和生产级别日志

### 环境变量

```bash
# 核心配置
RNA_ENV=local|server          # 运行环境
OPENAI_API_KEY=your_key       # OpenAI API密钥
DEEPSEEK_API_KEY=your_key     # DeepSeek API密钥

# 服务器配置
FRONTEND_PORT=8501            # 前端端口
AGENT_PORT=8002               # Agent端口
MCP_PORT=8000                 # MCP端口

# 路径配置
PBMC3K_PATH=/path/to/data     # 数据路径（可选）
```

## 🛠️ 开发指南

### 添加新功能

1. **创建功能分支**

```bash
git checkout -b feature/your-feature
```

2. **开发新工具**

```python
# 在 Rna/3_backend_mcp/rna_mcp_server.py 中添加
@mcp_server.tool()
async def your_new_tool(params: str) -> str:
    """新的分析工具"""
    # 实现功能
    return result
```

3. **测试功能**

```bash
python Rna/utils/test_demo.py
```

4. **提交代码**

```bash
git add .
git commit -m "添加新功能: your-feature"
git push origin feature/your-feature
```

### 调试技巧

1. **查看日志**

```bash
# Agent核心日志
tail -f Rna/2_agent_core/agent_server.log

# MCP后端日志
tail -f Rna/3_backend_mcp/rna_mcp_server.log
```

2. **测试单个组件**

```bash
# 测试MCP服务器
python Rna/3_backend_mcp/rna_mcp_server.py

# 测试Agent核心
python Rna/2_agent_core/agent_server.py
```

3. **配置验证**

```bash
python -c "from config import config_manager; config_manager.print_config_info()"
```

## 🚨 故障排除

### 常见问题

1. **端口被占用**

```bash
# 查看端口占用
lsof -i :8501
lsof -i :8002
lsof -i :8000

# 杀死进程
pkill -f streamlit
pkill -f agent_server
pkill -f rna_mcp_server
```

2. **数据路径错误**

```bash
# 检查数据文件
ls -la PBMC3kRNA-seq/filtered_gene_bc_matrices/hg19/

# 验证配置
python -c "from config import get_data_path; print(get_data_path())"
```

3. **依赖包问题**

```bash
# 重新安装依赖
pip install --force-reinstall -r requirements.txt
```

4. **API密钥问题**

```bash
# 检查环境变量
env | grep API_KEY

# 测试API连接
python -c "
import os
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
print('API密钥有效')
"
```

## 📝 更新日志

### v1.0.0 (2025-01-XX)

- ✨ 初始版本发布
- 🏗️ 3端分离架构
- 🚀 一键部署脚本
- 📊 完整分析流程

### v1.1.0 (计划中)

- ⚡ 性能优化版本
- 💾 智能缓存系统
- 🔧 统一服务器架构
- 📈 实时监控功能

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

如有问题，请：

1. 查看[故障排除](#-故障排除)部分
2. 检查[Issues](https://github.com/<your-github-username>/RnAgent-Project/issues)
3. 创建新的Issue

---

**RnAgent - 让单细胞RNA分析变得简单智能** 🧬

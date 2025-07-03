# 🧬 RnAgent 安装指南

本文档提供了RnAgent单细胞RNA分析智能体系统的详细安装说明。

## 📋 系统要求

### 最低要求

- **操作系统**: Linux, macOS, Windows 10+
- **Python**: 3.9+ (推荐 3.11)
- **内存**: 8GB RAM (推荐 16GB+)
- **存储**: 10GB 可用空间
- **网络**: 稳定的互联网连接（用于API调用）

### 推荐配置

- **CPU**: 4核心以上
- **内存**: 16GB+ RAM
- **存储**: SSD 20GB+ 可用空间
- **GPU**: 可选，用于加速某些计算

## 🚀 快速安装

### 方法一：一键安装脚本（推荐）

```bash
# 下载并运行安装脚本
curl -fsSL https://raw.githubusercontent.com/Wait021/RnAgent-Project/main/deploy.sh | bash
```

### 方法二：手动安装

1. **克隆项目**

```bash
git clone https://github.com/Wait021/RnAgent-Project.git
cd RnAgent-Project
```

2. **创建虚拟环境**

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

3. **选择安装方式**

#### 完整安装（推荐）

```bash
pip install -r requirements.txt
```

#### 最小安装（仅核心功能）

```bash
pip install -r requirements-minimal.txt
```

#### 开发环境安装

```bash
pip install -r requirements-dev.txt
```

## 📦 依赖文件说明

### `requirements.txt` - 完整安装

- 包含所有功能所需的依赖
- 支持完整的单细胞RNA分析流程
- 包括所有聚类、降维、可视化算法
- **推荐用于生产环境**

### `requirements-minimal.txt` - 最小安装

- 仅包含核心功能依赖
- 更快的安装速度
- 更小的环境占用
- **适合快速测试和演示**

### `requirements-dev.txt` - 开发环境

- 包含完整功能 + 开发工具
- 代码格式化、测试、文档工具
- **适合开发者和贡献者**

## 🔧 环境配置

1. **复制环境变量模板**

```bash
cp env.template .env
```

2. **编辑环境变量**

```bash
nano .env
```

3. **填写必要的API密钥**

```bash
# 必填项
OPENAI_API_KEY=your_openai_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key

# 可选项
RNA_ENV=local
FRONTEND_PORT=8501
AGENT_PORT=8002
MCP_PORT=8000
```

## ⚡ 启动服务

### 标准模式（3端分离）

```bash
cd Rna/
python run_rna_demo.py
```

### 优化模式（统一服务器）

```bash
cd Rna/optimized_core/
python run_optimized_demo.py
```

## 🌐 访问系统

启动成功后，可以通过以下地址访问：

- **前端界面**: <http://localhost:8501>
- **Agent核心**: <http://localhost:8002>  
- **MCP后端**: <http://localhost:8000>

## 🔍 验证安装

运行测试脚本验证安装：

```bash
# 测试连接
python Rna/utils/test_mcp_connection.py

# 测试完整流程
python Rna/utils/test_demo.py
```

## 🛠️ 常见问题解决

### 1. 依赖安装失败

**问题**: `leidenalg` 或 `python-igraph` 安装失败

**解决方案**:

```bash
# macOS
brew install igraph
pip install python-igraph leidenalg

# Ubuntu/Debian
sudo apt-get install libigraph0-dev
pip install python-igraph leidenalg

# CentOS/RHEL
sudo yum install igraph-devel
pip install python-igraph leidenalg
```

### 2. 内存不足

**问题**: 分析大数据集时内存不足

**解决方案**:

- 使用 `requirements-minimal.txt` 安装
- 增加系统虚拟内存
- 使用数据采样功能

### 3. API密钥错误

**问题**: API调用失败

**解决方案**:

```bash
# 检查环境变量
echo $OPENAI_API_KEY

# 测试API连接
python -c "
import os
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
print('API密钥有效')
"
```

### 4. 端口被占用

**问题**: 启动时端口冲突

**解决方案**:

```bash
# 查看端口占用
lsof -i :8501
lsof -i :8002
lsof -i :8000

# 杀死占用进程
pkill -f streamlit
pkill -f agent_server
pkill -f rna_mcp_server
```

## 🐳 Docker 安装（即将支持）

```bash
# 构建镜像
docker build -t rnagent .

# 运行容器
docker run -p 8501:8501 -e OPENAI_API_KEY=your_key rnagent
```

## 📊 性能优化建议

### 本地开发

- 使用 `requirements-minimal.txt`
- 启用代码缓存
- 使用小数据集测试

### 生产部署

- 使用 `requirements.txt`
- 配置合适的服务器规格
- 启用日志记录和监控

### 大规模数据分析

- 增加内存配置
- 使用GPU加速（如果可用）
- 考虑分布式计算

## 📝 更新和维护

### 更新到最新版本

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### 清理缓存

```bash
# 清理Python缓存
find . -type d -name "__pycache__" -exec rm -rf {} +

# 清理分析缓存
rm -rf Rna/*/cache/
rm -rf Rna/*/tmp/
```

## 🆘 获取帮助

1. 查看[故障排除文档](README.md#-故障排除)
2. 提交[Issue](https://github.com/Wait021/RnAgent-Project/issues)
3. 查看[项目文档](Rna/RnaAgent项目综合文档.md)

---

**祝您使用愉快！** 🎉

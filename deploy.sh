#!/bin/bash

# RnAgent 服务器自动部署脚本
# 用法: ./deploy.sh [环境名称]

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数定义
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 配置变量
PROJECT_NAME="rna_project"
PROJECT_DIR="./$PROJECT_NAME"
REPO_URL="https://github.com/Wait021/RnAgent-Project.git"  # RnAgent项目仓库地址
SERVICE_NAME="rna_agent"

# 获取环境参数
ENVIRONMENT=${1:-"server"}

log_info "开始部署 RnAgent 项目..."
log_info "目标环境: $ENVIRONMENT"
log_info "项目目录: $PROJECT_DIR"

# 1. 创建项目目录
log_info "创建项目目录..."
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# 2. 检查是否为Git仓库
if [ ! -d ".git" ]; then
    if [ -z "$REPO_URL" ]; then
        log_error "请设置REPO_URL变量为您的Git仓库地址"
        exit 1
    fi
    log_info "克隆仓库..."
    git clone "$REPO_URL" .
else
    log_info "拉取最新代码..."
    git fetch origin
    git reset --hard origin/main  # 强制重置到远程main分支
fi

# 3. 设置环境变量
log_info "设置环境变量..."
export RNA_ENV="$ENVIRONMENT"

# 检查.env文件
if [ ! -f ".env" ]; then
    log_warning ".env文件不存在，创建模板..."
    cat > .env << EOF
# RnAgent 环境配置
RNA_ENV=$ENVIRONMENT

# API密钥 (请填写您的实际密钥)
OPENAI_API_KEY=your_openai_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here

# 服务器配置
FRONTEND_PORT=8501
AGENT_PORT=8002
MCP_PORT=8000
EOF
    log_warning "请编辑 .env 文件并填写正确的API密钥"
fi

# 4. 检查Python环境
log_info "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 未安装"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
log_info "Python版本: $PYTHON_VERSION"

# 5. 安装Python依赖
log_info "安装Python依赖..."

# 检查是否有虚拟环境
if [ ! -d "venv" ]; then
    log_info "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装依赖
if [ -f "requirements.txt" ]; then
    log_info "安装项目依赖..."
    pip install -r requirements.txt
else
    log_info "安装组件依赖..."
    # 安装各组件依赖
    [ -f "Rna/1_frontend/requirements.txt" ] && pip install -r Rna/1_frontend/requirements.txt
    [ -f "Rna/2_agent_core/requirements.txt" ] && pip install -r Rna/2_agent_core/requirements.txt
    [ -f "Rna/3_backend_mcp/requirements.txt" ] && pip install -r Rna/3_backend_mcp/requirements.txt
    [ -f "Rna/optimized_core/requirements.txt" ] && pip install -r Rna/optimized_core/requirements.txt
fi

# 6. 检查数据文件
log_info "检查数据文件..."
DATA_DIR="$PROJECT_DIR/PBMC3kRNA-seq/filtered_gene_bc_matrices/hg19"

if [ ! -d "$DATA_DIR" ]; then
    log_warning "数据目录不存在: $DATA_DIR"
    
    # 检查是否有压缩文件需要解压
    TAR_FILE="$PROJECT_DIR/PBMC3kRNA-seq/pbmc3k_filtered_gene_bc_matrices.tar"
    if [ -f "$TAR_FILE" ]; then
        log_info "解压数据文件..."
        cd "$PROJECT_DIR/PBMC3kRNA-seq"
        tar -xf pbmc3k_filtered_gene_bc_matrices.tar
        cd "$PROJECT_DIR"
    else
        log_error "未找到数据文件，请手动上传PBMC3K数据集"
        exit 1
    fi
fi

# 验证必要文件
REQUIRED_FILES=("matrix.mtx" "barcodes.tsv" "genes.tsv")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$DATA_DIR/$file" ]; then
        log_error "缺少必要数据文件: $file"
        exit 1
    fi
done

log_success "数据文件检查完成"

# 7. 创建systemd服务文件（可选）
if command -v systemctl &> /dev/null; then
    log_info "创建systemd服务..."
    
    sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=RnAgent RNA Analysis Service
After=network.target

[Service]
Type=forking
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/Rna/run_rna_demo.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    log_success "systemd服务创建完成"
fi

# 8. 测试配置
log_info "测试配置..."
cd "$PROJECT_DIR"
source venv/bin/activate

# 测试导入
python3 -c "
import sys
sys.path.append('$PROJECT_DIR')
from config import config_manager
config_manager.print_config_info()
if config_manager.validate_config():
    print('✅ 配置验证成功')
else:
    print('❌ 配置验证失败')
    sys.exit(1)
"

# 9. 设置防火墙（如果需要）
log_info "检查防火墙设置..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 8501/tcp comment 'RnAgent Frontend'
    sudo ufw allow 8002/tcp comment 'RnAgent Core'
    sudo ufw allow 8000/tcp comment 'RnAgent MCP'
    log_success "防火墙规则已设置"
fi

# 10. 创建启动脚本
log_info "创建启动脚本..."
cat > start_rna_agent.sh << 'EOF'
#!/bin/bash
cd ./rna_project
source venv/bin/activate
export RNA_ENV=server

# 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 启动RnAgent
python3 Rna/run_rna_demo.py
EOF

chmod +x start_rna_agent.sh

# 11. 创建停止脚本
cat > stop_rna_agent.sh << 'EOF'
#!/bin/bash
# 停止RnAgent相关进程
pkill -f "rna_mcp_server.py"
pkill -f "agent_server.py"
pkill -f "rna_streamlit_app"
pkill -f "run_rna_demo.py"
echo "RnAgent 服务已停止"
EOF

chmod +x stop_rna_agent.sh

log_success "部署完成！"
echo ""
echo "🎉 RnAgent 部署成功！"
echo ""
echo "📋 下一步操作："
echo "1. 编辑 .env 文件，填写您的API密钥"
echo "2. 运行: ./start_rna_agent.sh"
echo "3. 访问: http://your_server_ip:8501"
echo ""
echo "🔧 管理命令："
echo "  启动服务: ./start_rna_agent.sh"
echo "  停止服务: ./stop_rna_agent.sh"
if command -v systemctl &> /dev/null; then
echo "  系统服务: sudo systemctl start/stop/status $SERVICE_NAME"
fi
echo ""
echo "📊 日志查看："
echo "  实时日志: tail -f Rna/2_agent_core/agent_server.log"
echo "  MCP日志: tail -f Rna/3_backend_mcp/rna_mcp_server.log" 
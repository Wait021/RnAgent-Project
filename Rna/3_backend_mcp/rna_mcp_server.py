#!/usr/bin/env python3
"""
RNA分析MCP服务器 - 基于STAgent_MCP的优化版本
"""

# ==== 首先导入标准库和第三方库 ====
from pydantic import BaseModel, Field
from fastmcp import FastMCP
import matplotlib.pyplot as plt
from typing import Dict, Any, Optional, List, Tuple
from io import StringIO
from datetime import datetime
import multiprocessing
import json
import re
import sys
import logging
import os
# ==== 设置项目根路径 ====
# 将项目根目录加入到 sys.path，确保可以找到config.py
project_root = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ==== 现在导入项目配置模块 ====
from config import get_config, get_data_path, get_plots_path
# === 设置项目根路径并导入配置 ===
# 获取配置
config = get_config()


# 设置详细的日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('rna_mcp_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 创建图片保存目录
plot_dir = get_plots_path()
os.makedirs(plot_dir, exist_ok=True)

# 创建FastMCP实例
mcp = FastMCP("RNA-Analysis-MCP-Server")


class PythonREPL(BaseModel):
    """模拟独立的Python REPL，参考STAgent_MCP实现"""

    globals: Optional[Dict] = Field(default_factory=dict, alias="_globals")
    locals: Optional[Dict] = None

    @staticmethod
    def sanitize_input(query: str) -> str:
        """清理输入到Python REPL的代码"""
        query = re.sub(r"^(\s|`)*(?i:python)?\s*", "", query)
        query = re.sub(r"(\s|`)*$", "", query)
        return query

    def run(self, command: str, timeout: Optional[int] = None) -> str:
        """运行命令并返回任何打印的内容 - 修复版本，直接在主进程中执行"""
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()

        try:
            cleaned_command = self.sanitize_input(command)
            logger.info(
                f"🔍 [代码清理] 原始长度: {len(command)}, 清理后长度: {len(cleaned_command)}")

            # 确保全局命名空间存在
            if self.globals is None:
                self.globals = {}

            # 在主进程中直接执行，保持变量持久性
            exec(cleaned_command, self.globals, self.locals)

            sys.stdout = old_stdout
            output = mystdout.getvalue()

            logger.info(f"✅ [代码执行] 执行成功，输出长度: {len(output)}")
            logger.info(f"📊 [全局变量] 当前全局变量数量: {len(self.globals)}")

            # 记录重要变量的存在
            important_vars = ['adata', 'sc', 'plt', 'pd', 'np']
            existing_vars = [
                var for var in important_vars if var in self.globals]
            if existing_vars:
                logger.info(f"✅ [变量检查] 存在的重要变量: {existing_vars}")

            return output

        except Exception as e:
            sys.stdout = old_stdout
            logger.error(f"❌ [代码执行] 执行失败: {str(e)}")
            logger.error(f"📍 [错误位置] 代码: {cleaned_command[:100]}...")

            import traceback
            logger.error(f"📋 [错误详情] {traceback.format_exc()}")

            return f"Error: {repr(e)}"


# 创建Python执行器实例，使用全局共享命名空间
global_namespace = {}
python_repl = PythonREPL(_globals=global_namespace)


@mcp.tool()
def python_repl_tool(query: str) -> dict:
    """执行Python代码的工具，参考STAgent_MCP的实现，支持图片生成和返回"""
    import time
    start_time = time.time()

    logger.info("="*60)
    logger.info("🐍 [MCP工具] python_repl_tool 开始执行")
    logger.info(f"📥 [输入参数] 类型: {type(query)}, 长度: {len(str(query))}")
    logger.info("="*60)

    # 简化输入处理逻辑
    code_str = ""

    if isinstance(query, str):
        code_str = query
    elif isinstance(query, dict):
        code_str = query.get('content', str(query))
    elif hasattr(query, 'content'):
        content = getattr(query, 'content', '')
        if isinstance(content, list) and len(content) > 0:
            for item in content:
                if hasattr(item, 'text'):
                    text_content = item.text
                    # 尝试解析JSON
                    try:
                        parsed = json.loads(text_content)
                        if isinstance(parsed, dict) and 'content' in parsed:
                            code_str = parsed['content']
                            break
                    except:
                        code_str = text_content
                        break
        else:
            code_str = str(content)
    else:
        code_str = str(query)

    # ===== 自动注入前导代码，保证最小依赖 =====
    prelude_lines: list[str] = []

    global_dict = python_repl.globals or {}

    # 如果尚未导入 scanpy / matplotlib，则注入
    if 'sc' not in global_dict:
        prelude_lines.append('import scanpy as sc')
        prelude_lines.append('import matplotlib.pyplot as plt')
        prelude_lines.append(
            "sc.settings.set_figure_params(dpi=80, show=False)")

    # 如果 adata 尚未加载且即将用到，则尝试预加载（避免后续 NameError）
    if 'adata' not in global_dict:
        # 只有当代码片段包含 "adata" 字样才尝试加载，避免无谓的 I/O
        if 'adata' in code_str:
            data_path = get_data_path()
            preload_code = f"data_path = '{data_path}'\nadata = sc.read_10x_mtx(data_path, var_names='gene_symbols', cache=True)\nadata.var_names_make_unique()"
            prelude_lines.append(preload_code)

    if prelude_lines:
        code_str = "\n".join(prelude_lines) + "\n" + code_str
        logger.info(f"📋 [代码注入] 注入了 {len(prelude_lines)} 行前导代码")

    logger.info(f"💻 [代码执行] 开始执行代码 ({len(code_str)} 字符)")
    logger.info(f"📝 [代码内容] {code_str[:200]}...")

    plot_paths = []
    result_parts = []

    try:
        logger.info("🚀 [Python执行] 开始运行Python代码...")
        exec_start = time.time()

        output = python_repl.run(code_str)

        exec_time = time.time() - exec_start
        logger.info(f"✅ [Python完成] 代码执行完成，耗时: {exec_time:.2f}s")

        if output and output.strip():
            logger.info(f"📤 [执行输出] {output.strip()[:100]}...")
            result_parts.append(output.strip())
        else:
            logger.info("📤 [执行输出] 无输出内容")

        # 检查生成的图表
        figures = [plt.figure(i) for i in plt.get_fignums()]
        if figures:
            logger.info(f"🖼️ [图片检测] 发现 {len(figures)} 个matplotlib图表")
            for i, fig in enumerate(figures):
                fig.set_size_inches(10, 6)
                plot_filename = f"plot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
                rel_path = os.path.join("tmp/plots", plot_filename)
                abs_path = os.path.join(os.path.dirname(__file__), rel_path)
                fig.savefig(abs_path, bbox_inches='tight', dpi=150)
                plot_paths.append(rel_path)
                logger.info(f"💾 [图片保存] 图片 {i+1} 保存为: {rel_path}")
            plt.close("all")
            result_parts.append(f"Generated {len(plot_paths)} plot(s).")
        else:
            logger.info("🖼️ [图片检测] 未发现matplotlib图表")

        if not result_parts:
            result_parts.append(
                "Executed code successfully with no output. If you want to see the output of a value, you should print it out with `print(...)`."
            )

    except Exception as e:
        exec_time = time.time() - exec_start if 'exec_start' in locals() else 0
        logger.error(f"❌ [Python错误] 代码执行失败，耗时: {exec_time:.2f}s")
        logger.error(f"🔥 [错误详情] {str(e)}")

        import traceback
        logger.error(f"📋 [错误栈] {traceback.format_exc()}")

        result_parts.append(f"Error executing code: {e}")

    total_time = time.time() - start_time
    result_summary = "\n".join(result_parts)
    result = {"content": result_summary, "artifact": plot_paths}

    logger.info("="*60)
    logger.info(f"🏁 [MCP完成] python_repl_tool 执行完成")
    logger.info(f"⏱️ [总耗时] {total_time:.2f}s")
    logger.info(
        f"📊 [结果统计] 内容长度: {len(result_summary)}, 图片数量: {len(plot_paths)}")
    logger.info(f"📤 [返回结果] {str(result)[:200]}...")
    logger.info("="*60)

    return result

# === 辅助函数: 统一执行代码并返回结果 ===


def _run_code(code: str) -> Dict[str, Any]:
    """直接执行 Python 代码并捕获输出 / 图像"""
    plot_paths: List[str] = []
    result_parts: List[str] = []

    try:
        output = python_repl.run(code)
        if output and output.strip():
            result_parts.append(output.strip())

        # 保存所有当前图像
        figures = [plt.figure(i) for i in plt.get_fignums()]
        if figures:
            for fig in figures:
                fig.set_size_inches(10, 6)
                plot_filename = f"plot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
                rel_path = os.path.join("tmp/plots", plot_filename)
                abs_path = os.path.join(os.path.dirname(__file__), rel_path)
                fig.savefig(abs_path, bbox_inches='tight', dpi=150)
                plot_paths.append(rel_path)
            plt.close("all")
            result_parts.append(f"Generated {len(plot_paths)} plot(s).")

        if not result_parts:
            result_parts.append(
                "Executed code successfully with no output. If you want to see the output of a value, you should print it out with `print(...)`.")

    except Exception as e:
        result_parts.append(f"Error executing code: {e}")

    return {"content": "\n".join(result_parts), "artifact": plot_paths}


@mcp.tool()
def load_pbmc3k_data() -> Dict[str, Any]:
    """加载PBMC3K数据集的代码"""
    import time
    start_time = time.time()

    logger.info("="*60)
    logger.info("🧬 [MCP工具] load_pbmc3k_data 开始执行")
    logger.info("📁 [数据加载] 准备加载PBMC3K数据集")
    logger.info("="*60)

    # 首先，预初始化全局命名空间中的基本模块
    prelude_code = '''
# 导入基本模块
import scanpy as sc
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 设置scanpy参数
sc.settings.verbosity = 2
sc.settings.set_figure_params(dpi=80, dpi_save=150)
plt.rcParams['figure.figsize'] = (8, 6)
'''
    # 预先执行导入和设置
    _run_code(prelude_code)

    code = f'''
# 数据路径
data_path = "{get_data_path()}"

print(f"正在从以下路径加载数据: {{data_path}}")

# 加载10X数据
adata = sc.read_10x_mtx(
    data_path,
    var_names='gene_symbols',
    cache=True
)

# 使基因名唯一
adata.var_names_make_unique()

print(f"\\n=== PBMC3K数据集基本信息 ===")
print(f"数据形状: {{adata.shape}}")
print(f"细胞数量: {{adata.n_obs}}")
print(f"基因数量: {{adata.n_vars}}")
print(f"AnnData对象: {{adata}}")

# 显示前5个细胞和基因的数据
print("\\n=== 数据预览 ===")
print("前5个细胞，前5个基因的表达量:")
print(adata.X[:5, :5].toarray())

# 确保adata在全局空间可用
globals()["adata"] = adata

print("\\n✅ PBMC3K数据加载完成!")
'''

    logger.info("💻 [代码执行] 开始执行PBMC3K数据加载代码")
    result = _run_code(code)

    total_time = time.time() - start_time
    logger.info("="*60)
    logger.info(f"🏁 [MCP完成] load_pbmc3k_data 执行完成")
    logger.info(f"⏱️ [总耗时] {total_time:.2f}s")
    logger.info(
        f"📊 [结果统计] 内容长度: {len(result.get('content', ''))}, 图片数量: {len(result.get('artifact', []))}")
    logger.info("="*60)

    return result


@mcp.tool()
def quality_control_analysis() -> Dict[str, Any]:
    """质量控制分析代码"""
    import time
    start_time = time.time()

    logger.info("="*60)
    logger.info("📊 [MCP工具] quality_control_analysis 开始执行")
    logger.info("🔍 [质量控制] 准备进行质量控制分析和可视化")
    logger.info("="*60)

    code = '''
# 质量控制分析
print("\\n=== 开始质量控制分析 ===")

# 计算质量控制指标
adata.var['mt'] = adata.var_names.str.startswith('MT-')  # 线粒体基因
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)

# 添加一些基本统计信息
print(f"线粒体基因数量: {adata.var['mt'].sum()}")
print(
    f"每个细胞的基因数量范围: {adata.obs['n_genes_by_counts'].min():.0f} - {adata.obs['n_genes_by_counts'].max():.0f}")
print(
    f"每个细胞的总分子数范围: {adata.obs['total_counts'].min():.0f} - {adata.obs['total_counts'].max():.0f}")
print(
    f"线粒体基因比例范围: {adata.obs['pct_counts_mt'].min():.2f}% - {adata.obs['pct_counts_mt'].max():.2f}%")

# 质控可视化 - 第一组图表
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# 每个细胞的基因数量分布
axes[0].hist(adata.obs['n_genes_by_counts'], bins=50, alpha=0.7, color='blue')
axes[0].set_xlabel('Number of genes by counts')
axes[0].set_ylabel('Number of cells')
axes[0].set_title('Genes per cell distribution')

# 每个细胞的总分子数分布
axes[1].hist(adata.obs['total_counts'], bins=50, alpha=0.7, color='green')
axes[1].set_xlabel('Total counts')
axes[1].set_ylabel('Number of cells')
axes[1].set_title('UMI counts per cell distribution')

# 线粒体基因比例分布
axes[2].hist(adata.obs['pct_counts_mt'], bins=50, alpha=0.7, color='red')
axes[2].set_xlabel('Mitochondrial gene percentage')
axes[2].set_ylabel('Number of cells')
axes[2].set_title('Mitochondrial gene % distribution')

plt.tight_layout()
plt.suptitle('Quality Control Metrics Distribution', y=1.02, fontsize=16)

# 第二组图表 - 小提琴图
fig2, axes2 = plt.subplots(1, 3, figsize=(15, 5))

# 手动创建小提琴图，避免scanpy的显示问题
import seaborn as sns

# 基因数量小提琴图
axes2[0].violinplot([adata.obs['n_genes_by_counts']], positions=[0])
axes2[0].set_ylabel('Number of genes by counts')
axes2[0].set_title('Genes per cell (violin)')
axes2[0].set_xticks([])

# 总counts小提琴图
axes2[1].violinplot([adata.obs['total_counts']], positions=[0])
axes2[1].set_ylabel('Total counts')
axes2[1].set_title('Total UMI counts (violin)')
axes2[1].set_xticks([])

# 线粒体基因比例小提琴图
axes2[2].violinplot([adata.obs['pct_counts_mt']], positions=[0])
axes2[2].set_ylabel('Mitochondrial gene percentage')
axes2[2].set_title('Mitochondrial % (violin)')
axes2[2].set_xticks([])

plt.tight_layout()
plt.suptitle('Quality Control Metrics (Violin Plots)', y=1.02, fontsize=16)

print("\\n✅ 质量控制分析完成!")
'''

    logger.info("💻 [代码执行] 开始执行质量控制分析代码")
    result = _run_code(code)

    total_time = time.time() - start_time
    logger.info("="*60)
    logger.info(f"🏁 [MCP完成] quality_control_analysis 执行完成")
    logger.info(f"⏱️ [总耗时] {total_time:.2f}s")
    logger.info(
        f"📊 [结果统计] 内容长度: {len(result.get('content', ''))}, 图片数量: {len(result.get('artifact', []))}")
    logger.info("="*60)

    return result


@mcp.tool()
def preprocessing_analysis() -> Dict[str, Any]:
    """数据预处理分析代码"""
    logger.info("返回数据预处理分析代码")

    code = '''
# 数据预处理
print("\\n=== 开始数据预处理 ===")

# 过滤细胞和基因
print("过滤前:")
print(f"细胞数量: {adata.n_obs}")
print(f"基因数量: {adata.n_vars}")

# 过滤基因：至少在3个细胞中表达
sc.pp.filter_genes(adata, min_cells=3)

# 过滤细胞：表达基因数在200-5000之间，线粒体基因比例<20%
sc.pp.filter_cells(adata, min_genes=200)
adata = adata[adata.obs.n_genes_by_counts < 5000, :]
adata = adata[adata.obs.pct_counts_mt < 20, :]

print("\\n过滤后:")
print(f"细胞数量: {adata.n_obs}")
print(f"基因数量: {adata.n_vars}")

# 保存原始数据
adata.raw = adata

# 归一化到每个细胞10,000个分子
sc.pp.normalize_total(adata, target_sum=1e4)

# 对数变换
sc.pp.log1p(adata)

# 寻找高变基因
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)

# 可视化高变基因 - 手动创建图表
fig, ax = plt.subplots(figsize=(10, 6))
highly_var_data = adata.var[[
    'means', 'dispersions_norm', 'highly_variable']].copy()

# 绘制散点图
not_hv = highly_var_data[~highly_var_data['highly_variable']]
hv = highly_var_data[highly_var_data['highly_variable']]

ax.scatter(not_hv['means'], not_hv['dispersions_norm'],
          alpha=0.5, s=1, color='lightgray', label='Not highly variable')
ax.scatter(hv['means'], hv['dispersions_norm'],
          alpha=0.7, s=1, color='red', label='Highly variable')

ax.set_xlabel('Mean expression')
ax.set_ylabel('Normalized dispersion')
ax.set_title('Highly Variable Genes')
ax.legend()
ax.set_xscale('log')

print(f"\\n高变基因数量: {sum(adata.var.highly_variable)}")

# 只保留高变基因进行下游分析
adata.raw = adata
adata = adata[:, adata.var.highly_variable]

print("\\n✅ 数据预处理完成!")
'''

    return _run_code(code)


@mcp.tool()
def dimensionality_reduction_analysis() -> Dict[str, Any]:
    """降维分析代码"""
    logger.info("返回降维分析代码")

    code = '''
# 降维分析
print("\\n=== 开始降维分析 ===")

# 标准化数据
sc.pp.scale(adata, max_value=10)

# 主成分分析
sc.tl.pca(adata, svd_solver='arpack')

# 手动可视化PCA方差比例
fig, ax = plt.subplots(figsize=(10, 6))
pca_variance_ratio = adata.uns['pca']['variance_ratio'][:50]
ax.plot(range(1, len(pca_variance_ratio)+1), pca_variance_ratio, 'bo-')
ax.set_xlabel('Principal Component')
ax.set_ylabel('Variance Ratio')
ax.set_title('PCA Variance Ratio')
ax.set_yscale('log')
ax.grid(True, alpha=0.3)

# 计算邻居图
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=40)

# UMAP降维
sc.tl.umap(adata)

# 手动创建UMAP可视化
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# UMAP with total_counts
scatter1 = axes[0].scatter(adata.obsm['X_umap'][:, 0], adata.obsm['X_umap'][:, 1],
                          c=adata.obs['total_counts'], s=1, alpha=0.7, cmap='viridis')
axes[0].set_xlabel('UMAP_1')
axes[0].set_ylabel('UMAP_2')
axes[0].set_title('UMAP: Total Counts')
plt.colorbar(scatter1, ax=axes[0])

# UMAP with n_genes_by_counts
scatter2 = axes[1].scatter(adata.obsm['X_umap'][:, 0], adata.obsm['X_umap'][:, 1],
                          c=adata.obs['n_genes_by_counts'], s=1, alpha=0.7, cmap='viridis')
axes[1].set_xlabel('UMAP_1')
axes[1].set_ylabel('UMAP_2')
axes[1].set_title('UMAP: Number of Genes')
plt.colorbar(scatter2, ax=axes[1])

# UMAP with pct_counts_mt
scatter3 = axes[2].scatter(adata.obsm['X_umap'][:, 0], adata.obsm['X_umap'][:, 1],
                          c=adata.obs['pct_counts_mt'], s=1, alpha=0.7, cmap='viridis')
axes[2].set_xlabel('UMAP_1')
axes[2].set_ylabel('UMAP_2')
axes[2].set_title('UMAP: Mitochondrial %')
plt.colorbar(scatter3, ax=axes[2])

plt.tight_layout()

print("\\n✅ 降维分析完成!")
'''

    return _run_code(code)


@mcp.tool()
def clustering_analysis() -> Dict[str, Any]:
    """聚类分析代码"""
    logger.info("返回聚类分析代码")

    code = '''
# 聚类分析
print("\\n=== 开始聚类分析 ===")

# Leiden聚类
sc.tl.leiden(adata, resolution=0.5)

# 显示聚类统计
cluster_counts = adata.obs['leiden'].value_counts().sort_index()
print("\\n各聚类的细胞数量:")
for cluster, count in cluster_counts.items():
    print(f"Cluster {cluster}: {count} cells")

print(f"\\n总共识别出 {len(cluster_counts)} 个聚类")

# 手动创建UMAP聚类可视化
import numpy as np
import matplotlib.colors as mcolors

# 创建综合图表
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
fig.suptitle('UMAP visualization with clustering and QC metrics', fontsize=16)

# 为聚类创建颜色映射
unique_clusters = adata.obs['leiden'].unique()
colors = plt.cm.tab10(np.linspace(0, 1, len(unique_clusters)))
cluster_colors = dict(zip(unique_clusters, colors))

# 聚类结果
for cluster in unique_clusters:
    mask = adata.obs['leiden'] == cluster
    axes[0,0].scatter(adata.obsm['X_umap'][mask, 0], adata.obsm['X_umap'][mask, 1],
                     c=[cluster_colors[cluster]], s=1, alpha=0.7, label=f'Cluster {cluster}')
axes[0,0].set_xlabel('UMAP_1')
axes[0,0].set_ylabel('UMAP_2')
axes[0,0].set_title('Leiden clustering')
axes[0, 0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')

# 总counts
scatter1 = axes[0, 1].scatter(adata.obsm['X_umap'][:, 0], adata.obsm['X_umap'][:, 1],
                           c=adata.obs['total_counts'], s=1, alpha=0.7, cmap='viridis')
axes[0, 1].set_xlabel('UMAP_1')
axes[0, 1].set_ylabel('UMAP_2')
axes[0, 1].set_title('Total counts')

# 基因数量
scatter2 = axes[1, 0].scatter(adata.obsm['X_umap'][:, 0], adata.obsm['X_umap'][:, 1],
                           c=adata.obs['n_genes_by_counts'], s=1, alpha=0.7, cmap='viridis')
axes[1, 0].set_xlabel('UMAP_1')
axes[1, 0].set_ylabel('UMAP_2')
axes[1, 0].set_title('Number of genes')

# 线粒体基因比例
scatter3 = axes[1, 1].scatter(adata.obsm['X_umap'][:, 0], adata.obsm['X_umap'][:, 1],
                           c=adata.obs['pct_counts_mt'], s=1, alpha=0.7, cmap='viridis')
axes[1, 1].set_xlabel('UMAP_1')
axes[1, 1].set_ylabel('UMAP_2')
axes[1, 1].set_title('Mitochondrial gene percentage')

plt.tight_layout()

print("\\n✅ 聚类分析完成!")
'''

    return _run_code(code)


@mcp.tool()
def marker_genes_analysis() -> Dict[str, Any]:
    """标记基因分析代码"""
    logger.info("返回标记基因分析代码")

    code = '''
# 标记基因分析
print("\\n=== 开始标记基因分析 ===")

# 简单检查聚类是否已完成
if 'leiden' not in adata.obs.columns:
    print("⚠️ 未找到聚类结果，请先执行聚类分析")
    print("建议先运行: clustering_analysis")
else:
    # 显示聚类统计
    cluster_counts = adata.obs['leiden'].value_counts().sort_index()
    print(f"\\n聚类统计：共 {len(cluster_counts)} 个聚类")
    for cluster, count in cluster_counts.items():
        print(f"Cluster {cluster}: {count} cells")

    # 寻找每个聚类的标记基因
    print("\\n开始差异基因分析...")
    sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon')
    
    # 显示标记基因结果
    sc.pl.rank_genes_groups(adata, n_genes=5, sharey=False, show=False)
    
    # 创建标记基因热图
    sc.pl.rank_genes_groups_heatmap(adata, n_genes=3, show_gene_labels=True, show=False)
    
    # 提取前几个聚类的top基因
    if 'rank_genes_groups' in adata.uns:
        result = adata.uns['rank_genes_groups']
        groups = result['names'].dtype.names
        top_genes = {}
        
        print("\\n各聚类的top 5标记基因:")
        for group in groups:
            top_genes[group] = [result['names'][group][i] for i in range(5)]
            print(f"\\nCluster {group}:")
            for i, gene in enumerate(top_genes[group]):
                score = result['scores'][group][i]
                pval = result['pvals'][group][i]
                print(f"  {i+1}. {gene} (score: {score:.2f}, pval: {pval:.2e})")
    else:
        print("\\n⚠️ 差异基因分析结果不可用")

# 可视化一些知名的免疫细胞标记基因
known_markers = ['CD3D', 'CD3E', 'CD79A', 'CD79B',
    'CD14', 'CD68', 'FCGR3A', 'CD8A', 'CD4']
available_markers = [gene for gene in known_markers if gene in adata.var_names]

if available_markers:
    print(f"\\n可视化已知标记基因: {', '.join(available_markers)}")
    sc.pl.umap(adata, color=available_markers, ncols=3, show=False)
else:
    print("\\n未找到常见的免疫细胞标记基因")

print("\\n✅ 标记基因分析完成!")
'''

    return _run_code(code)


@mcp.tool()
def generate_analysis_report() -> Dict[str, Any]:
    """生成分析报告代码"""
    logger.info("返回分析报告生成代码")

    code = '''
# 生成分析报告
import os
print("\\n=== 生成PBMC3K数据分析报告 ===")

print("\\n" + "="*60)
print("           PBMC3K 单细胞RNA测序数据分析报告")
print("="*60)

print(f"\\n1. 数据概览:")
print(f"   - 细胞总数: {adata.n_obs:,}")
print(f"   - 基因总数: {adata.n_vars:,}")
if hasattr(adata, 'raw') and adata.raw is not None:
    print(f"   - 原始细胞数: {adata.raw.n_obs:,}")
    print(f"   - 原始基因数: {adata.raw.n_vars:,}")

if 'n_genes_by_counts' in adata.obs.columns:
    print(f"\\n2. 质量控制统计:")
    print(f"   - 每细胞平均基因数: {adata.obs['n_genes_by_counts'].mean():.0f}")
if 'total_counts' in adata.obs.columns:
    print(f"   - 每细胞平均分子数: {adata.obs['total_counts'].mean():.0f}")
if 'pct_counts_mt' in adata.obs.columns:
    print(f"   - 平均线粒体基因比例: {adata.obs['pct_counts_mt'].mean():.2f}%")

if 'leiden' in adata.obs.columns:
    print(f"\\n3. 聚类结果:")
    cluster_counts = adata.obs['leiden'].value_counts().sort_index()
    print(f"   - 识别出聚类数: {len(cluster_counts)}")
    for cluster, count in cluster_counts.items():
        percentage = count / adata.n_obs * 100
        print(f"   - Cluster {cluster}: {count} cells ({percentage:.1f}%)")
else:
    print("\\n3. 聚类结果: 未执行聚类分析")

if 'highly_variable' in adata.var.columns:
    print(f"\\n4. 高变基因:")
    print(f"   - 高变基因数量: {sum(adata.var.highly_variable):,}")
    print(
        f"   - 高变基因比例: {sum(adata.var.highly_variable)/len(adata.var)*100:.1f}%")

# 只有在有必要数据时才创建图表
if 'leiden' in adata.obs.columns and 'X_umap' in adata.obsm:
    print("\\n📊 生成综合可视化图表...")

    # 创建综合图表
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('PBMC3K Data Analysis Summary', fontsize=16, y=0.98)

    # 1. 聚类UMAP
    sc.pl.umap(adata, color='leiden',
               ax=axes[0, 0], show=False, frameon=False, legend_loc='on data')
    axes[0, 0].set_title('Cell Clusters (Leiden)')

    # 2. 总counts (如果存在)
    if 'total_counts' in adata.obs.columns:
        sc.pl.umap(adata, color='total_counts',
                   ax=axes[0, 1], show=False, frameon=False)
        axes[0, 1].set_title('Total UMI Counts')
    else:
        axes[0, 1].text(0.5, 0.5, 'Total counts\\nnot available',
                      ha='center', va='center', transform=axes[0, 1].transAxes)
        axes[0, 1].set_title('Total UMI Counts')

    # 3. 基因数量 (如果存在)
    if 'n_genes_by_counts' in adata.obs.columns:
        sc.pl.umap(adata, color='n_genes_by_counts',
                   ax=axes[0, 2], show=False, frameon=False)
        axes[0, 2].set_title('Number of Genes')
    else:
        axes[0, 2].text(0.5, 0.5, 'Gene counts\\nnot available',
                      ha='center', va='center', transform=axes[0, 2].transAxes)
        axes[0, 2].set_title('Number of Genes')

    # 4. 聚类细胞数量柱状图
    cluster_counts.plot(kind='bar', ax=axes[1, 0], color='skyblue')
    axes[1, 0].set_title('Cells per Cluster')
    axes[1, 0].set_xlabel('Cluster')
    axes[1, 0].set_ylabel('Number of Cells')
    axes[1, 0].tick_params(axis='x', rotation=0)

    # 5. QC指标分布
    if 'n_genes_by_counts' in adata.obs.columns:
        axes[1, 1].hist(adata.obs['n_genes_by_counts'],
                        bins=30, alpha=0.7, color='green')
        axes[1, 1].set_title('Genes per Cell Distribution')
        axes[1, 1].set_xlabel('Number of Genes')
        axes[1, 1].set_ylabel('Number of Cells')
    else:
        axes[1, 1].text(0.5, 0.5, 'QC data\\nnot available',
                      ha='center', va='center', transform=axes[1, 1].transAxes)
        axes[1, 1].set_title('Genes per Cell Distribution')

    # 6. 线粒体基因比例
    if 'pct_counts_mt' in adata.obs.columns:
        axes[1, 2].hist(adata.obs['pct_counts_mt'],
                        bins=30, alpha=0.7, color='red')
        axes[1, 2].set_title('Mitochondrial Gene % Distribution')
        axes[1, 2].set_xlabel('Mitochondrial Gene %')
        axes[1, 2].set_ylabel('Number of Cells')
    else:
        axes[1, 2].text(0.5, 0.5, 'MT data\\nnot available',
                      ha='center', va='center', transform=axes[1, 2].transAxes)
        axes[1, 2].set_title('Mitochondrial Gene % Distribution')

    plt.tight_layout()
    # plt.show() # 注释掉，图片会通过 _run_code 函数自动保存
else:
    print("\\n⚠️ 图表生成跳过：缺少聚类结果或UMAP坐标")
    print("建议先执行: clustering_analysis 或 dimensionality_reduction_analysis")

print(f"\\n5. 分析流程总结:")
print("   ✅ 数据加载和基本信息查看")
print("   ✅ 质量控制和细胞/基因过滤")
print("   ✅ 数据标准化和高变基因识别")
print("   ✅ 主成分分析和UMAP降维")
print("   ✅ 基于图的聚类分析")
print("   ✅ 差异基因分析")

print("\\n" + "="*60)
print("                    分析完成!")
print("="*60)

# 保存结果
output_dir = "output_results"
os.makedirs(output_dir, exist_ok=True)

# 保存AnnData对象
adata.write(f"{output_dir}/pbmc3k_processed.h5ad")
print(f"\\n📁 处理后的数据已保存到: {output_dir}/pbmc3k_processed.h5ad")

print("\\n✅ 分析报告生成完成!")
'''

    return _run_code(code)


@mcp.tool()
def complete_analysis_pipeline() -> Dict[str, Any]:
    """完整的PBMC3K分析流程"""
    logger.info("执行完整的PBMC3K分析流程")

    code = '''
# 完整的PBMC3K数据分析流程
print("\\n" + "="*80)
print("                  🧬 PBMC3K 完整分析流程")
print("="*80)

# 导入必要的库

# scanpy设置
sc.settings.verbosity = 3  # 详细输出
sc.settings.set_figure_params(dpi=80, facecolor='white')

print("\\n📁 步骤1: 数据加载...")
# 加载数据
adata = sc.read_10x_mtx(
    '{get_data_path()}',
    var_names='gene_symbols',
    cache=True
)
adata.var_names_unique()

print(f"原始数据: {adata.n_obs} 个细胞, {adata.n_vars} 个基因")

print("\\n🔍 步骤2: 质量控制...")
# 计算质控指标
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)

# 可视化质控指标
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
sc.pl.violin(adata, ['n_genes_by_counts', 'total_counts', 'pct_counts_mt'],
             jitter=0.4, multi_panel=True, ax=axes, show=False)
plt.tight_layout()

print("\\n🧹 步骤3: 数据预处理...")
# 过滤
print("过滤前:", f"{adata.n_obs} 细胞, {adata.n_vars} 基因")
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
adata = adata[adata.obs.n_genes_by_counts < 5000, :]
adata = adata[adata.obs.pct_counts_mt < 20, :]
print("过滤后:", f"{adata.n_obs} 细胞, {adata.n_vars} 基因")

# 保存原始数据
adata.raw = adata

# 归一化
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# 寻找高变基因
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
print(f"高变基因数量: {sum(adata.var.highly_variable)}")

# 可视化高变基因
sc.pl.highly_variable_genes(adata, show=False)

# 只保留高变基因
adata = adata[:, adata.var.highly_variable]

# 标准化
sc.pp.scale(adata, max_value=10)

print("\\n📊 步骤4: 降维分析...")
# PCA
sc.tl.pca(adata, svd_solver='arpack')
sc.pl.pca_variance_ratio(adata, n_comps=50, log=True, show=False)

# 计算邻居图
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=40)

# UMAP
sc.tl.umap(adata)

print("\\n🎯 步骤5: 聚类分析...")
# Leiden聚类
sc.tl.leiden(adata, resolution=0.5)

# 聚类统计
cluster_counts = adata.obs['leiden'].value_counts().sort_index()
print(f"\\n识别出 {len(cluster_counts)} 个聚类:")
for cluster, count in cluster_counts.items():
    percentage = count / adata.n_obs * 100
    print(f"  Cluster {cluster}: {count} cells ({percentage:.1f}%)")

# 可视化聚类结果
sc.pl.umap(adata, color=['leiden', 'total_counts',
           'n_genes_by_counts'], ncols=3, show=False)

print("\\n🧬 步骤6: 标记基因分析...")
# 差异基因分析
sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon')
sc.pl.rank_genes_groups(adata, n_genes=5, sharey=False, show=False)

# 提取top基因
result = adata.uns['rank_genes_groups']
groups = result['names'].dtype.names
print("\\n各聚类的top 3标记基因:")
for group in groups:
    top_genes = [result['names'][group][i] for i in range(3)]
    print(f"Cluster {group}: {', '.join(top_genes)}")

print("\\n🏷️ 步骤7: 已知标记基因可视化...")
# 可视化已知标记基因
known_markers = ['CD3D', 'CD3E', 'CD79A', 'CD79B',
    'CD14', 'CD68', 'FCGR3A', 'CD8A', 'CD4']
available_markers = [gene for gene in known_markers if gene in adata.var_names]

if available_markers:
    print(f"可视化已知标记基因: {', '.join(available_markers)}")
    sc.pl.umap(adata, color=available_markers, ncols=3, show=False)
else:
    print("未找到常见的免疫细胞标记基因")

print("\\n📋 步骤8: 生成综合报告...")
# 创建综合分析图表
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('PBMC3K Complete Analysis Results', fontsize=16, y=0.98)

# 聚类结果
sc.pl.umap(adata, color='leiden',
           ax=axes[0, 0], show=False, frameon=False, legend_loc='on data')
axes[0, 0].set_title('Cell Clusters (Leiden)')

# 总counts
sc.pl.umap(adata, color='total_counts',
           ax=axes[0, 1], show=False, frameon=False)
axes[0, 1].set_title('Total UMI Counts')

# 基因数量
sc.pl.umap(adata, color='n_genes_by_counts',
           ax=axes[0, 2], show=False, frameon=False)
axes[0, 2].set_title('Number of Genes')

# 聚类细胞数量
cluster_counts.plot(kind='bar', ax=axes[1, 0], color='skyblue')
axes[1, 0].set_title('Cells per Cluster')
axes[1, 0].set_xlabel('Cluster')
axes[1, 0].set_ylabel('Number of Cells')

# QC指标分布
axes[1, 1].hist(adata.obs['n_genes_by_counts'],
                bins=30, alpha=0.7, color='green')
axes[1, 1].set_title('Genes per Cell Distribution')
axes[1, 1].set_xlabel('Number of Genes')
axes[1, 1].set_ylabel('Number of Cells')

# 线粒体基因比例
axes[1, 2].hist(adata.obs['pct_counts_mt'], bins=30, alpha=0.7, color='red')
axes[1, 2].set_title('Mitochondrial Gene % Distribution')
axes[1, 2].set_xlabel('Mitochondrial Gene %')
axes[1, 2].set_ylabel('Number of Cells')

plt.tight_layout()

print("\\n💾 步骤9: 保存结果...")
# 保存结果
output_dir = "output_results"
os.makedirs(output_dir, exist_ok=True)

# 保存AnnData对象
adata.write(f"{output_dir}/pbmc3k_complete_analysis.h5ad")
print(f"分析结果已保存到: {output_dir}/pbmc3k_complete_analysis.h5ad")

print("\\n" + "="*80)
print("                      ✅ 完整分析流程完成!")
print("="*80)

print("\\n📊 分析总结:")
print(f"  📁 最终数据: {adata.n_obs} 细胞, {adata.n_vars} 基因")
print(f"  🎯 聚类数量: {len(cluster_counts)} 个")
print(f"  🧬 高变基因: {sum(adata.var.highly_variable)} 个")
print(f"  💾 结果文件: {output_dir}/pbmc3k_complete_analysis.h5ad")

print("\\n🎉 PBMC3K单细胞RNA测序数据分析完成！")
'''

    return _run_code(code)


@mcp.tool()
def health_check() -> Dict[str, Any]:
    """健康检查"""
    logger.info("MCP服务器健康检查")
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "RNA分析MCP服务器运行正常"
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 启动RNA分析MCP服务器...")
    logger.info("=" * 60)
    logger.info("🔧 [服务配置] 传输协议: SSE")
    logger.info("🌐 [服务地址] http://localhost:8000")
    logger.info("📊 [图片目录] tmp/plots/")
    logger.info("🛠️ [可用工具] 8个RNA分析工具")

    # 检查数据路径
    data_path = get_data_path()
    if os.path.exists(data_path):
        logger.info(f"✅ [数据路径] PBMC3K数据路径存在: {data_path}")
    else:
        logger.warning(f"⚠️ [数据路径] PBMC3K数据路径不存在: {data_path}")

    logger.info("=" * 60)

    # 启动MCP服务器
    mcp.run(transport="sse", host=config.host, port=config.mcp_port)

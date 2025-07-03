import scanpy as sc
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 设置全局参数
sc.settings.verbosity = 2
sc.settings.set_figure_params(dpi=80, dpi_save=150)
# 设置matplotlib图形大小
import matplotlib.pyplot as plt
plt.rcParams['figure.figsize'] = (6, 6)

# 读取10X格式的数据
data_path = 'filtered_gene_bc_matrices/hg19/'
adata = sc.read_10x_mtx(data_path, var_names='gene_symbols', cache=True)
adata.var_names_make_unique()

# 基本信息
print(adata)

# 质控指标计算
adata.var['mt'] = adata.var_names.str.startswith('MT-')  # 线粒体基因
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)

# 质控可视化
sc.pl.violin(adata, ['n_genes_by_counts', 'total_counts', 'pct_counts_mt'],
             jitter=0.4, multi_panel=True)

# 过滤低质量细胞
adata = adata[adata.obs.n_genes_by_counts < 2500, :]
adata = adata[adata.obs.pct_counts_mt < 5, :]

# 标准化 + Log 转换
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# 筛选高变基因
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
sc.pl.highly_variable_genes(adata)

# 保留高变基因
adata = adata[:, adata.var.highly_variable]

# 标准化 & PCA
sc.pp.scale(adata, max_value=10)
sc.tl.pca(adata, svd_solver='arpack')
sc.pl.pca_variance_ratio(adata, log=True)

# 邻接图 + UMAP + 聚类
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=40)
sc.tl.umap(adata)
sc.tl.leiden(adata)

# 可视化 UMAP 聚类结果
sc.pl.umap(adata, color=['leiden'], legend_loc='on data')

# 差异表达基因分析
sc.tl.rank_genes_groups(adata, 'leiden', method='t-test')
sc.pl.rank_genes_groups(adata, n_genes=5, sharey=False)

# 小提琴图可视化 top 基因
top_genes = adata.uns['rank_genes_groups']['names']['0'][:3]
sc.pl.violin(adata, top_genes, groupby='leiden', rotation=90)

# 常见细胞marker辅助注释
marker_genes = ['CD3D', 'CD14', 'MS4A1', 'GNLY', 'NKG7', 'CD8A']
sc.pl.dotplot(adata, marker_genes, groupby='leiden')

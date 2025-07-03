import scanpy as sc

# 读取 10X 表达数据（你的路径）
adata = sc.read_10x_mtx(
    "filtered_gene_bc_matrices/hg19",
    var_names="gene_symbols",
)

print(adata.shape)  # 通常是 ~2700 x 3000

# 只保留前 500 个细胞作为测试分析
adata = adata[:500, :]

# 基础分析流程
sc.pp.calculate_qc_metrics(adata, inplace=True)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=1000)
adata = adata[:, adata.var.highly_variable]
sc.pp.scale(adata, max_value=10)
sc.tl.pca(adata)
sc.pp.neighbors(adata)
sc.tl.umap(adata)
sc.tl.leiden(adata)

# 可视化结果
sc.pl.umap(adata, color=['leiden'])

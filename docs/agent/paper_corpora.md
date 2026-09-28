# Agent 论文库与本地联调

本项目保留两套论文库，分别服务于“可复现评测”和“近期论文 Agent 演示”。两套目录不能混用，也不能用近期论文替换课程评测基准。

## 1. 课程基准库

目录：`data/samples/papers/`

这 5 篇论文与仓库现有 `data/samples/eval/transformer_backend_eval_20qa.jsonl` 的题目、页码和文档 ID 对应。下载时应保持文件名和版本不变；如果 PDF 二进制内容发生变化，文档 SHA-256 也会变化，现有 QA 的 `relevant_document_ids` 就需要重新生成，不能手工修改。

| 文件 | 年份 | 主题 | 来源 |
| --- | ---: | --- | --- |
| `2203.00555v1.pdf` | 2022 | DeepNet / DeepNorm | <https://arxiv.org/abs/2203.00555> |
| `2103.00112v3.pdf` | 2021 | Transformer in Transformer（TNT） | <https://arxiv.org/abs/2103.00112> |
| `2009.06732v3.pdf` | 2022（v3 更新） | Efficient Transformers 综述 | <https://arxiv.org/abs/2009.06732> |
| `2006.16236v3.pdf` | 2020 | 线性 Transformer / Transformers are RNNs | <https://arxiv.org/abs/2006.16236> |
| `1-s2.0-S2666651022000146-main.pdf` | 2022 | Transformer 综述 | <https://doi.org/10.1016/j.aiopen.2022.10.001> |

这套库用于后端成员的 20 条 QA、向量检索/BM25/RRF/Reranker 对比以及课程报告中的可复现实验。

## 2. Agent 近期演示库

目录：`data/samples/papers_recent/`

该目录已加入 `.gitignore`，只在本机保存 PDF，不提交到 GitHub。建议使用以下 2023—2025 年论文作为 Agent 的新论文演示语料：

| 建议文件 | 年份 | 主题 | 来源 |
| --- | ---: | --- | --- |
| `2307.08691.pdf` | 2023 | FlashAttention-2 | <https://arxiv.org/abs/2307.08691> |
| `2307.08621.pdf` | 2023 | RetNet / Retentive Network | <https://arxiv.org/abs/2307.08621> |
| `2407.08608.pdf` | 2024 | FlashAttention-3 | <https://arxiv.org/abs/2407.08608> |
| `2412.19437.pdf` | 2024 | DeepSeek-V3 Technical Report | <https://arxiv.org/abs/2412.19437> |
| `2505.09388.pdf` | 2025 | Qwen3 Technical Report | <https://arxiv.org/abs/2505.09388> |

这些论文不是现有 20 条 QA 的替代品，也不应被写入课程基准 QA 的相关文档 ID。它们用于展示：用户提出近期论文问题时，Agent 能调用 `knowledge_retrieval`，经过后端 `hybrid_rerank`（向量 + BM25 + RRF + Reranker），再由 DeepSeek 生成带真实 Citation 的回答。

## 3. 下载与建索引

在仓库根目录执行。下面的下载只写入 Git 忽略目录：

```bash
mkdir -p data/samples/papers data/samples/papers_recent

curl -L --fail --retry 2 https://arxiv.org/pdf/2203.00555v1 -o data/samples/papers/2203.00555v1.pdf
curl -L --fail --retry 2 https://arxiv.org/pdf/2103.00112v3 -o data/samples/papers/2103.00112v3.pdf
curl -L --fail --retry 2 https://arxiv.org/pdf/2009.06732v3 -o data/samples/papers/2009.06732v3.pdf
curl -L --fail --retry 2 https://arxiv.org/pdf/2006.16236v3 -o data/samples/papers/2006.16236v3.pdf

curl -L --fail --retry 2 https://arxiv.org/pdf/2307.08691 -o data/samples/papers_recent/2307.08691.pdf
curl -L --fail --retry 2 https://arxiv.org/pdf/2307.08621 -o data/samples/papers_recent/2307.08621.pdf
curl -L --fail --retry 2 https://arxiv.org/pdf/2407.08608 -o data/samples/papers_recent/2407.08608.pdf
curl -L --fail --retry 2 https://arxiv.org/pdf/2412.19437 -o data/samples/papers_recent/2412.19437.pdf
curl -L --fail --retry 2 https://arxiv.org/pdf/2505.09388 -o data/samples/papers_recent/2505.09388.pdf
```

课程基准库的第五篇 ScienceDirect PDF 可能需要从[开放获取文章页](https://www.sciencedirect.com/science/article/pii/S2666651022000146)
或[PDF 阅读器](https://www.sciencedirect.com/sdfe/reader/pii/S2666651022000146/pdf)手动下载，并保存为准确的文件名：
`data/samples/papers/1-s2.0-S2666651022000146-main.pdf`。自动化请求可能被站点返回 403；不要用网页 HTML、摘要页面或自行重新导出的 PDF 代替论文文件。

后端的索引脚本会把向量索引写入同样被忽略的 `data/indexes/`：

```bash
python scripts/build_index.py data/samples/papers/*.pdf
python scripts/build_index.py data/samples/papers_recent/*.pdf
```

Agent 运行时仍需要后端成员把内存中的 `HybridRetriever` 和已加载的 `Document` 对象注入 `build_deepseek_rag_agent_service`。`build_index.py` 负责持久化向量索引，但不会替代 Agent 运行时的 BM25、RRF 或 Reranker 组装。

## 4. 核对规则

- `git status --short --ignored` 中，论文应显示为 `!! data/samples/papers_recent/`，不能出现 `??` 或 `A`。
- 课程基准库的 SHA-256 必须与现有 QA 使用的文档 ID 一致；不一致时先确认 PDF 版本，再决定是否重建 QA，不能伪造哈希。
- 论文内容、页码和 Citation 由后端真实返回；Agent 不根据文件名或模型回答猜测引用。
- DeepSeek Key 只写入本地 `.env`，论文 PDF、索引、Key 都不进入提交。

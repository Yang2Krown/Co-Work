# PDF loader and embedding model experiment

以下数据均来自 2026-09-13 的真实运行，使用 Python 3.11.16。原始 JSON 输出
已原样保存于 [results/pdf_loaders.json](results/pdf_loaders.json) 和
[results/embedding_models.json](results/embedding_models.json)；未保存模型权重、
索引或本地缓存。

## PDF loader comparison

Corpus：`data/samples/papers/` 中 5 篇 Transformer 论文；每个 parser 都处理
全部 5 篇。成功率均为 5/5（100%）。

| parser | average latency (ms) | average chars | non-empty pages | extraction anomaly observations |
| --- | ---: | ---: | ---: | --- |
| PyPDF2 | 397.14 | 92515.4 | 114/114 | 4/5 had control-character observations |
| pdfplumber | 1570.90 | 85800.6 | 114/114 | none from deterministic heuristic |
| PyMuPDF | 131.11 | 93070.2 | 114/114 | 3/5 had low-count control-character observations |

每条原始记录还包含文件名、页数、字符数、UTF-8 文本 SHA-256 和错误字段。
异常标记只报告空文本、替换字符和控制字符，不等价于人工版面质量结论。
PyMuPDF 在本次 corpus 上最快，字符总量最高（465351），且全部成功，因此继续
作为默认 parser；涉及复杂版面时仍应保留 parser 对比记录。

## Embedding model comparison

固定同一 corpus、同一份 20 QA、`structure/512/64`、Top-K 5 和
`InMemoryVectorStore`，只运行 vector retrieval。

| model | resolved model | dim | cold load (ms) | first batch (ms) | warm batch (ms) | warm items/s | Hit@5 | MRR | avg query (ms) | max RSS delta (bytes) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| m3e-base | `moka-ai/m3e-base` | 768 | 12167.04 | 39507.48 | 41993.39 | 25.69 | 0.7000 | 0.5433 | 16.88 | 620199936 |
| bge-large-zh | `BAAI/bge-large-zh-v1.5` | 1024 | 218330.23 | 101864.55 | 184510.65 | 5.85 | 0.7500 | 0.5725 | 47.79 | 1303773184 |

两模型均真实加载成功。bge-large-zh 的 Hit@5/MRR 较高，但本机上的 cold、warm
和资源成本都明显更高；因此质量优先推荐 bge-large-zh，资源或交互延迟优先可
选择 m3e-base。本轮不擅自修改 `config/backend.yaml` 的默认模型。

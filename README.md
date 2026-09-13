# Co-Work

生产实习小组作业。成员 A 负责后端文档处理、检索和 RAG 生成层；本仓库
当前后端实现按 `BACKEND_REQUIREMENTS.md` 的 M0–M7 里程碑组织。

## Backend quick start

以下命令均在仓库根目录执行。项目优先使用 Python 3.11：

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

运行默认测试（不下载真实大模型、不调用外部 LLM API）：

```bash
.venv/bin/python -m pytest -q
```

安装依赖后，使用文档建立或更新向量索引：

```bash
.venv/bin/python scripts/build_index.py path/to/paper.pdf --config config/backend.yaml
```

`build_index.py` 使用配置中的 loader、chunking、embedding 和 vector store
设置，并维护增量索引 manifest。当前后端提供 Chroma、FAISS 和内存向量存储，
检索模式由 `src/backend/retrieval/` 中的接口组合：

```text
vector
hybrid          vector + BM25 + RRF
hybrid_rerank  hybrid + reranker
```

使用真实 JSONL 评测集可运行：

```bash
.venv/bin/python scripts/evaluate_retrieval.py \
  path/to/paper.pdf \
  --evaluation path/to/retrieval.jsonl \
  --output /tmp/retrieval-results.json
```

评测脚本只根据提供的真实 JSONL 计算 Hit@5/MRR，不会伪造指标。真实 embedding、
Chroma、FAISS 和 reranker smoke test 是独立脚本，不属于默认 pytest：

```bash
.venv/bin/python scripts/smoke_test_retrieval.py \
  --embedding-model m3e-base \
  --reranker-model bge-reranker-base \
  --output /tmp/retrieval-smoke.json
```

## RAG configuration

RAG 参数位于 `config/backend.yaml`，包括 LLM provider/model、API endpoint、
超时、上下文上限、生成参数、低相关阈值、缓存和 fallback 开关。项目不使用
`python-dotenv`。复制环境模板并填写本地密钥后，在 macOS/Linux 中可以使用
`source .env`，或显式导出变量：

```bash
cp .env.example .env
source .env
# 或：export OPENAI_API_KEY=your-api-key
```

当前 OpenAI-compatible client 读取 `OPENAI_API_KEY`。API key 不写入 YAML、
代码、日志或 Git。

RAG 核心入口是：

```python
from src.backend.rag import RAGService

response = rag_service.answer("我的问题", top_k=5)
for fragment in rag_service.stream_answer("我的问题", top_k=5):
    print(fragment, end="", flush=True)
```

需要在流式响应中传递引用时，使用向后兼容的结构化事件接口：

```python
for event in rag_service.stream_answer_events("我的问题", top_k=5):
    # event.event: metadata | token | end | error
    consume(event)
```

首个 `metadata` 事件包含从检索结果复制的真实 `citations`、
`retrieved_chunks` 和 `request_id`。

`RAGResponse` 包含 `answer`、`citations`、`retrieved_chunks`、`latency_ms`、
可获得的 `token_usage`、`fallback_used` 和错误时的 `error`。

## Backend documentation

Final Experiment 使用 5 篇 Transformer 论文和 20 条人工核验 QA，运行环境为
Python 3.11.16；真实结果和原始 JSON 见以下文档与链接。

- [架构说明](docs/backend/architecture.md)
- [集成契约](docs/backend/integration_contract.md)
- [分块实验](docs/backend/chunking_experiment.md)
- [检索实验](docs/backend/retrieval_experiment.md)
- [PDF Loader 与 Embedding 对比实验](docs/backend/model_and_loader_experiment.md)

实验原始 JSON：
[PDF loaders](docs/backend/results/pdf_loaders.json) ·
[chunking](docs/backend/results/chunking.json) ·
[embedding models](docs/backend/results/embedding_models.json) ·
[retrieval](docs/backend/results/retrieval.json)

后端不负责 Streamlit/Gradio 页面、Agent ReAct 循环、工具路由或最终系统级评测。

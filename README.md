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

## Agent quick start

Agent 模块位于 `src/agent/`，不改写 `src/backend/`。默认注册八个工具：知识库
RAG、论文元信息、论文对比、关键词提取、论文结构化摘要、当前时间、安全计算器
和可注入的联网搜索。没有注入搜索函数时，联网搜索保持关闭。

Agent 默认通过后端已有的 OpenAI-compatible client 连接 DeepSeek，当前配置为
`https://api.deepseek.com`、`deepseek-v4-flash` 和 `DEEPSEEK_API_KEY`。真实调用前只在
本机配置密钥，不要把密钥写入代码、YAML 或 Git：

```bash
cp .env.example .env
# 编辑 .env，把 your-deepseek-api-key-here 替换为本地 Key
source .env
```

如果后端已经构造好了 `RAGService`，可以直接注入；如果只有后端的混合检索器，
推荐使用组合工厂，让 Agent 和 RAG 共用同一个 DeepSeek client，并强制使用后端的
`hybrid_rerank`（向量检索 + BM25 + RRF + Reranker）：

```python
from src.agent import build_deepseek_rag_agent_service, create_app

agent_service = build_deepseek_rag_agent_service(
    retriever=hybrid_retriever,
    documents=ingestion_result,
)
app = create_app(agent_service)
```

若已有后端 `RAGService`，并且它已经使用了同一个 DeepSeek client，则使用
`build_agent_service(llm_client=rag_service.llm_client, rag_service=rag_service)`。
两种方式都只通过集成边界复用后端检索实现，不在 Agent 中重复编写 BM25、RRF 或
Reranker。

客户端构造和模块导入不会发起网络请求；只有需要 ReAct、RAG 生成或模型摘要时才会读取
`DEEPSEEK_API_KEY` 并调用 DeepSeek。计算器、当前时间、关键词提取等确定性路由可在无
Key 时离线运行。传入的 `rag_service` 或 `hybrid_retriever` 仍由后端负责；本模块不改写队友的
RAG 实现。

接口为 `GET /healthz`、`POST /api/agent/chat` 和 `POST /api/agent/chat/stream`。
ReAct 协议、会话记忆、真实引用边界和集成方式见
[Agent 架构说明](docs/agent/architecture.md) 与 [Agent 集成说明](docs/agent/integration.md)。
论文基准库、近期论文演示库和本地索引步骤见
[Agent 论文库说明](docs/agent/paper_corpora.md)；论文 PDF、索引和 API Key 均不提交到 Git。

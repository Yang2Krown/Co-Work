# Agent 系统联调说明

## 构造服务

后端成员完成混合检索器后，推荐使用组合工厂。它会使用同一个 DeepSeek client 构造
RAG 和 Agent，并固定 `hybrid_rerank`：向量检索 + BM25 + RRF + Reranker。

```python
from src.agent import build_deepseek_rag_agent_service, create_app

agent_service = build_deepseek_rag_agent_service(
    retriever=hybrid_retriever,
    documents=ingestion_result,
)
app = create_app(agent_service)
```

如果后端已经构造好了 `RAGService`，则使用：

```python
from src.agent import build_agent_service

agent_service = build_agent_service(
    llm_client=rag_service.llm_client,
    rag_service=rag_service,
    documents=ingestion_result,
)
```

这里显式复用 `rag_service.llm_client`；集成层会拒绝 Agent 与 RAG 使用不同的
client，避免两套模型配置或两份 Token 统计。

两种方式都不改写 `src/backend`，Agent 只调用后端 `RAGService.answer`，并复制其中
真实的 `citations`、`retrieved_chunks`、`retrieval_mode` 和检索延迟。
当前后端契约只保证 `RAGResponse.latency_ms`；如果后端未来提供独立的
`retrieval_latency_ms`，Agent 会优先使用它，并在结果中标注 `latency_source`。

本地先准备模型密钥与 DashScope Embedding 端点：

```bash
# 编辑仓库根目录的 .env：填入 DEEPSEEK_API_KEY、DASHSCOPE_API_KEY 和工作空间对应的 DASHSCOPE_API_BASE
# 程序会自动读取 .env；不要在终端执行 export 或 source。
```

`build_deepseek_agent_service`、`build_deepseek_rag_agent_service` 和 `create_app` 不在 import 或构造阶段发起网络请求，
第一次需要 ReAct、RAG 生成或摘要的请求才会读取 `DEEPSEEK_API_KEY`。当前默认模型是
`deepseek-v4-flash`，地址是 `https://api.deepseek.com`。确定性工具不依赖 Key；传入的
`rag_service` 仍按 `docs/backend/integration_contract.md` 由后端成员负责其自身配置。
API key 不随请求传给 Agent，也不得写入 YAML、代码、日志或提交到 Git。

### DashScope Embedding 与建库

项目默认不下载本地 Embedding 权重，而是使用阿里云百炼的 OpenAI-compatible
Embedding 接口。`config/backend.yaml` 默认配置为：

```yaml
embedding:
  provider: dashscope
  model_name: text-embedding-v4
  api_base_env: DASHSCOPE_API_BASE
  api_key_env: DASHSCOPE_API_KEY
```

其中 `DASHSCOPE_API_BASE` 必须是百炼控制台中当前地域、当前工作空间的
OpenAI-compatible Base URL，例如
`https://<WorkspaceId>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。它和 Key
均只保存在本地 `.env`；不得把真实工作空间信息或 Key 写入仓库。

准备好论文 PDF 后建立（或增量更新）向量索引：

```bash
python3 scripts/build_index.py data/samples/papers/*.pdf
```

建库时每个分块会调用 DashScope Embedding，向量写入配置的 Chroma 目录；查询时使用
同一个模型生成查询向量，因此不能在同一索引上任意切换 Embedding 模型或维度。BM25
索引由同批文档分块在运行时构建，不需要 API Key。

## HTTP 接口

### `GET /healthz`

返回模块状态、已注册工具名、依赖状态和进程内指标。默认不探测 LLM、向量库或互联网；
只有构造服务时显式注入 `health_check` 才会执行依赖检查。

### `POST /api/agent/chat`

请求：

```json
{"session_id":"demo","message":"请查知识库回答问题","metadata":{}}
```

论文工具使用请求的 `metadata` 传递已确认的目录 ID，不从自然语言或文件名猜测：

```json
{"session_id":"paper-demo","message":"请读取论文元信息","metadata":{"paper_id":"doc-001"}}
{"session_id":"paper-demo","message":"比较两篇论文","metadata":{"paper_a":"doc-001","paper_b":"doc-002"}}
{"session_id":"paper-demo","message":"总结这篇论文","metadata":{"paper_id":"doc-001"}}
```

知识库请求可额外传 `top_k`（1–20）；联网搜索可传 `max_results`（1–10），但只有
显式注入 `search_fn` 后才会执行。

响应是 `AgentRunResult`，包含 `answer`、`citations`、`trace`、`iterations`、
`status`、可获得的 `token_usage` 和结构化 `error`。`status` 为 `completed`、
`failed` 或 `max_iterations`。

### `POST /api/agent/chat/stream`

请求体与普通接口相同，响应为 `text/event-stream`。每个事件形如：

```text
event: tool_finished
data: {"event":"tool_finished","run_id":"...","session_id":"demo","payload":{"result":{"tool_name":"knowledge_retrieval","ok":true}}}

```

客户端应处理 `run_started`、`thought`、`tool_started`、`tool_finished`、
`final`、`error` 和 `run_finished`，并允许工具失败后继续收到最终结构化结果。
正常顺序是 `run_started → thought → tool_started/tool_finished → final → run_finished`；
失败或达到上限时，`final` 可能被 `error` 替代，但最后仍会有 `run_finished`。

## 安全与默认边界

- Agent 请求不携带 API key；密钥只由后端 LLM client 从环境变量读取。
- 计算器只接受数字和白名单算术 AST，不使用 `eval`。
- 联网搜索默认关闭；只有在服务构造时显式传入 `search_fn` 才能执行。
- `/healthz` 默认不发起网络探测；组合工厂会报告 LLM Key 是否存在、RAG 是否注入以及
  `hybrid_rerank` 模式，真实连通性仍通过显式注入的 `health_check` 检查。
- 传入真实 `health_check` 时，才执行调用方提供的 LLM/RAG 检查。
- 后端 RAG 返回的引用是唯一来源；没有页码时保持 `null`。

## 本地验证

```bash
PYTHONPYCACHEPREFIX=/tmp/cowork-pycache python3 -m compileall -q src/agent
```

真实模型、真实论文索引和外部搜索应作为单独集成环境验证，不能把静态编译结果
当作线上模型质量、延迟或工具成功率。

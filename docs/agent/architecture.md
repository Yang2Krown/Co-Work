# Co-Work Agent 架构说明

## 范围

`src/agent/` 是独立的 Agent 模块，复用后端已经提供的 `RAGService`、
`LLMClient` 和 `RAGPrompt` 边界，但不修改 `src/backend/`。本阶段实现 Agent
核心与薄层联调，不包含 Streamlit/Gradio 页面、最终 50+ QA 集、Docker 或演示
PPT。

模型参数位于 `config/agent.yaml`，默认使用 DeepSeek 的 OpenAI-compatible 接口。
该文件只保存 `api_base`、模型名和环境变量名，不保存密钥；真实 Key 由本地的
`DEEPSEEK_API_KEY` 提供。

## 请求流程

```text
AgentRequest
    │
    ├─ IntentRouter ── deterministic intents ── ToolRegistry
    │
    └─ JSON ReAct loop
         ├─ LLMClient.generate(RAGPrompt)
         ├─ parse tool_call/final
         ├─ one or more tools (ThreadPoolExecutor)
         ├─ structured Observation + AgentTraceStep
         └─ grounded final answer + backend citations
```

每个 `session_id` 对应一个内存会话，并持有独立锁；同一会话的请求不会交叉
写入，不同会话可以并行。消息数或粗略 token 估算超过阈值后，旧消息通过可注入
摘要回调压缩，仅保留最近窗口。本阶段的 `SessionStore` 是可替换接口，未引入
数据库持久化。

## JSON ReAct 协议

模型每轮只能返回一个 JSON 对象：

```json
{"type":"tool_call","thought":"先查证据","calls":[{"name":"knowledge_retrieval","arguments":{"query":"问题"}}]}
```

或：

```json
{"type":"final","answer":"根据证据回答","citation_ids":[1]}
```

解析器支持一次有限修复；非法 JSON、未知工具、工具异常、超时、重复动作和
最大迭代都会转化为结构化 Observation 或 `AgentRunResult`，不会让 API 直接崩溃。

## 八个工具

| 工具 | 行为 |
| --- | --- |
| `knowledge_retrieval` | 调用注入的后端 `RAGService.answer`，复用向量 + BM25 + RRF + Reranker，并复制真实 `Citation` 和检索片段 |
| `paper_metadata` | 从文档元数据和前置文本读取可验证元信息，不返回全文 |
| `paper_compare` | 对两个目录记录进行结构化字段比较 |
| `keyword_extract` | 本地正则与词频提取，不访问模型 |
| `paper_summary` | 使用 DeepSeek 结构化摘要器，失败时回退到不编造内容的抽取式摘要 |
| `current_time` | 使用注入时钟或本地时钟 |
| `calculator` | AST 白名单算术；拒绝名称、函数调用和其他 Python 表达式 |
| `web_search` | 只有显式注入 `search_fn` 才启用，默认可解释地关闭 |

Agent 不从模型文本猜测文件名、页码或引用。最终引用的文件、页码和 chunk ID
全部来自后端 `RAGResponse.citations`；多个 RAG 调用仅重新分配本次运行内的展示
编号，不改变来源字段。

`hybrid_rerank` 的具体向量检索、BM25、RRF 和 Reranker 均由 `src/backend` 负责，
Agent 只消费统一的 `RAGResponse`，不复制检索算法。

## 可观测事件

`AgentService.stream` 按顺序发出 `run_started`、`thought`、工具开始/结束、
`final` 或 `error`，最后发出带完整 `AgentRunResult` 的 `run_finished`。普通
`run` 只是消费同一事件流并返回最终结构。`AgentMetrics` 记录运行次数、状态、
迭代次数、累计模型 token usage、每个工具的调用/成功率/延迟，以及 RAG 调用的
检索延迟和返回片段数；每轮 `AgentTraceStep` 保留对应模型 usage。`/healthz` 可
返回这些进程内指标，但默认不主动探测外部服务。

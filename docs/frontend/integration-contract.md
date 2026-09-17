# 前端集成接口契约

应用入口为 `src.application.Application(root)`。所有路径属于本地单人工作区；方法返回 Python dict 或标识字符串。与现有 HTTP 接口不冲突。代码中的 Pydantic 类型是字段结构的最终来源。

## DeepSeek 组合边界

`compose` 读取 Agent LLM 配置，要求主机为 `api.deepseek.com`、密钥环境变量为 `DEEPSEEK_API_KEY`。调用现有 `build_deepseek_rag_agent_service`；通过可选 `client_wrapper` 在构造 RAG、摘要回调、Agent 前包裹同一个 client。Agent 暴露 `rag_service`，供直接问答使用。

`agent.llm_client is rag.llm_client` 必须成立。后端独立 `config/backend.yaml` 的 provider/model/API 不参与 UI 的 client 选择；其中 chunk、retrieval、generation、cache 配置仍复用。工厂与导入不发网络请求。

SafeClient 在错误到达 RAG 日志和 Agent trace 前移除供应商原始响应，保留鉴权失败、限流、超时、缺 Key 和通用服务错误分类。前端无密钥输入框、请求字段或数据库字段。联网搜索未注入时不可用。

## 公共方法

| 方法 | 输入 | 返回与错误 |
| --- | --- | --- |
| `list_documents()` | 无 | DocumentRecord 列表 |
| `submit_import(files)` | `list[tuple[str,bytes]]` | job_id；类型/大小/数量不合法抛 ValueError，校验整批后才写文件 |
| `get_job(job_id)` | 标识 | ImportJob dict 或 None |
| `retry_import(job_id, document_ids)` | 原任务失败文件 ID | 新 job_id；不允许重试无关文件 |
| `delete_document(document_id)` | 真实目录 ID | job_id；后台完成所有索引同步后标记成功 |
| `repair()` | 无 | job_id；完成中断删除、清理失败导入、恢复运行快照 |
| `create_conversation(mode)` | rag / agent | Conversation dict |
| `list_conversations()` | 无 | 按创建时间倒序 |
| `get_conversation(id)` | 标识 | Conversation + 按时间排序的 messages |
| `delete_conversation(id)` | 标识 | 删除会话、消息、运行及 Agent 记忆；忙时拒绝 |
| `start_turn(id,message,metadata)` | 1–8000 字符非空文本 | run_id；同步预留操作门，重复提交拒绝 |
| `read_events(run_id,cursor=0)` | 已消费数量 | `{events,cursor,status,error}`；只返回新增事件 |
| `get_status()` | 无 | provider、model、配置、知识库、busy、metrics、最近探测结果 |
| `probe_dependencies()` | 无 | 后台执行 DeepSeek 小额生成 + 本地检索；结果写入状态 |
| `close()` | 无 | 等待工作线程结束并关闭 SQLite |

### 持久化类型

- DocumentRecord：document_id、file_name、size、path、status、chunk_count、error、解析后的 Document。
- ImportJob：job_id、status、stage、total、completed、逐文件 items、error。跳过计入已处理数，不能把文件数进度称为 token/embedding 内部进度。
- Conversation：conversation_id、mode、title、created_at。
- MessageRecord：message_id、conversation_id、run_id、role、content、status、citations、retrieved_chunks、trace、token_usage、error、latency_ms、created_at。
- RunRecord：run_id、conversation_id、mode、status、events、metadata、error、created_at。

SQLite 存储 JSON 记录并启用 WAL，单连接通过 RLock 保护。Agent 会话内锁下保存 messages 和 summary；不通过重新播放历史用户消息恢复上下文。

## 文档状态与一致性

`pending → processing → ready | failed`；删除先置 `deleting`。原文件按内容 SHA-256 目录保存，文件名去除路径成分。支持 .pdf/.docx/.txt/.md；1–20 个文件，单文件 (0,50MiB]。

后台采用后端 load_file、chunk_document、IncrementalIndex 和已有 VectorStore。新服务快照重建 BM25 与论文目录，保留已生成向量。持久化 manifest 用于后续增量跳过；更新后替换 Agent/RAG 快照并改变缓存版本。中断或异常不向用户假报成功。

导入部分失败返回 partial，只重试失败文件。索引写入途中失败尝试移除该文档向量，失败时保留 dirty。删除操作移除向量及 manifest、重建检索快照后删除原文件与登记。原文件无法删除也保持需要修复。

## 运行与事件

UI 不直接驱动模型生成器。单工作线程驱动生成器，把事件和回答快照持续写入 SQLite。页面轮询读取，重绘不调用 start_turn。当前应用一次只允许一个操作，确保知识库更新和检索互斥。

### RAG

- metadata：保存真实 citations、retrieved_chunks；空列表保持为空。
- token：逐片段追加文本，是真实供应商流，不做延迟动画。
- error：保存错误但保留已生成文本。
- end：终止；存在 error 为 failed，否则 completed。
- 未出现 end：标记 interrupted；不自动重放。

引用编号只在当前回答内有效。默认 top_k=5。直接 RAG 不具有多轮语义记忆。现有 RAG 流式接口未提供 Token 使用量，也未使用 answer() 的语义缓存；界面不伪造这些指标。Agent 的 knowledge_retrieval 调用 answer() 可复用语义缓存。

### Agent

支持 run_started、thought、tool_started、tool_finished、final、error、run_finished。

保留 run_id、session_id、step_index、tool_name、payload，工具依 call_id 关联，不依赖完成顺序。tool_finished 的失败不是运行终止。final 可以提前呈现答案；run_finished.payload.result 是最终权威结果，覆盖答案、引用、trace、usage、status、error。最终状态支持 completed、failed、max_iterations。没有 run_finished 则为 interrupted。

工具 observations 中的真实 retrieved_chunks 保留为引用快照。摘要使用 metadata.paper_id；对比使用 paper_a/paper_b，界面只能选择已就绪目录 ID，不从文件名猜测。

## 恢复、错误与可观测性

进程启动把 queued/running 的任务、运行和消息标记为 interrupted。用户主动重试会创建新 run，保留旧失败记录；论文工具重试保留 metadata。历史引用保留，即使原文件删除也不篡改以前的答案。

健康摘要不主动探测。连接检查可能计费，按钮旁明确提示。空库时显示未验证检索模型，而不是检查通过。工具指标为当前进程统计；历史请求数与回答耗时来自 SQLite。Token 缺失是未提供；RAG 内 latency_source 区分 backend_response_latency 与 backend_retrieval_latency。无标注数据不能生成 Hit@5/MRR。

# Co-Work 后端开发强约束需求文档

> 文件建议位置：仓库根目录 `BACKEND_REQUIREMENTS.md`  
> 适用仓库：`https://github.com/Yang2Krown/Co-Work.git`  
> 适用角色：成员 A / Backend 后端开发工程师  
> 适用范围：课程实践中的 **模块一：文档处理与检索层**、**模块二：RAG 生成层**  
> 文档性质：后端开发的单一事实来源（Source of Truth）。Codex 在本仓库执行与后端相关的任何设计、编码、重构、测试、依赖调整前，必须先阅读并遵守本文档。

---

## 0. Codex 执行总则（最高优先级）

### 0.1 强制规则

1. **只实现后端职责，不主动实现其他成员模块。**
   - 不实现 Web 页面、Streamlit/Gradio 页面布局、CSS、前端交互。
   - 不实现 Agent 的 ReAct 核心循环、工具路由、Agent 记忆管理、并行工具调用。
   - 不承担完整系统评测、最终 PPT、完整用户手册等其他成员主要职责。
   - 允许为集成需要提供清晰、稳定的 Python 接口、数据结构和必要的后端测试。

2. **不得擅自改变课程要求。**
   - 本文档明确要求“必须实现”的功能，不得因为“更简单”“框架已有”而删除。
   - 特别是混合检索中的 **RRF（Reciprocal Rank Fusion）必须保留清晰的自主实现逻辑**，不能仅调用一个高层封装后声称完成。
   - 需要比较的方案必须保留可切换配置，不能只留下最终“最好”的一个方案。

3. **禁止无说明的大规模重构。**
   - 如需修改目录结构、核心接口、配置格式或删除已有代码，先说明原因、影响范围和迁移方案。
   - 优先小步修改，保证每一步可运行、可回退。

4. **每次任务开始前先检查仓库现状。**
   - 阅读 `README.md`、本文档、现有目录结构、依赖文件和相关代码。
   - 运行 `git status`。
   - 不覆盖其他成员已经完成的代码。
   - 发现冲突或职责边界不清时，停止扩大修改范围，并在结果中明确指出。

5. **不得提交敏感信息。**
   - API Key、Token、数据库口令、私人路径等只允许放在 `.env`，并确保 `.env` 在 `.gitignore`。
   - 提供 `.env.example`，其中只能有变量名和示例占位符。

6. **代码必须可复现。**
   - 新增 Python 依赖时同步更新 `requirements.txt`。
   - 新增配置项时同步更新示例配置或 README 的后端说明。
   - 不允许“只在开发者电脑上能运行”的硬编码绝对路径。

7. **不允许伪造实验结果。**
   - Hit@5、MRR、延迟、模型效果等数据必须来自真实运行。
   - 如果当前环境无法跑模型或缺少数据，只能留下可执行的实验脚本和 TODO，不得编造数值。

### 0.2 Codex 每次完成任务后的固定输出

每次 Codex 完成一个后端任务后，必须汇报：

- 修改了哪些文件；
- 每个文件为什么修改；
- 当前完成了本文档哪个需求编号；
- 执行了哪些测试/命令；
- 哪些测试通过、哪些未运行；
- 是否新增依赖；
- 是否存在待办或风险；
- 建议的 Git commit message。

---

# 1. 项目目标

本后端负责为“智能科研助理 —— 基于 RAG + Agent 的论文知识库问答系统”提供可靠的数据、检索与生成能力。

后端最终必须完成下面这条链路：

```text
学术文档
  ↓
文档加载
  ↓
文本清洗与分块
  ↓
Embedding 向量化
  ↓
向量数据库 / 索引
  ↓
向量检索 + BM25
  ↓
RRF 融合
  ↓
Reranker 重排序
  ↓
Top-K 上下文
  ↓
RAG Prompt
  ↓
LLM 生成
  ↓
带“文档名 + 页码”引用的答案
```

后端必须能够被后续 Agent 模块调用，也必须能够被前端模块集成，但后端本身不负责实现 Agent 或前端界面。

---

# 2. 后端职责边界

## 2.1 本成员必须负责

### 模块一：文档处理与检索层

- 多格式文档加载；
- PDF 解析方案对比；
- 批量导入与状态追踪；
- 文本清洗与分块；
- 3 种以上分块策略；
- 分块参数实验；
- Embedding；
- 向量数据库；
- 增量索引；
- 向量 Top-K 检索；
- BM25；
- RRF；
- Reranker；
- 检索性能实验；
- 检索层模块代码；
- 分块策略实验记录。

### 模块二：RAG 生成层

- RAG Prompt；
- 检索上下文拼接；
- 上下文长度控制；
- LLM 调用封装；
- 流式输出能力；
- 引用溯源；
- 生成参数实验；
- 语义缓存；
- 降级策略；
- 请求日志；
- Token / 延迟等基础观测；
- RAG 模块测试。

## 2.2 明确不属于本成员主要职责

以下内容不得由 Codex 在没有明确新增指令时主动扩张实现：

```text
Agent ReAct 核心循环
Agent 工具选择路由
Agent 并行工具调用
Agent 长对话记忆
Agent 错误自愈主逻辑
Streamlit / Gradio 页面
网页样式
Agent Thought/Action/Observation 前端可视化
最终 50+ QA 评测集的完整建设
完整系统级 QA 报告
Docker 最终部署负责人工作
演示 PPT
```

注意：为了支持其他成员集成，后端可以定义接口、返回统一数据结构、提供测试示例，但不能把其他模块整个包办。

---

# 3. 仓库与 Git 约束

当前项目使用 GitHub 仓库：

```text
https://github.com/Yang2Krown/Co-Work.git
```

开发必须在本地 clone 的 `Co-Work` 目录中进行。

## 3.1 分支建议

后端成员不要长期直接在 `main` 上开发。

建议创建：

```bash
git switch -c backend-jolley
```

日常流程：

```bash
git status
git pull --rebase origin main
# 编码 / 测试
git status
git add <明确的文件>
git commit -m "feat(backend): ..."
git push -u origin backend-jolley
```

禁止为了省事频繁使用无法解释的：

```bash
git add .
```

当改动范围较大时，优先明确添加本次相关文件，避免误提交其他成员文件、临时文件、模型缓存或数据。

## 3.2 Commit 规范

建议：

```text
feat(backend): add PDF document loader
feat(retrieval): implement BM25 and RRF fusion
feat(rag): add citation-aware answer generation
test(retrieval): add retrieval metric tests
fix(rag): handle empty retrieval fallback
refactor(backend): split vector store abstraction
docs(backend): update backend setup guide
```

一次 commit 尽量只解决一个明确问题。

---

# 4. 推荐目录结构

如果仓库目前只有 README 或结构尚未建立，后端优先按照以下结构创建；如果其他成员已经建立公共结构，应兼容现有结构，不得强行覆盖。

```text
Co-Work/
├── README.md
├── BACKEND_REQUIREMENTS.md
├── requirements.txt
├── .gitignore
├── .env.example
│
├── config/
│   └── backend.yaml
│
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   ├── processed/
│   │   └── .gitkeep
│   ├── indexes/
│   │   └── .gitkeep
│   └── samples/
│       └── .gitkeep
│
├── src/
│   └── backend/
│       ├── __init__.py
│       │
│       ├── loaders/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── pdf_loader.py
│       │   ├── docx_loader.py
│       │   └── text_loader.py
│       │
│       ├── chunking/
│       │   ├── __init__.py
│       │   ├── fixed.py
│       │   ├── recursive.py
│       │   ├── semantic.py
│       │   └── service.py
│       │
│       ├── embeddings/
│       │   ├── __init__.py
│       │   └── service.py
│       │
│       ├── vectorstores/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── chroma_store.py
│       │   └── faiss_store.py
│       │
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── vector_retriever.py
│       │   ├── bm25_retriever.py
│       │   ├── rrf.py
│       │   ├── reranker.py
│       │   └── hybrid_retriever.py
│       │
│       ├── rag/
│       │   ├── __init__.py
│       │   ├── prompt.py
│       │   ├── context_builder.py
│       │   ├── llm_client.py
│       │   ├── citation.py
│       │   ├── cache.py
│       │   └── service.py
│       │
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── models.py
│       │
│       ├── observability/
│       │   ├── __init__.py
│       │   └── logging.py
│       │
│       └── exceptions.py
│
├── scripts/
│   ├── ingest_documents.py
│   ├── build_index.py
│   ├── evaluate_chunking.py
│   ├── evaluate_retrieval.py
│   └── demo_rag.py
│
├── tests/
│   └── backend/
│       ├── test_loaders.py
│       ├── test_chunking.py
│       ├── test_rrf.py
│       ├── test_retrieval.py
│       └── test_rag.py
│
└── docs/
    └── backend/
        ├── architecture.md
        ├── chunking_experiment.md
        ├── retrieval_experiment.md
        └── integration_contract.md
```

原则：

- `src/backend` 只放可复用业务代码；
- `scripts` 放命令行实验/构建脚本；
- `tests` 放测试；
- `docs/backend` 放后端设计与实验说明；
- 大型论文、模型权重、向量索引默认不提交 Git；
- `data/raw`、`data/processed`、`data/indexes` 中的大文件应通过 `.gitignore` 排除。

---

# 5. 统一核心数据结构

为了后续 Agent 和 Frontend 可以稳定调用，后端必须尽早统一数据结构。

建议使用 `dataclass` 或 Pydantic Model，不能在各模块之间长期传递结构不明的裸 dict。

## 5.1 Document

```python
Document(
    document_id: str,
    file_name: str,
    file_type: str,
    text: str,
    metadata: dict
)
```

metadata 至少保留：

```text
source_path
page_number（可获得时）
title（可获得时）
```

## 5.2 Chunk

```python
Chunk(
    chunk_id: str,
    document_id: str,
    text: str,
    page_number: int | None,
    file_name: str,
    metadata: dict
)
```

必须保证 Chunk 可以追溯回：

```text
哪个文件
哪一页
哪个 chunk
```

否则后面的引用溯源不可能可靠实现。

## 5.3 RetrievalResult

```python
RetrievalResult(
    chunk_id: str,
    text: str,
    document_id: str,
    file_name: str,
    page_number: int | None,
    vector_score: float | None,
    bm25_score: float | None,
    rrf_score: float | None,
    rerank_score: float | None,
    rank: int
)
```

不同检索阶段的分数不要互相覆盖。

## 5.4 RAGResponse

```python
RAGResponse(
    answer: str,
    citations: list,
    retrieved_chunks: list[RetrievalResult],
    latency_ms: float,
    token_usage: dict | None,
    fallback_used: bool
)
```

---

# 6. 模块一：文档加载器

## REQ-BE-101 PDF 加载

必须对比至少：

```text
PyPDF2
pdfplumber
PyMuPDF
```

Codex 不得一开始就只写一个加载器然后删除其他方案的可比较能力。

需要设计统一接口，例如：

```python
load_pdf(path, engine="pymupdf")
```

必须尽量保留：

- 页码；
- 文件名；
- 文本；
- 基础元信息。

实验需记录：

- 是否成功解析；
- 文本完整性；
- 双栏论文的阅读顺序表现；
- 速度；
- 公式/表格附近文本表现。

最终可以选择默认解析引擎，但另外两个方案的实验代码或可切换实现必须保留。

## REQ-BE-102 Word 加载

使用 `python-docx` 实现 `.docx` 文档加载。

至少输出：

```text
段落文本
文件名
文档 ID
必要元信息
```

## REQ-BE-103 TXT / Markdown 加载

支持：

```text
.txt
.md
```

统一使用 UTF-8，并针对常见编码异常提供友好错误信息。

## REQ-BE-104 批量导入

需要支持一次处理多个文件。

每个文件至少有状态：

```text
pending
processing
success
failed
```

失败一个文件不能导致整个批次崩溃。

需要记录失败原因，并支持失败项重试。

后端提供进度信息即可；进度条 UI 属于前端，不在本成员范围。

---

# 7. 模块一：文本分块

## REQ-BE-201 固定大小切分

必须支持并实验：

```text
chunk_size = 256
chunk_size = 512
chunk_size = 1024
```

需要支持合理的 overlap 配置。

## REQ-BE-202 递归字符切分

实现或合理调用：

```text
RecursiveCharacterTextSplitter
```

但必须封装到本项目统一 Chunk 接口。

## REQ-BE-203 语义/结构切分

至少按：

```text
句子边界
段落边界
```

进行结构感知切分。

必须尽量避免把完整句子无意义地从中间截断。

## REQ-BE-204 学术 PDF 特殊处理

分块模块需要考虑并记录以下问题：

- 双栏论文；
- 跨页文本；
- 表格附近内容；
- 数学公式；
- 标题/章节边界。

课程实践阶段不要求完美恢复论文版面，但必须能说明已知局限，不能假装这些问题不存在。

## REQ-BE-205 分块策略对比实验

同一批文档至少比较：

```text
固定切分
递归切分
结构/语义切分
```

并测试不同策略对检索效果的影响。

实验脚本：

```text
scripts/evaluate_chunking.py
```

实验记录：

```text
docs/backend/chunking_experiment.md
```

严禁伪造实验数值。

---

# 8. 模块一：Embedding 与向量存储

## REQ-BE-301 Embedding 模型

课程要求比较：

```text
bge-large-zh
m3e-base
```

代码层必须允许切换模型，而不是把模型名称散落硬编码到多个文件。

例如配置：

```yaml
embedding:
  provider: local
  model_name: bge-large-zh
  batch_size: 32
```

至少记录：

- 向量生成速度；
- 检索质量表现；
- 资源占用的基本情况。

## REQ-BE-302 向量数据库

课程要求在以下方案中进行选型/比较：

```text
Chroma
FAISS
```

架构上使用统一抽象，避免 RAG 逻辑直接依赖某一数据库私有 API。

至少提供：

```python
add_chunks(...)
search(...)
delete_document(...)
persist(...)
```

## REQ-BE-303 增量更新

新增一篇论文时，不能强制重建全部知识库。

系统需要：

1. 识别文档；
2. 只处理新增/变更文档；
3. 生成新增 chunk；
4. 只向索引加入新增向量。

需要避免同一文档重复导入导致无穷重复 chunk。

## REQ-BE-304 Top-K 向量检索

实现 configurable Top-K：

```yaml
retrieval:
  vector_top_k: 20
  final_top_k: 5
```

最终数值可根据实验调整，不允许散落硬编码。

---

# 9. 模块一：BM25 + RRF + Reranker

这是本后端最关键的课程要求之一。

## REQ-BE-401 BM25

使用 `rank_bm25` 或同等级方案实现关键词检索。

BM25 和向量检索必须能够独立运行，便于实验对比。

## REQ-BE-402 RRF 融合

必须实现 RRF 融合算法。

要求：

- 代码清晰；
- 有独立函数/模块；
- 有单元测试；
- 输入为不同检索器的排序结果；
- 输出为融合后的排序；
- 不允许完全依赖高层框架内部不可见实现。

建议接口：

```python
rrf_fuse(
    ranked_lists: list[list[RetrievalResult]],
    k: int = 60
) -> list[RetrievalResult]
```

测试必须覆盖：

- 两个列表存在重复 chunk；
- 某 chunk 只出现在一个列表；
- 排名相同时结果稳定；
- 空列表情况。

## REQ-BE-403 Reranker

接入：

```text
bge-reranker-base
或
bge-reranker-v2 系列
```

流程目标：

```text
向量候选
+
BM25 候选
↓
RRF
↓
Top-N 候选
↓
Reranker
↓
最终 Top-K
```

Reranker 必须可配置关闭，以便进行三档对比实验。

## REQ-BE-404 三档检索实验

必须至少对比：

```text
A. 纯向量检索
B. 向量 + BM25 + RRF
C. 向量 + BM25 + RRF + Reranker
```

至少记录：

```text
Hit@5
MRR
```

如果已经构建可用评测数据，也可增加 Recall。

实验输出写入：

```text
docs/backend/retrieval_experiment.md
```

真实数据可导出为 CSV/JSON，供 QA 成员进一步使用。

---

# 10. 模块二：RAG 生成

## REQ-BE-501 RAG Prompt

Prompt 至少包括：

```text
System Role
Retrieved Context
User Question
Output Format
Citation Rules
Insufficient Evidence Rules
```

核心规则：

- 模型应优先基于检索上下文回答；
- 没有足够证据时必须明确说知识库中未找到充分依据；
- 禁止虚构文档名和页码；
- 引用只能来自真正检索到的 chunk。

Prompt 单独维护：

```text
src/backend/rag/prompt.py
```

不要散落在业务函数中。

## REQ-BE-502 上下文拼接

检索结果进入 LLM 之前必须：

1. 按最终相关性排序；
2. 去除明显重复内容；
3. 保留来源信息；
4. 控制最大上下文长度；
5. 必要时动态截断。

不得简单地把所有 chunk 无限制拼接。

## REQ-BE-503 引用溯源

答案必须能够返回类似：

```text
[1] paper_a.pdf, p.5
[2] paper_b.pdf, p.8
```

底层 citation 必须对应真实检索结果。

如果页码解析不到，可以明确返回：

```text
page_number = null
```

不得猜页码。

## REQ-BE-504 生成参数实验

代码必须允许配置：

```text
temperature
top_p
top_k（模型支持时）
```

至少保留实验能力，不把参数写死在函数里。

## REQ-BE-505 流式输出

后端必须提供流式生成能力。

可采用：

```text
Python generator / async generator
```

如果后续集成明确需要 HTTP，再由薄 API 层转换为 SSE。

本成员不需要实现 Streamlit 的“打字机动画”，只需要提供可被前端消费的流。

---

# 11. 缓存与降级

## REQ-BE-601 语义缓存

相同或高度相似问题允许命中缓存。

至少考虑：

```text
question embedding
similarity threshold
knowledge base version
generation config
```

知识库发生变化后，不能无脑继续使用已经过期的缓存答案。

## REQ-BE-602 检索无结果

如果无检索结果：

```text
fallback_used = true
```

并明确提示：

```text
当前知识库中未找到相关文档
```

是否允许继续纯 LLM 回答必须由配置控制。

## REQ-BE-603 低相关结果

如果检索相关度低：

- 不把低置信信息伪装成确定事实；
- 返回低相关提示；
- 仍可把检索候选提供给上层调用者。

## REQ-BE-604 模型调用失败

LLM 超时、API 错误或本地服务不可用时：

- 捕获错误；
- 返回结构化异常；
- 给上层调用者友好信息；
- 记录日志；
- 不让整个进程因为单次请求崩溃。

---

# 12. 日志与基础可观测性

每次 RAG 请求至少记录：

```text
request_id
timestamp
user_question
retrieval_mode
top_k
retrieved chunk IDs
retrieval scores
LLM model
generation parameters
answer
latency
token usage（能够获取时）
fallback_used
error（如有）
```

日志不得记录 API Key。

开发阶段日志建议使用结构化 logging，不使用大量无管理的 `print()`。

需要能统计：

- 每次请求延迟；
- Top-1 检索分数；
- Token 使用量（模型返回时）；
- 检索模式。

这些数据以后由 QA/前端成员继续用于整体评测和展示。

---

# 13. 配置管理

所有容易调整的参数必须进入配置，而不是散落硬编码。

至少包括：

```yaml
document:
  pdf_engine: pymupdf

chunking:
  strategy: recursive
  chunk_size: 512
  chunk_overlap: 64

embedding:
  model_name: bge-large-zh

vector_store:
  type: chroma

retrieval:
  vector_top_k: 20
  final_top_k: 5
  enable_bm25: true
  enable_rrf: true
  rrf_k: 60
  enable_reranker: true

rag:
  temperature: 0.2
  top_p: 0.9
  allow_llm_fallback: true

cache:
  enabled: true
  similarity_threshold: 0.95
```

数值是合理初始值，不代表课程实验最终最佳值；最终结果必须由真实实验确定。

---

# 14. 依赖管理

原则：

- 优先 Python 3.11；
- 使用 `requirements.txt`；
- 只引入实际需要的包；
- 禁止为了一个简单函数引入超大型框架；
- 高层框架可用于工程性工作，但不能掩盖课程要求自主实现的关键算法。

可能涉及的依赖类别：

```text
PyMuPDF
pdfplumber
PyPDF2
python-docx
sentence-transformers
chromadb
faiss-cpu
rank-bm25
numpy
pydantic
PyYAML
pytest
```

是否引入 LangChain/LlamaIndex，应以“减少工程重复”为目的；如果引入，也必须把关键检索流程保持透明、可测试、可替换。

---

# 15. 测试要求

Codex 不能以“代码写完”作为完成标准。

## 15.1 单元测试最低覆盖

至少测试：

```text
PDF / DOCX / TXT 加载
固定分块
递归分块
Chunk 元数据保留
RRF
BM25 检索基本行为
向量检索接口
空检索降级
Citation 生成
RAG 返回结构
```

## 15.2 集成测试

至少有一个小型端到端测试：

```text
测试文档
↓
加载
↓
分块
↓
建立索引
↓
检索
↓
RAG
↓
返回答案 + Citation
```

测试尽量使用小型样例，避免 CI / 普通电脑必须下载巨大模型才能运行全部测试。

需要把“纯逻辑测试”和“依赖真实模型的慢测试”区分开。

---

# 16. 后端对其他成员暴露的接口

后端必须保持以下能力边界清晰。

## 16.1 文档导入

概念接口：

```python
ingest_documents(paths: list[str]) -> IngestionResult
```

返回：

```text
成功文件
失败文件
处理 chunk 数
索引版本
错误信息
```

## 16.2 检索

```python
retrieve(
    query: str,
    mode: str = "hybrid_rerank",
    top_k: int = 5
) -> list[RetrievalResult]
```

建议 mode：

```text
vector
hybrid
hybrid_rerank
```

## 16.3 RAG

```python
answer(
    question: str,
    top_k: int = 5
) -> RAGResponse
```

## 16.4 流式 RAG

```python
stream_answer(question: str, top_k: int = 5)
```

Agent 成员以后可以把这些能力封装成 Agent Tool，但后端本身不负责写 Agent 的 Tool Router。

---

# 17. 错误处理

至少定义清晰异常：

```text
DocumentLoadError
UnsupportedFileTypeError
EmbeddingError
VectorStoreError
RetrievalError
RerankerError
LLMServiceError
ConfigurationError
```

不要把所有异常都写成：

```python
except Exception:
    return None
```

如果必须捕获总异常，应记录原始错误并转换为明确的业务异常。

---

# 18. 性能与工程约束

课程项目阶段重点是正确性和可解释性，而不是过度优化。

但是必须做到：

- 批量 embedding，不逐条低效调用；
- 索引可持久化；
- 支持增量更新；
- 同一模型不要每次请求重复加载；
- 缓存可关闭；
- Reranker 可关闭；
- 所有实验模式可以通过配置切换；
- 不在 import 时执行耗时模型下载；
- 不在代码中自动下载无法控制的 GB 级资源而不提示用户。

---

# 19. `.gitignore` 最低要求

至少排除：

```gitignore
.env
.venv/
venv/
__pycache__/
*.pyc
.pytest_cache/
.DS_Store

data/raw/*
!data/raw/.gitkeep

data/processed/*
!data/processed/.gitkeep

data/indexes/*
!data/indexes/.gitkeep

logs/
.cache/
*.log
```

如模型、Chroma/FAISS 本地文件产生额外大文件，也需要补充排除规则。

---

# 20. 后端阶段性里程碑

Codex 不应一次性生成整个项目。必须按阶段推进。

## M0：仓库初始化与后端骨架

完成：

- 后端目录；
- requirements；
- .gitignore；
- .env.example；
- 配置系统；
- schemas；
- 基础测试框架。

验收：

```bash
pytest
```

基础测试可执行。

---

## M1：文档加载

完成：

- PDF 三方案；
- DOCX；
- TXT / Markdown；
- 批量加载；
- 状态记录；
- 样例测试。

验收：

给定样例文档，能够输出统一 Document 数据结构，并保留来源与页码信息。

---

## M2：分块

完成：

- fixed；
- recursive；
- semantic/structure；
- chunk_size 256/512/1024；
- 实验脚本。

验收：

Chunk 能稳定回溯原文档和页码，实验脚本可运行。

---

## M3：Embedding + Vector Store

完成：

- bge-large-zh / m3e-base 可配置；
- Chroma / FAISS 抽象；
- 增量索引；
- Top-K 搜索。

验收：

导入文档后可以根据问题返回相关 chunk。

---

## M4：混合检索

完成：

- BM25；
- RRF；
- Reranker；
- 三种检索模式；
- Hit@5 / MRR 实验代码。

验收：

以下三种模式都能独立运行：

```text
vector
hybrid
hybrid_rerank
```

---

## M5：RAG

完成：

- Prompt；
- context builder；
- LLM client；
- answer；
- citation；
- streaming。

验收：

输入与知识库相关问题，返回：

```text
答案
引用
retrieved_chunks
延迟
Token 信息（可获得时）
```

---

## M6：缓存、降级、日志

完成：

- 语义缓存；
- 无结果降级；
- 低相关提示；
- LLM 错误处理；
- 结构化日志。

验收：

模拟空知识库、LLM 失败等情况，系统不崩溃且返回明确状态。

---

## M7：后端交付整理

完成：

```text
docs/backend/architecture.md
docs/backend/chunking_experiment.md
docs/backend/retrieval_experiment.md
docs/backend/integration_contract.md
```

同步：

```text
README 后端运行方法
requirements.txt
.env.example
```

---

# 21. Definition of Done

一个后端任务只有同时满足以下条件才能标记完成：

- 功能实现；
- 对应测试完成；
- 运行没有明显报错；
- 不破坏已有接口；
- 配置项没有硬编码散落；
- 没有敏感信息；
- 没有把大模型/索引/论文大文件误提交；
- requirements 已同步；
- 文档有必要更新；
- `git status` 中没有无法解释的改动；
- Codex 已说明本次实现对应的需求编号。

---

# 22. 后端最终交付物

成员 A 最终应能明确交出：

1. 多格式文档加载模块；
2. PDF 三种解析方案对比；
3. 三种以上分块策略；
4. 分块参数对比脚本与实验记录；
5. Embedding 模型可切换实现；
6. Chroma / FAISS 可选向量存储；
7. 增量索引；
8. Top-K 向量检索；
9. BM25；
10. 自主实现的 RRF；
11. Reranker；
12. 纯向量 / 混合 / 混合+重排三档检索；
13. Hit@5 / MRR 等检索实验脚本与真实结果记录；
14. RAG Prompt；
15. 上下文拼接和截断；
16. LLM 调用；
17. 流式输出；
18. 文档名 + 页码 Citation；
19. 语义缓存；
20. 降级策略；
21. 请求日志和基础性能信息；
22. 单元测试和最小端到端测试；
23. 后端架构、实验和接口说明文档。

---

# 23. 明确禁止的“看似完成”

下面这些情况一律不算完成：

### 错误 1

```text
调用 LangChain 一个 RetrievalQA
→ 声称 RAG、检索、RRF、Reranker 全部完成
```

不允许。

### 错误 2

```text
只实现 PyMuPDF
→ 文档写“已比较 PyPDF2/pdfplumber/PyMuPDF”
```

不允许。

### 错误 3

```text
代码里写死：
chunk_size=512
model="xxx"
top_k=5
```

且没有配置能力。

不允许。

### 错误 4

```text
生成回答里直接让 LLM 自己编 [论文，第X页]
```

不允许。

Citation 必须来自检索 metadata。

### 错误 5

```text
为了“项目完整”主动把 Agent、前端也全部写了
```

不允许。本成员只负责后端范围。

### 错误 6

```text
实验还没跑，却在 Markdown 里写 Hit@5=0.87
```

严禁。

### 错误 7

直接删除或覆盖队友文件来迁就自己的目录设计。

严禁。

---

# 24. 给 Codex 的固定启动指令

每次新开 Codex 会话时，优先发送：

```text
你正在开发 Git 仓库 Yang2Krown/Co-Work 中成员 A 的后端部分。

开始任何工作前：
1. 阅读仓库根目录 BACKEND_REQUIREMENTS.md；
2. 阅读 README.md；
3. 检查当前 Git 分支和 git status；
4. 检查现有代码，不覆盖其他成员工作；
5. 只实现 BACKEND_REQUIREMENTS.md 定义的 Backend 范围；
6. 将 BACKEND_REQUIREMENTS.md 视为本次后端开发的最高项目约束；
7. 如果我的临时指令和该文档存在明显冲突，先指出冲突，不要静默违背文档；
8. 不要一次性生成整个项目，按照里程碑逐步完成；
9. 每次修改后运行相关测试；
10. 完成后汇报修改文件、需求编号、测试结果、依赖变化、风险和建议 commit message。

现在先不要写代码。请先审计当前仓库，并告诉我：
- 当前仓库结构；
- 当前分支和 Git 状态；
- 已完成了哪些后端需求；
- 缺失哪些后端需求；
- 你建议从哪个里程碑开始；
- 下一步准备修改哪些文件。
等我确认后再开始编码。
```

---

# 25. 第一阶段推荐执行顺序

首次正式开发时，不要直接说：

```text
“帮我把整个后端做完”
```

应按下面顺序让 Codex 执行：

```text
第一轮：仓库审计，不写代码
第二轮：M0 后端骨架
第三轮：M1 文档加载
第四轮：M2 分块
第五轮：M3 Embedding + Vector Store
第六轮：M4 混合检索
第七轮：M5 RAG
第八轮：M6 缓存/降级/日志
第九轮：M7 整理与接口交付
```

每完成一个里程碑，先：

```bash
git status
pytest
```

人工检查后再 commit，再进入下一阶段。

---

# 26. 最终原则

本后端追求的不是“代码很多”，而是：

```text
课程要求完整
+
核心算法透明
+
接口清晰
+
实验可复现
+
代码可测试
+
能被 Agent / Frontend 稳定集成
+
Git 历史清楚
```

如果 Codex 在“做得更复杂”和“严格完成课程要求”之间需要选择，优先严格完成课程要求。

如果 Codex 在“自动帮用户包办其他成员工作”和“守住 Backend 职责边界”之间需要选择，必须守住 Backend 职责边界。

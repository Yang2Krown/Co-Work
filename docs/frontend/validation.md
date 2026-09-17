# 前端与集成验证记录

验证日期：2026-09-16 至 2026-09-17。代码测试、原型演示和真实外部服务调用分别记录，不能互相替代。

## 环境

macOS Apple Silicon，当前验证环境 Python 3.14.6、Streamlit 1.64.0、pytest 8.4.2。团队部署仍建议 README 中的 Python 3.11/3.12，以便安装机器学习依赖。仅向项目 `.venv` 安装了 UI、解析与离线测试所需包。

## 自动化测试

```bash
.venv/bin/python -m pytest -q
```

结果：**66 passed，2 skipped**。6 条警告来自 PyMuPDF/SWIG 与 PyPDF2 的弃用提示。

- 应用层 17 项：内容去重、同名不同内容、部分失败、索引失败重试、上传限制、文档删除一致性、dirty 恢复、SQLite 会话与摘要恢复、运行中互斥、断流保留文本、DeepSeek client 共享、401/429/超时脱敏、工具失败后继续及最大迭代结果。
- 前端 AppTest 2 项：页面导航、空状态、确定性计算、重复渲染不重复提交、检查器、模式切换新建会话。
- 现有后端测试：47 项通过；Chroma 和 FAISS 两项因未安装对应包跳过。
- `git diff --check` 通过。

应用生命周期测试使用真实解析器、BM25 与内存向量存储，以及替身 Embedding/Reranker/LLM；这些测试不证明真实模型检索质量。

## 浏览器与视觉

六个 HTML 原型场景的源文件已按 Swiss / International typographic 方向重写。当前环境未安装可用的 Playwright/Chrome 渲染器，因此没有重新导出 PNG；原有 PNG 仅作为旧版历史快照，不作为本版视觉验收依据。

真实 Streamlit 浏览器检查使用专用临时数据目录，与用户知识库分离。通过：

1. 空工作台加载，提交 `3 * 7` 并返回计算结果 21。
2. 回答完成后立即点击执行详情，展开检查器。
3. 切换至 1280×800，无页面水平溢出。
4. 上传无效 PDF，显示部分失败、具体错误和重试入口。
5. 删除测试文档，确认对话框正常，删除后知识库为空。
6. 系统状态导航、缺失指标口径正确，无可见 Streamlit 异常和浏览器脚本错误。

视觉检查修正了检查器开关被顶栏遮挡的问题；时序检查修正了任务结束自动刷新可能吞掉点击的问题。最终浏览器脚本位于 `tests/frontend/browser_smoke.mjs`，需要 Playwright 与 Chrome，可通过 `PLAYWRIGHT_MODULE` 指定包路径。

```bash
# 另一个终端启动专用测试工作区，不要对日常数据目录运行浏览器冒烟测试
COWORK_DATA_DIR=/tmp/cowork-ui-qa .venv/bin/streamlit run app.py --server.port 8501
node tests/frontend/browser_smoke.mjs
```

浏览器截图为临时 QA 文件，交付的六张 PNG 位于 `docs/frontend/prototype/`，均明确标注为演示数据。

## 真实 DeepSeek 验证

使用当前环境中的 `DEEPSEEK_API_KEY`，没有输出或保存密钥。配置模型为 `deepseek-v4-flash`。

| 检查 | 结果 | 解释 |
| --- | --- | --- |
| 小额连接探测 | 通过 | 返回非空文本；一次诊断请求实际使用 52 Token |
| 修正后的应用健康检查 | 通过 | 将输出上限由 8 提升至 128，避免推理 Token 占满预算导致无正文 |
| RAG 真流式 | completed | 空知识库，返回 52 字符，metadata → 多个 token → end；总耗时约 6.285 秒 |
| Agent 事件流 | completed | 空知识库，知识库工具路由，run_started → thought → tool_started → tool_finished → final → run_finished；约 2.201 秒 |
| client 共享 | 通过 | Agent 与直接 RAG 是同一个 DeepSeek client |

上表两种对话使用空知识库，只验证真实 API、生成和事件传输；引用数量均为 0，不能据此声称完成真实论文检索。耗时是单次观察，不是性能基准或服务承诺。

真实本地论文解析另行验证：`2505.09388.pdf` 提取文本 116111 字符，分块 280 个，280 个分块具有页码。论文文件与正文未添加到提交中。

## 尚未完成的环境级验证

**完整“真实论文 → 本地 Embedding → Chroma/FAISS → Reranker → DeepSeek → 引用核对”链路尚未运行。** 当前 `.venv` 缺少 sentence-transformers、Chroma 和 FAISS，机器上也没有本次所需的 Hugging Face 模型缓存。应用已经实现组合代码，但真实模型检索、索引持久化适配器及质量指标仍需验证。

在合适的 Python 环境安装 `requirements.txt` 并准备模型后，运行：

```bash
.venv/bin/python scripts/smoke_test_workspace.py --paper path/to/paper.pdf
```

该脚本在独立临时工作区执行连接探测、导入、两种问答、引用数量和删除一致性检查，明确返回成功或失败；不会在默认 pytest 中调用外部模型。正式课程验收还应人工核对答案引用，并由 QA 使用标注集评测 Hit@5、MRR 等质量指标。

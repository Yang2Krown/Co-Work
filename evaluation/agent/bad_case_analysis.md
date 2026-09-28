Agent Bad Case 分析

1\. 分析目的

为进一步验证论文知识库问答系统中 Agent 模块的稳定性与可靠性，对 Agent 测试过程中出现的典型异常案例进行分析。

本次分析重点关注 Agent 在工具选择、工具调用次数以及外部信息检索方面存在的问题，并针对具体问题分析产生原因及优化方法。

\---

2\. Bad Case 总体情况

本次测试共发现并分析 3 个典型 Bad Case，主要包括：

| 编号 | 类型 | 主要问题 |

|---|---|---|

| BC01 | Agent 决策错误 | 知识库问题未调用知识库检索工具 |

| BC02 | 工具重复调用 | 相同工具在同一任务中被重复调用 |

| BC03 | 工具选择不合理 | 知识库问题中进行了不必要的 Web 搜索 |

这些问题主要与 Agent 的 Prompt 约束和工具调用决策机制有关。

\---

3\. 典型 Bad Case 分析

3.1 BC01：未调用知识库检索工具

问题描述：

在部分涉及已上传论文内容的问题中，Agent 没有优先调用 `knowledge\_retrieval` 工具，而是直接根据语言模型自身已有知识生成回答。

该行为可能导致回答没有充分利用当前论文知识库中的内容，并且无法生成与知识库文档对应的可靠引用。



典型场景：

用户提出明确的论文知识库问题，例如：

> 根据上传的论文，说明 Transformer 中某种方法的主要特点。

在优化前的 Agent 决策过程中，Agent 可能直接生成回答，而没有执行：

knowledge\_retrieval



原因分析：

主要原因是原始 Prompt 对“知识库问题”和“普通知识问答”的边界约束不够明确。

Agent 可以根据自身语言模型知识直接回答问题，因此在判断问题属于一般知识问答时，可能跳过知识库检索。



影响：

该问题可能造成：

1\. 回答没有充分依据用户上传的论文；

2\. 无法获得对应的知识库引用；

3\. 回答内容与知识库文档存在偏差；

4\. 降低论文问答场景下的可追溯性。



优化方法：

在 Agent Prompt 中增加明确的知识库调用规则：

For explicit knowledge-base questions, questions about uploaded papers, or questions asking for an answer according to the papers, you MUST call knowledge\_retrieval before producing a final answer. Do not answer directly from general model knowledge in these cases.

通过该规则强制 Agent 在明确的知识库问题中优先调用 knowledge\_retrieval。



优化结果：

Prompt 优化后，Agent 能够正确识别知识库问题，并在生成最终答案之前调用知识库检索工具。

该问题在最终 Agent 测试中未再次出现。



3.2 BC02：重复调用知识库检索工具

问题描述：

在部分测试任务中，Agent 已经通过 knowledge\_retrieval 获取了足够的信息，但随后又针对相同问题重复调用知识库检索工具。



典型场景：

Agent 执行：

knowledge\_retrieval

&#x20;       ↓

获得相关论文内容

&#x20;       ↓

再次调用 knowledge\_retrieval

&#x20;       ↓

生成最终答案



当第一次检索已经返回足够相关的内容时，第二次检索通常不会明显增加有效信息。



原因分析:

主要原因是 Agent 在 ReAct 推理过程中缺少对“已有工具结果是否已经足够”的明确约束。

当模型无法完全确定第一次检索结果是否满足需求时，可能选择再次调用相同工具。



影响:

重复调用会导致：

1\. 增加模型推理轮次；

2\. 增加 API 请求次数；

3\. 增加整体响应时间；

4\. 增加不必要的 Token 消耗。



优化方法:

在 Prompt 中增加工具重复调用限制：

After knowledge\_retrieval returns sufficient relevant evidence, do not repeat knowledge\_retrieval for the same request unless the previous result is insufficient, contradictory, or clearly unrelated.

同时结合 Agent 原有的重复动作检测机制，对连续重复工具调用进行限制。



优化结果:

优化后，Agent 能够在获得充分知识库证据后直接进入答案生成阶段。

只有当第一次检索结果不足、存在矛盾或明显无关时，才允许再次进行检索。



3.3 BC03：不必要的 Web Search



问题描述:

在部分知识库问答场景中，Agent 在已经可以通过本地知识库获得答案的情况下，额外调用了 web\_search 工具。



典型场景:

用户询问已经上传论文中的相关内容时，Agent 的工具调用流程可能为：

knowledge\_retrieval

&#x20;       ↓

web\_search

&#x20;       ↓

生成最终答案



如果用户没有要求查询互联网信息，则 Web Search 并不是完成该任务的必要工具。



原因分析:

主要原因是 Agent 在面对论文知识问题时，可能将“补充信息”与“必须进行网络搜索”混淆。

同时，原始 Prompt 没有明确限制知识库问题中的 Web Search 使用条件。



影响:



不必要的 Web Search 可能导致：

1\. 增加整体响应时间；

2\. 增加外部网络请求；

3\. 引入知识库之外的信息；

4\. 增加答案信息来源的不确定性；

5\. 增加 Agent 工具调用轮次。



优化方法:



在 Prompt 中增加明确约束：

For explicit knowledge-base questions, do not use web\_search unless the user explicitly requests external web information, web search, internet information, or current/latest information.



即：

\* 知识库问题 → 优先使用 knowledge\_retrieval

\* 用户明确要求互联网信息 → 可以使用 web\_search

\* 用户询问当前/最新信息 → 可以使用 web\_search

\* 普通论文内容问题 → 不应无必要调用 web\_search



优化结果:

Prompt 优化后，Agent 对知识库问题和外部网络搜索任务的边界判断更加明确。

在最终测试中，Agent 能够优先使用知识库检索工具，并避免在没有明确需求时调用 Web Search。



4\. Bad Case 分类总结

根据上述案例，可以将 Agent 出现的问题划分为以下四类：



4.1 检索失败

Agent 没有调用知识库检索工具，或者没有获得足够的知识库信息。



主要原因:

\* 问题意图识别不准确；

\* Prompt 对知识库问题约束不足；

\* Agent 过度依赖语言模型自身知识。



改进方向:

加强知识库问题识别规则，并明确规定知识库问题必须执行检索。



4.2 生成错误

Agent 获取工具结果后，对工具返回的信息理解或组织不准确。



主要原因:

\* 上下文信息过多；

\* 工具结果与问题相关性不足；

\* 模型推理过程存在偏差。



改进方向:

优化上下文构建和 Prompt，并提高检索结果与用户问题之间的相关性。



4.3 引用错误

回答虽然使用了知识库内容，但引用与最终答案中的事实对应关系不够准确。



主要原因:

\* 检索结果包含多个相关文档；

\* 模型对不同来源内容进行整合时产生混淆；

\* 引用与回答内容之间缺少严格约束。



改进方向:

加强 CitationRef 的来源管理，在生成答案时保留文档名称、页码和 Chunk ID 等信息，确保答案能够追溯到具体知识库内容。



4.4 Agent 决策错误

Agent 对当前任务所需要使用的工具判断不准确。



主要表现:

\* 知识库问题没有调用 knowledge\_retrieval；

\* 已获得足够信息后重复调用工具；

\* 知识库问题不必要地调用 web\_search。



改进方向:

通过 Prompt 规则、工具调用限制和重复动作检测等机制，对 Agent 的工具选择行为进行约束。



5\. 优化前后对比

本次 Bad Case 分析主要针对 Agent 的工具决策能力进行优化。



问题	优化前	优化后

知识库问题未检索	存在	已改善

重复知识库检索	存在	已改善

不必要 Web Search	存在	已改善

工具调用边界	不够明确	规则更加明确

知识库问题处理	可能直接回答	优先执行知识库检索



6\. 最终测试结果

在完成 Prompt 优化后，对 Agent 进行最终测试。



测试规模：



测试用例数：20



最终测试结果：

指标	最终结果

Tool-calling Accuracy	100%

Completion Rate	100%

Average Reasoning Rounds	1.85

Failed Runs	0

Max Iteration Runs	0

最终测试中，20 个测试用例均成功完成，没有出现任务失败或达到最大推理轮次的情况。



7\. 总结

通过对典型 Bad Case 的分析可以发现，Agent 的主要问题并不完全来自底层模型能力，而与工具选择规则、Prompt 约束以及工具调用策略密切相关。

针对测试中发现的典型问题，本系统主要通过以下方式进行优化：

1\. 明确知识库问题必须调用 knowledge\_retrieval；

2\. 限制已经获得充分证据后的重复检索；

3\. 明确 web\_search 的使用条件；

4\. 结合工具调用次数限制和重复动作检测机制；

5\. 对工具执行结果进行结构化管理。

优化后的 Agent 在最终 20 个测试用例中达到 100% 的工具调用准确率和 100% 的任务完成率，平均推理轮次为 1.85，未出现失败任务和最大轮次触发情况。

这些结果表明，针对知识库问答场景进行明确的工具调用约束，可以有效改善 Agent 的任务决策过程，为系统后续的论文问答、知识检索和多工具协同提供更加稳定的基础。




"""The right-hand research inspector."""

import html
from pathlib import Path

import streamlit as st

from src.frontend.components.markdown import render_markdown


TOOL_NAMES = {
    "knowledge_retrieval": "知识库检索",
    "paper_metadata": "论文元信息",
    "paper_compare": "论文对比",
    "paper_summary": "论文摘要",
    "keyword_extract": "关键词提取",
    "calculator": "计算器",
    "current_time": "当前时间",
    "web_search": "联网搜索",
}


def _tool_name(name):
    return TOOL_NAMES.get(name, name or "工具")


def _source_preview(text, limit=320):
    """Keep the inspector scannable while retaining the full source on demand."""

    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value, False
    return value[:limit].rstrip() + "…", True


def _token_text(usage):
    """Format provider usage as a readable metric value."""

    if not isinstance(usage, dict):
        return "未提供"
    total = usage.get("total_tokens")
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    calls = usage.get("model_calls")
    if isinstance(total, (int, float)) and not isinstance(total, bool):
        label = f"{int(total):,}"
    elif isinstance(prompt, (int, float)) and isinstance(completion, (int, float)):
        label = f"{int(prompt + completion):,}"
    else:
        return "已记录"
    if isinstance(calls, (int, float)) and not isinstance(calls, bool) and calls > 1:
        label += f" · {int(calls)} 次调用"
    return label


def _event_info(event):
    name = event.get("event")
    payload = event.get("payload") or event.get("metadata") or {}
    if name == "route_selected":
        if payload.get("uses_llm"):
            return "理解问题", "进入模型规划", "done"
        return "理解问题", f"直接调用 {_tool_name(payload.get('tool_name'))}", "done"
    if name == "llm_started":
        phase = str(payload.get("phase") or "").lower()
        if phase in {"react_planning", "planning"}:
            return "理解问题", "模型规划中", "active"
        if phase in {"tool_internal", "tool"}:
            return "执行工具", "模型调用中", "active"
        return "生成回答", "模型处理中", "active"
    if name == "llm_finished":
        phase = str(payload.get("phase") or "").lower()
        label = "理解问题" if phase in {"react_planning", "planning"} else "执行工具" if phase in {"tool_internal", "tool"} else "生成回答"
        return label, "模型调用完成", "done" if payload.get("ok", True) else "failed"
    if name == "retrieval_started":
        return "知识库检索", "检索中", "active"
    if name == "retrieval_finished":
        return "知识库检索", f"{payload.get('chunk_count', '?')} 个片段", "done"
    if name == "metadata":
        return "整理引用", "引用已更新", "done"
    if name == "thought":
        return "推理过程", "思考已生成", "done"
    if name in ("answer_token", "token"):
        return "生成最终回答", "流式输出", "active"
    if name == "tool_started":
        return _tool_name(event.get("tool_name")), "工具运行中", "active"
    if name == "tool_finished":
        result = payload.get("result") or {}
        return _tool_name(event.get("tool_name")), "工具完成" if result.get("ok") else "工具失败 · 可继续", "done" if result.get("ok") else "failed"
    if name == "final":
        return "生成最终回答", "已完成", "done"
    if name == "error":
        return "执行异常", str(payload.get("error") or event.get("error") or "未提供"), "failed"
    if name == "run_finished":
        result = payload.get("result") or {}
        status = result.get("status") or payload.get("status") or event.get("status") or "completed"
        if status in ("failed", "error", "interrupted"):
            return "生成最终回答", "已结束 · 失败", "failed"
        if status == "max_iterations":
            return "生成最终回答", "已结束 · 达到迭代上限", "failed"
        return "生成最终回答", "已完成", "done"
    if name == "end":
        return "生成最终回答", "已完成", "done"
    return None


def _timeline_rows(events, compact=False):
    rows = []
    positions = {}
    for event in events or []:
        info = _event_info(event)
        if not info:
            continue
        label, detail, state = info
        # A single run can emit many planning/tool/token events. Keep the
        # latest state for each visible step instead of printing repeated
        # rows with the same label.
        if label in positions:
            rows[positions[label]] = (label, detail, state)
        else:
            positions[label] = len(rows)
            rows.append((label, detail, state))
    return rows[-6:] if compact else rows


def live_timeline(events, compact=False):
    rows = _timeline_rows(events, compact=compact)
    if not rows:
        return
    body = ['<div class="cw-process-box"><div class="cw-process-title">执行过程</div>']
    for label, detail, state in rows:
        body.append(
            '<div class="cw-process-row">'
            f'<span class="cw-process-marker {html.escape(state)}"></span>'
            f'<span>{html.escape(label)}</span>'
            f'<span class="cw-process-detail">{html.escape(detail)}</span>'
            "</div>"
        )
    body.append("</div>")
    st.html("".join(body))


def sources(app, message):
    citations = message.get("citations") or []
    if not citations:
        st.caption("无引用")
        return
    chunks = {chunk.get("chunk_id"): chunk for chunk in message.get("retrieved_chunks", [])}
    documents = app.list_documents()
    for citation in citations:
        citation_id = citation.get("citation_id", "?")
        file_name = citation.get("file_name") or "未命名文件"
        page = citation.get("page_number")
        citation_key = html.escape(str(citation_id), quote=True)
        card = [
            f'<div class="cw-source-card" data-citation-id="{citation_key}">',
            f'<strong>[{html.escape(str(citation_id))}] {html.escape(str(file_name))}</strong>',
            f'<small>{html.escape("第 " + str(page) + " 页" if page is not None else "页码 未提供")}</small>',
            "</div>",
        ]
        st.html("".join(card))
        chunk = chunks.get(citation.get("chunk_id"))
        if not chunk:
            st.caption("未返回引用片段")
            continue
        source_text = chunk.get("text") or ""
        preview, truncated = _source_preview(source_text)
        if preview:
            st.html(f'<div class="cw-source-preview">{html.escape(preview)}</div>')
        if truncated:
            with st.expander("展开完整片段", expanded=False):
                render_markdown(
                    source_text,
                    citations=[],
                    streaming=False,
                    key=f"chunk-{message.get('message_id')}-{citation_id}",
                )
        document = next(
            (
                item
                for item in documents
                if item.get("document_id") == chunk.get("document_id") and item.get("status") == "ready"
            ),
            None,
        )
        path = Path(document["path"]) if document.get("path") else None
        if path and path.is_file():
            st.download_button(
                "下载原文",
                path.read_bytes(),
                file_name=document.get("file_name", "document"),
                key=f"download-{message.get('message_id')}-{citation_id}",
            )
        else:
            st.caption("原文件已删除；保留本次引用快照")


def trace(message, events):
    live_timeline(events)
    visible_events = []
    for index, event in enumerate(events or []):
        name = event.get("event")
        # Streaming answer chunks are useful for the live timeline, but one
        # expander per chunk would swamp the detailed execution view.
        if name in {"run_started", "token", "answer_token"}:
            continue
        if name == "tool_started" and event.get("payload", {}).get("call_id"):
            call_id = event["payload"]["call_id"]
            finished = any(
                later.get("event") == "tool_finished"
                and (later.get("payload", {}).get("result") or {}).get("call_id") == call_id
                for later in (events or [])[index + 1 :]
            )
            if finished:
                continue
        info = _event_info(event)
        if not info:
            continue
        visible_events.append((event, info))

    if visible_events:
        for event, (label, detail, state) in visible_events:
            payload = event.get("payload") or event.get("metadata") or {}
            details = {
                "sequence": event.get("sequence"),
                "timestamp": event.get("timestamp"),
                "step_index": event.get("step_index"),
                "tool_name": event.get("tool_name"),
                "phase": event.get("phase"),
                "payload": payload,
                "citations": event.get("citations") or [],
                "retrieved_chunks": event.get("retrieved_chunks") or [],
            }
            if event.get("error"):
                details["error"] = event["error"]
            with st.expander(f"{label} · {detail}", expanded=False):
                st.json(details, expanded=True)
        return

    # Old or partially persisted runs may contain a trace without transport
    # events. Keep that data inspectable as a graceful fallback.
    steps = message.get("trace") or []
    if steps:
        for step in steps:
            status = step.get("status") or "completed"
            with st.expander(f"步骤 {step.get('step_index', 0) + 1} · {status}", expanded=False):
                thought = step.get("thought")
                if thought:
                    st.markdown("**Thought**")
                    render_markdown(str(thought), citations=[], streaming=False, key=f"thought-{step.get('step_index')}")
                if step.get("calls"):
                    st.caption("Action")
                    st.json(step.get("calls"), expanded=True)
                for observation in step.get("observations", []):
                    name = _tool_name(observation.get("tool_name"))
                    ok = observation.get("ok")
                    latency = observation.get("latency_ms")
                    detail = "完成" if ok else "失败 · 可继续"
                    if latency is not None:
                        detail += f" · {float(latency):.0f} ms"
                    st.markdown(f"**{name}** · {detail}")
                    st.caption("Observation")
                    st.json(observation, expanded=True)
        return

    if not events:
        st.caption("无执行轨迹")


def metrics(message, events):
    latency = message.get("latency_ms")
    usage = message.get("token_usage")
    token_text = _token_text(usage)
    values = [
        ("耗时", f"{float(latency) / 1000:.2f} 秒" if latency is not None else "未提供"),
        ("Token", token_text),
        ("引用", str(len(message.get("citations") or []))),
        ("事件", str(len(events or []))),
    ]
    st.html('<div class="cw-metric-grid">' + "".join(
        f'<div class="cw-metric"><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong></div>'
        for label, value in values
    ) + "</div>")


def inspector(app, message):
    st.subheader("回答详情")
    if not message:
        st.caption("无可检查的回答")
        return
    try:
        events = app.read_events(message["run_id"])["events"]
    except (KeyError, ValueError):
        events = []
    tabs = st.tabs(["引用", "执行过程", "指标"])
    with tabs[0]:
        sources(app, message)
    with tabs[1]:
        trace(message, events)
    with tabs[2]:
        metrics(message, events)

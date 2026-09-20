import html

import streamlit as st

from src.frontend.components.page import render_page_header


def _status_class(ok):
    if ok is True:
        return "cw-status-ok"
    if ok is False:
        return "cw-status-error"
    return "cw-status-pending"


def _row(label, value, class_name=""):
    return (
        '<div class="cw-status-row">'
        f"<span>{html.escape(str(label))}</span>"
        f'<strong class="{class_name}">{html.escape(str(value))}</strong>'
        "</div>"
    )


def _token_text(usage):
    if not usage:
        return "未提供"
    if isinstance(usage, dict):
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
    return str(usage)


def _probe_rows(probe):
    if not probe:
        return _row("连接探测", "未验证", "cw-status-pending")
    rows = [_row("最近探测", probe.get("checked_at") or "未提供")]
    for key, label in (("llm", "DeepSeek API"), ("retrieval", "混合检索")):
        item = probe.get(key) or {}
        rows.append(_row(label, item.get("message") or "未提供", _status_class(item.get("ok"))))
    return "".join(rows)


def render(app):
    status = app.get_status()
    documents = app.list_documents()
    kb = status.get("knowledge_base") or {}
    metrics = status.get("metrics") or {}
    probe = status.get("probe")
    run_records = app.db.list("run")
    answer_records = [item for item in app.db.list("message") if item.get("role") == "assistant"]
    recorded_latencies = [
        float(item["latency_ms"])
        for item in answer_records
        if isinstance(item.get("latency_ms"), (int, float)) and not isinstance(item.get("latency_ms"), bool)
    ]
    history_count = len(run_records)
    history_latency = sum(recorded_latencies) if recorded_latencies else None

    ready_count = sum(item.get("status") == "ready" for item in documents)
    render_page_header("系统状态", f"{ready_count} / {len(documents)} 已就绪", key="cw_status_header")

    with st.container(key="cw_status_body"):
        actions = st.columns([1.1, 1.1, 4], gap="small")
        with actions[0]:
            if st.button("检查连接", type="primary", disabled=app.busy, use_container_width=True):
                app.probe_dependencies()
                st.rerun()
        with actions[1]:
            if st.button("恢复索引", disabled=app.busy, use_container_width=True):
                app.repair()
                st.rerun()

        left, right = st.columns(2, gap="large")
        with left:
            st.subheader("服务")
            st.html(
                '<div class="cw-status-card">'
                + _row("服务", status.get("provider", "未提供"))
                + _row("模型", status.get("model", "未提供"))
                + _row("API 配置", status.get("llm", "未提供"), "cw-status-pending" if "未验证" in str(status.get("llm")) else "")
                + _row("Embedding", (status.get("embedding") or {}).get("status", "未提供"), "cw-status-pending" if "未验证" in str((status.get("embedding") or {}).get("status")) else "")
                + _probe_rows(probe)
                + "</div>"
            )
        with right:
            st.subheader("知识库")
            dirty = kb.get("dirty")
            dirty_text = "待修复" if dirty else "正常"
            dirty_class = "cw-status-error" if dirty else "cw-status-ok"
            st.html(
                '<div class="cw-status-card">'
                + _row("本地文件", f"{len(documents)} 个")
                + _row("已就绪", f"{ready_count} 个")
                + _row("索引", dirty_text, dirty_class)
                + _row("版本", kb.get("version") or "未提供")
                + "</div>"
            )

        st.subheader("运行指标")
        runs = history_count
        calls = sum(item.get("calls", 0) for item in (metrics.get("tools") or {}).values())
        successes = sum(item.get("successes", 0) for item in (metrics.get("tools") or {}).values())
        success_rate = f"{successes / calls:.0%}" if calls else "未提供"
        cards = st.columns(4, gap="small")
        card_values = (
            ("历史请求", str(runs) if runs else "0"),
            ("总响应耗时", f"{history_latency / 1000:.2f} 秒" if history_latency is not None else "未提供"),
            ("Token", _token_text(metrics.get("token_usage"))),
            ("工具成功率", success_rate),
        )
        for column, (label, value) in zip(cards, card_values):
            with column:
                st.metric(label, value)

        tools = metrics.get("tools") or {}
        if tools:
            st.subheader("工具调用")
            st.table(
                [
                    {
                        "工具": name,
                        "调用": data.get("calls", 0),
                        "成功": data.get("successes", 0),
                        "失败": data.get("failures", 0),
                        "成功率": f'{data["success_rate"]:.0%}' if data.get("success_rate") is not None else "未提供",
                    }
                    for name, data in tools.items()
                ]
            )

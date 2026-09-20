import streamlit as st

from src.frontend.components.markdown import render_markdown
from src.frontend.components.page import render_page_header


SUMMARY_FIELDS = (
    ("background", "研究背景"),
    ("method", "研究方法"),
    ("results", "实验结果"),
    ("conclusion", "结论"),
)


def _label(paper):
    title = paper.get("title") or "未提取标题"
    file_name = paper.get("file_name") or "未命名文件"
    stem = file_name.rsplit(".", 1)[0]
    if title.strip().casefold() == stem.strip().casefold():
        return file_name
    return f"{title} · {file_name}" if paper.get("title") else file_name


def _value(value):
    if value in (None, "", [], {}):
        return "未提取到"
    if isinstance(value, list):
        return "、".join(map(str, value))
    return str(value)


def _run(app, name, arguments):
    try:
        result = app.run_paper_tool(name, arguments)
    except (ValueError, OSError) as exc:
        st.session_state.analysis_result = None
        st.session_state.analysis_error = str(exc)
        return
    if result.get("ok"):
        st.session_state.analysis_result = result.get("data") or {}
        st.session_state.analysis_error = None
    else:
        st.session_state.analysis_result = None
        st.session_state.analysis_error = result.get("error") or "分析失败"


def _render_summary(result):
    for field, title in SUMMARY_FIELDS:
        st.markdown(f"### {title}")
        render_markdown(str(result.get(field) or "未提取到"), citations=[], streaming=False, key=f"analysis-{field}")


def _render_compare(result):
    left = result.get("paper_a") or {}
    right = result.get("paper_b") or {}
    fields = (
        ("title", "标题"),
        ("year", "年份"),
        ("authors", "作者"),
        ("method", "方法"),
        ("datasets", "数据集"),
        ("results", "实验结果"),
        ("abstract", "摘要"),
    )
    st.table(
        [
            {"对比维度": label, "论文 A": _value(left.get(field)), "论文 B": _value(right.get(field))}
            for field, label in fields
        ]
    )


def render(app):
    papers = app.list_ready_papers()
    render_page_header("论文分析", f"{len(papers)} 份已就绪", key="cw_analysis_header")

    if not papers:
        with st.container(key="cw_analysis_body"):
            st.info("没有已就绪论文")
            if st.button("上传论文", type="primary"):
                st.session_state.page = "知识库"
                st.rerun()
        return

    with st.container(key="cw_analysis_body"):
        paper_map = {paper["paper_id"]: paper for paper in papers}
        mode = st.radio(
            "分析模式",
            ["摘要", "对比"],
            horizontal=True,
            key="analysis_mode",
            label_visibility="collapsed",
        )
        if mode == "摘要":
            with st.form("summary-form"):
                controls = st.columns([4, 1.15], vertical_alignment="bottom", gap="medium")
                with controls[0]:
                    selected = st.selectbox(
                        "选择论文",
                        list(paper_map),
                        format_func=lambda value: _label(paper_map[value]),
                    )
                with controls[1]:
                    submitted = st.form_submit_button("生成摘要", type="primary", disabled=app.busy, use_container_width=True)
            if submitted:
                _run(app, "paper_summary", {"paper_id": selected})
        else:
            with st.form("compare-form"):
                options = list(paper_map)
                controls = st.columns([1, 1, .7], vertical_alignment="bottom", gap="medium")
                with controls[0]:
                    left = st.selectbox("论文 A", options, format_func=lambda value: _label(paper_map[value]))
                with controls[1]:
                    right = st.selectbox(
                        "论文 B",
                        options,
                        index=1 if len(options) > 1 else 0,
                        format_func=lambda value: _label(paper_map[value]),
                    )
                with controls[2]:
                    submitted = st.form_submit_button("比较论文", type="primary", disabled=app.busy, use_container_width=True)
            if submitted:
                if left == right:
                    st.session_state.analysis_result = None
                    st.session_state.analysis_error = "请选择两篇不同论文"
                else:
                    _run(app, "paper_compare", {"paper_a": left, "paper_b": right})

        if st.session_state.analysis_error:
            st.error(st.session_state.analysis_error)
        result = st.session_state.analysis_result
        if isinstance(result, dict):
            with st.container(key="cw_analysis_result"):
                st.html('<div class="cw-result-heading"><strong>分析结果</strong></div>')
                if mode == "摘要" and any(field in result for field, _ in SUMMARY_FIELDS):
                    _render_summary(result)
                elif mode == "对比" and "paper_a" in result:
                    _render_compare(result)
                if st.button("继续提问"):
                    st.session_state.page = "聊天"
                    st.session_state.conversation_id = None
                    st.session_state.selected_message = None
                    st.rerun()

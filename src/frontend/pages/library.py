import html
from pathlib import Path

import streamlit as st

from src.frontend.components.page import render_page_header


STATUS_LABELS = {
    "ready": ("已就绪", "cw-ready"),
    "pending": ("等待处理", "cw-pending"),
    "processing": ("处理中", "cw-pending"),
    "failed": ("解析失败", "cw-failed"),
    "deleting": ("删除中", "cw-pending"),
}


@st.dialog("删除文件")
def confirm_delete(app, document):
    st.write(f"确认删除「{document['file_name']}」？")
    st.caption("历史回答中的引用快照会保留")
    if st.button("确认删除", type="primary"):
        try:
            app.delete_document(document["document_id"])
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def _format_size(size):
    size = float(size or 0)
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024:.0f} KB"


def _jobs(app):
    return app.db.list("job")[-5:]


def _retry(app, job_id, document_id):
    try:
        app.retry_import(job_id, [document_id])
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(str(exc))


def render(app):
    documents = app.list_documents()
    ready_count = sum(document["status"] == "ready" for document in documents)
    render_page_header("知识库", f"{ready_count} / {len(documents)} 已就绪", key="cw_library_header")

    with st.container(key="cw_library_body"):
        upload, limits = st.columns([2.25, 1], gap="large", vertical_alignment="top")
        with upload:
            st.subheader("导入文件")
            with st.form("cw_upload_form", clear_on_submit=True):
                uploader, action = st.columns([4.9, 0.9], gap="small", vertical_alignment="center")
                with uploader:
                    files = st.file_uploader(
                        "选择文件",
                        type=["pdf", "docx", "txt", "md"],
                        accept_multiple_files=True,
                        disabled=app.busy,
                        label_visibility="collapsed",
                    )
                with action:
                    submitted = st.form_submit_button(
                        "导入知识库",
                        type="primary",
                        disabled=app.busy,
                    )
                if submitted:
                    try:
                        if not files:
                            raise ValueError("请选择文件")
                        app.submit_import([(file.name, file.getvalue()) for file in files])
                        st.rerun()
                    except (ValueError, OSError) as exc:
                        st.error(str(exc))
        with limits:
            st.subheader("限制")
            st.html(
                '<div class="cw-limit-list">'
                '<div><span>格式</span><strong>PDF · DOCX · TXT · Markdown</strong></div>'
                '<div><span>单文件</span><strong>≤ 50 MB</strong></div>'
                '<div><span>单批</span><strong>≤ 20 个</strong></div>'
                '</div>'
            )

        st.html('<div class="cw-content-rule"></div>')
        was_busy = app.busy

        @st.fragment(run_every=0.8)
        def documents_panel():
            current = app.list_documents()
            ready_ids = {
                document.get("document_id")
                for document in current
                if document.get("status") == "ready"
            }
            jobs = _jobs(app)
            visible_jobs = [
                job
                for job in jobs
                if job.get("items")
                and (
                    job.get("status") in ("queued", "running", "failed", "partial")
                    or any(item.get("status") == "failed" for item in job.get("items", []))
                )
                and (
                    job.get("status") in ("queued", "running")
                    or any(
                        item.get("status") == "failed"
                        and item.get("document_id") not in ready_ids
                        for item in job.get("items", [])
                    )
                )
            ]
            # Keep the queue readable when the workspace contains several
            # retries for the same batch. The document table still exposes
            # each file's current status and retry action.
            visible_jobs = visible_jobs[-1:]
            if visible_jobs:
                st.html('<div class="cw-list-heading"><strong>处理队列</strong><span>最近任务</span></div>')
                for job in visible_jobs:
                    items = job.get("items", [])
                    failed = [item for item in items if item.get("status") == "failed"]
                    completed = sum(item.get("status") in ("completed", "ready", "skipped") for item in items)
                    if job.get("status") in ("queued", "running"):
                        st.progress(completed / max(job.get("total", 1), 1), text=job.get("stage") or "处理中")
                    job_status = {
                        "queued": "等待处理",
                        "running": "处理中",
                        "partial": "部分失败",
                        "failed": "失败",
                    }.get(job.get("status"), job.get("status"))
                    st.html(
                        f'<div class="cw-job-summary"><strong>{html.escape(str(job_status))}</strong>'
                        f' <span>已完成 {completed} / {len(items)}</span>'
                        + (f' <span class="cw-failed">· 失败 {len(failed)}</span>' if failed else "")
                        + "</div>"
                    )
                    if job.get("error"):
                        st.html(f'<div class="cw-inline-error">{html.escape(str(job["error"]))}</div>')
                    for item in failed:
                        columns = st.columns([5, 1], vertical_alignment="center")
                        with columns[0]:
                            st.caption(f"{item.get('file_name', '文件')} · {item.get('error') or '解析失败'}")
                        with columns[1]:
                            if st.button("重试", key=f"retry-{job['job_id']}-{item['document_id']}", disabled=app.busy):
                                _retry(app, job["job_id"], item["document_id"])

            st.html(
                f'<div class="cw-list-heading cw-documents-heading"><strong>文档</strong><span>{len(current)} 个</span></div>'
            )
            if not current:
                st.info("知识库为空")
                return

            with st.container(key="cw_documents_list"):
                st.html(
                    '<div class="cw-document-header"><span>文件</span><span>大小</span><span>片段</span><span>状态</span><span>操作</span></div>'
                )
                jobs_by_document = {
                    item.get("document_id"): job
                    for job in _jobs(app)
                    for item in job.get("items", [])
                    if item.get("document_id")
                }
                for document in current:
                    status_text, status_class = STATUS_LABELS.get(document.get("status"), (document.get("status"), ""))
                    name = html.escape(str(document.get("file_name", "未命名文件")))
                    error = document.get("error")
                    row = st.container()
                    with row:
                        values = st.columns([2.5, .8, .7, .8, 1], vertical_alignment="center")
                        with values[0]:
                            st.html(
                                f'<div class="cw-document-name"><strong>{name}</strong>'
                                + (f'<small>{html.escape(str(error))}</small>' if error else "")
                                + "</div>"
                            )
                        with values[1]:
                            st.caption(_format_size(document.get("size")))
                        with values[2]:
                            st.caption(str(document.get("chunk_count") or "—"))
                        with values[3]:
                            st.html(f'<span class="{status_class}">{html.escape(str(status_text))}</span>')
                        with values[4]:
                            actions = st.columns(2)
                            if document.get("status") == "failed":
                                job = jobs_by_document.get(document.get("document_id"))
                                if job and actions[0].button("重试", key=f"row-retry-{document['document_id']}", disabled=app.busy):
                                    _retry(app, job["job_id"], document["document_id"])
                            if actions[1].button("删除", key=f"delete-doc-{document['document_id']}", disabled=app.busy):
                                confirm_delete(app, document)

            if was_busy and not app.busy:
                st.rerun()

        documents_panel()

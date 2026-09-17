import html

import streamlit as st


@st.dialog('删除文件')
def confirm_delete(app, document):
    st.write(f"「{document['file_name']}」将从本地知识库和索引中删除。")
    if st.button('确认删除', type='primary'):
        try:
            app.delete_document(document['document_id'])
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def render(app):
    documents = app.list_documents()
    ready_count = sum(document['status'] == 'ready' for document in documents)
    st.html('<div class="cw-toolbar">LOCAL INDEX</div>')
    st.title('知识库')
    st.caption(f'{ready_count} 个文件可检索 · 支持 PDF、DOCX、TXT 和 Markdown')
    st.html('<div class="cw-rule"></div>')

    upload, note = st.columns([2.1, 1], gap='large')
    with upload:
        st.subheader('添加文件')
        with st.form('upload-form', clear_on_submit=True):
            files = st.file_uploader('选择文件', type=['pdf', 'docx', 'txt', 'md'], accept_multiple_files=True, disabled=app.busy)
            submitted = st.form_submit_button('加入知识库', type='primary', disabled=app.busy, use_container_width=True)
            if submitted:
                try:
                    app.submit_import([(file.name, file.getvalue()) for file in files])
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
    with note:
        st.subheader('处理规则')
        st.caption('单个文件不超过 50 MB，每次最多 20 个。文件只保存在当前工作区，重复内容不会再次建索引。')

    was_busy = app.busy

    @st.fragment(run_every=0.8)
    def documents_panel():
        jobs = app.db.list('job')[-3:]
        for job in jobs:
            if job['status'] in ('queued', 'running'):
                st.progress(job['completed'] / max(job['total'], 1), text=job['stage'])
            if job.get('error'):
                st.warning(job['error'])
            failed = [item['document_id'] for item in job['items'] if item['status'] == 'failed']
            if failed and st.button('重试未完成文件', key='retry-job-' + job['job_id'], disabled=app.busy):
                try:
                    app.retry_import(job['job_id'], failed)
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))

        current = app.list_documents()
        st.html(f'<div class="cw-section-label">文件 / {len(current)}</div>')
        if not current:
            st.info('还没有文件。上传后会自动解析并建立本地索引。')
        labels = {'ready': '可检索', 'pending': '等待处理', 'processing': '正在处理', 'failed': '处理失败', 'deleting': '正在删除'}
        for document in current:
            info, action = st.columns([6, 1], vertical_alignment='center')
            with info:
                file_name = html.escape(document['file_name'])
                st.html(
                    f'<div class="cw-doc-row"><strong>{file_name}</strong>'
                    f"<small>{labels[document['status']]} · {document['size']/1024:.1f} KB · {document['chunk_count']} 个片段</small></div>"
                )
                if document['error']:
                    st.warning(document['error'])
            with action:
                if st.button('删除', key='delete-doc-' + document['document_id'], disabled=app.busy):
                    confirm_delete(app, document)
        if was_busy and not app.busy:
            st.rerun()

    documents_panel()

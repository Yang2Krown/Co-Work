"""Present deterministic paper tools without leaking JSON into the reading flow."""
import json
import streamlit as st

def render_answer(message):
    content = message.get('content') or ''
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, dict) and isinstance(data.get('paper_a'), dict) and isinstance(data.get('paper_b'), dict):
        labels = {'title': '标题', 'year': '年份', 'authors': '作者', 'method': '方法', 'datasets': '数据集', 'results': '实验结果', 'abstract': '摘要'}
        def display(value):
            if not value:
                return '未提取到'
            return '、'.join(map(str, value)) if isinstance(value, list) else str(value)
        rows = [{'对比维度': label, '论文 A': display(data['paper_a'].get(field)), '论文 B': display(data['paper_b'].get(field))} for field, label in labels.items()]
        st.table(rows)
        st.caption('基于论文目录的结构化字段对比，缺失字段不补写结论。')
    elif isinstance(data, dict) and any(k in data for k in ('background', 'conclusion')):
        for field, title in [('background', '研究背景'), ('method', '研究方法'), ('results', '实验结果'), ('conclusion', '结论')]:
            st.markdown('**' + title + '**')
            st.write(data.get(field) or '未提取到')
    else:
        st.markdown(content or ('正在执行…' if message['status'] in ('queued', 'running') else '未产生回答'))
    if content and message['role'] == 'assistant':
        with st.expander('复制原始回答'):
            st.code(content, language=None, wrap_lines=True)

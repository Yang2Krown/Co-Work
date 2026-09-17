from pathlib import Path
import streamlit as st

TOOL_NAMES = {'knowledge_retrieval': '知识库检索', 'paper_metadata': '论文元信息', 'paper_compare': '论文对比',
              'paper_summary': '论文摘要', 'keyword_extract': '关键词提取', 'calculator': '计算器',
              'current_time': '当前时间', 'web_search': '联网搜索'}

def sources(app, message):
    citations = message.get('citations') or []
    if not citations:
        st.caption('当前回答没有可用引用。')
    chunks = {c['chunk_id']: c for c in message.get('retrieved_chunks', [])}
    for citation in citations:
        page = citation.get('page_number')
        st.markdown(f"**[{citation['citation_id']}] {citation['file_name']}**")
        st.caption(f'第 {page} 页' if page is not None else '未提供页码')
        chunk = chunks.get(citation.get('chunk_id'))
        if chunk:
            st.markdown(chunk['text'])
            document = next((d for d in app.list_documents() if d['document_id'] == chunk['document_id'] and d['status'] == 'ready'), None)
            if document and Path(document['path']).is_file():
                st.download_button('下载原文', Path(document['path']).read_bytes(), file_name=document['file_name'],
                    key=f"download-{message['message_id']}-{citation['citation_id']}")
            else:
                st.caption('原文件已删除或不可用；保留本次引用快照。')
        else:
            st.caption('未返回引用片段。')
        st.divider()

def trace(message, events):
    steps = message.get('trace') or []
    if steps:
        for step in steps:
            with st.expander(f"步骤 {step['step_index'] + 1} · {step['status']}"):
                st.caption('Thought')
                st.write(step.get('thought') or '未提供')
                st.caption('Action')
                st.json(step.get('calls', []), expanded=False)
                st.caption('Observation')
                for observation in step.get('observations', []):
                    st.write(TOOL_NAMES.get(observation['tool_name'], observation['tool_name']))
                    st.caption(f"{'完成' if observation['ok'] else '失败'} · {observation['latency_ms']:.0f} ms")
                    data = observation.get('data')
                    if isinstance(data, dict) and data.get('latency_source'):
                        st.caption('RAG 总响应耗时' if data['latency_source'] == 'backend_response_latency' else '检索耗时')
                    st.json(observation, expanded=False)
    else:
        for index, event in enumerate(events):
            name, payload = event['event'], event.get('payload', {})
            if name == 'thought':
                with st.expander('Thought · 执行计划'):
                    st.write(payload.get('thought', ''))
            elif name in ('tool_started', 'tool_finished'):
                result = payload.get('result', {})
                call_id = payload.get('call_id') or result.get('call_id')
                if name == 'tool_started' and call_id and any(
                    e['event'] == 'tool_finished' and e.get('payload', {}).get('result', {}).get('call_id') == call_id
                    for e in events[index + 1:]
                ):
                    continue
                marker = '○ ' if name == 'tool_started' else ('✓ ' if result.get('ok') else '! 失败 · ')
                st.write(marker + TOOL_NAMES.get(event.get('tool_name'), event.get('tool_name', '工具')))
                with st.expander('Action / Observation', expanded=False):
                    st.json(payload, expanded=False)
        if not events:
            st.caption('执行后可在这里查看工具轨迹。')

def inspector(app, message):
    st.subheader('检查器')
    if not message:
        st.caption('选择一条回答以查看来源与执行过程。')
        return
    tabs = st.tabs(['引用', '执行过程'])
    with tabs[0]:
        sources(app, message)
    with tabs[1]:
        events = app.read_events(message['run_id'])['events']
        trace(message, events)
        if message.get('latency_ms') is not None:
            st.caption(f"总响应耗时 {message['latency_ms'] / 1000:.2f} 秒")
        usage = message.get('token_usage')
        st.caption('Token：未提供' if usage is None else f'Token：{usage}')

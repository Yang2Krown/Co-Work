from pathlib import Path
import streamlit as st

TOOL_NAMES = {'knowledge_retrieval': '知识库检索', 'paper_metadata': '论文元信息', 'paper_compare': '论文对比',
              'paper_summary': '论文摘要', 'keyword_extract': '关键词提取', 'calculator': '计算器',
              'current_time': '当前时间', 'web_search': '联网搜索'}


def _event_label(event):
    name = event.get('event')
    payload = event.get('payload') or event.get('metadata') or {}
    if name == 'route_selected':
        return ('✓ ', '规则路由：直接调用 ' + TOOL_NAMES.get(payload.get('tool_name'), payload.get('tool_name') or '工具')) if not payload.get('uses_llm') else ('○ ', '进入 LLM ReAct 规划')
    if name == 'llm_started': return '○ ', 'LLM 调用中 · ' + str(payload.get('phase') or '生成')
    if name == 'llm_finished': return ('✓ ' if payload.get('ok', True) else '! ', 'LLM 调用完成 · ' + str(payload.get('phase') or '生成'))
    if name == 'retrieval_started': return '○ ', '正在执行混合检索（向量 + BM25）'
    if name == 'retrieval_finished': return '✓ ', '混合检索完成 · {} 个片段'.format(payload.get('chunk_count', '?'))
    if name == 'metadata': return '✓ ', '已获取引用与检索片段'
    if name in ('answer_token', 'token'): return '… ', '正在流式生成回答'
    if name == 'tool_started': return '○ ', '工具运行中：' + TOOL_NAMES.get(event.get('tool_name'), event.get('tool_name', '工具'))
    if name == 'tool_finished':
        result = payload.get('result', {})
        return ('✓ ' if result.get('ok') else '! ', ('工具完成：' if result.get('ok') else '工具失败：') + TOOL_NAMES.get(event.get('tool_name'), event.get('tool_name', '工具')))
    if name == 'final': return '✓ ', '已生成最终回答'
    if name == 'error': return '! ', '执行异常：' + str(payload.get('error') or event.get('error') or '未知错误')
    if name in ('end', 'run_finished'): return '✓ ', '本轮执行结束'
    return None


def live_timeline(events, compact=False):
    visible = []
    for event in events:
        label = _event_label(event)
        if label and (event.get('event') not in ('token', 'answer_token') or not visible or visible[-1][1] != label[1]):
            visible.append(label)
    if compact:
        visible = visible[-6:]
    if not visible:
        return
    with st.container(border=True):
        st.caption('实时执行流')
        for marker, text in visible:
            st.write(marker + text)

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
    live_timeline(events)
    steps = message.get('trace') or []
    if steps:
        for step in steps:
            with st.expander(f"步骤 {step['step_index'] + 1} · {step['status']}"):
                st.caption('行动摘要')
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
            elif name in ('route_selected', 'llm_started', 'llm_finished', 'retrieval_started',
                          'retrieval_finished', 'metadata', 'error', 'end', 'run_finished'):
                label = _event_label(event)
                if not label:
                    continue
                with st.expander(label[1], expanded=False):
                    details = {
                        'sequence': event.get('sequence'),
                        'timestamp': event.get('timestamp'),
                        'step_index': event.get('step_index'),
                        'tool_name': event.get('tool_name'),
                        'phase': event.get('phase'),
                        'payload': payload or event.get('metadata') or {},
                        'citations': event.get('citations') or [],
                        'retrieved_chunks': event.get('retrieved_chunks') or [],
                    }
                    if event.get('error'):
                        details['error'] = event['error']
                    st.json(details, expanded=False)
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

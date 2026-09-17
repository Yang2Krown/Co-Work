import streamlit as st

from src.frontend.components.answer import render_answer
from src.frontend.components.details import inspector, live_timeline


def send(app, message, metadata=None):
    try:
        if not st.session_state.conversation_id:
            conversation = app.create_conversation('agent')
            st.session_state.conversation_id = conversation['conversation_id']
        app.start_turn(st.session_state.conversation_id, message, metadata)
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(str(exc))


def render(app):
    if st.session_state.pop('open_inspector', False):
        st.session_state.inspector = True

    title, controls = st.columns([5, 1.2], vertical_alignment='bottom')
    with title:
        st.html('<div class="cw-toolbar">连接正常</div>')
        st.title('聊天')
    with controls:
        st.toggle('显示来源', key='inspector')
    st.html('<div class="cw-rule"></div>')

    if app.get_status()['knowledge_base'].get('dirty'):
        st.warning('上次文档处理未完成，请在知识库中重试失败文件。')

    was_busy = app.busy

    @st.fragment(run_every=0.25)
    def conversation_panel():
        active = app.get_conversation(st.session_state.conversation_id) if st.session_state.conversation_id else None
        messages = active['messages'] if active else []
        if st.session_state.inspector:
            body, side = st.columns([2.15, 1], gap='large')
        else:
            body, side = st.container(), None
        with body:
            for message in messages:
                avatar = ':material/person:' if message['role'] == 'user' else ':material/auto_awesome:'
                with st.chat_message(message['role'], avatar=avatar):
                    render_answer(message)
                    if message['role'] == 'assistant' and message['status'] in ('queued', 'running'):
                        try:
                            live_timeline(app.read_events(message['run_id'])['events'], compact=True)
                        except ValueError:
                            pass
                    if message.get('error'):
                        st.error(message['error'])
                    if message['role'] == 'assistant':
                        actions = st.columns([1, 1, 4])
                        citations = message.get('citations') or []
                        if actions[0].button(f'来源 {len(citations)}', key='cite-' + message['message_id']):
                            st.session_state.selected_message = message['message_id']
                            st.session_state.open_inspector = True
                            st.rerun()
                        if actions[1].button('详情', key='details-' + message['message_id']):
                            st.session_state.selected_message = message['message_id']
                            st.session_state.open_inspector = True
                            st.rerun()
                        if message['status'] in ('failed', 'interrupted', 'max_iterations'):
                            if st.button('重试', key='retry-' + message['message_id'], disabled=app.busy):
                                user = next(m for m in messages if m['run_id'] == message['run_id'] and m['role'] == 'user')
                                send(app, user['content'], app.db.get('run', message['run_id']).get('metadata', {}))
            if app.busy:
                st.status((app.operation or '正在处理') + '…', state='running')
            if not messages:
                st.html('<div class="cw-composer-space"></div>')
            if text := st.chat_input('发消息', disabled=app.busy, max_chars=8000):
                send(app, text)
        if side:
            with side:
                answers = [m for m in messages if m['role'] == 'assistant']
                selected = next((m for m in answers if m['message_id'] == st.session_state.selected_message), answers[-1] if answers else None)
                inspector(app, selected)
        if was_busy and not app.busy:
            st.rerun()

    conversation_panel()

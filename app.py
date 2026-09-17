"""Run with: streamlit run app.py"""
import os

import streamlit as st
from src.frontend.state import application, initialize
from src.frontend.theme import apply_theme
from src.frontend.pages import workspace, library

st.set_page_config(page_title='Co-Work', page_icon=':material/library_books:', layout='wide', initial_sidebar_state='expanded')
apply_theme()
initialize()
app = application()

def connection_gate():
    st.html('''
    <div class="cw-setup-kicker">CO-WORK / CONNECTION</div>
    <div class="cw-setup-title">连接 DeepSeek</div>
    <div class="cw-setup-copy">工作区会先发起一次连接检查。验证通过后，才会开放文件上传和聊天。</div>
    ''')
    left, form = st.columns([1.15, 1], gap='large', vertical_alignment='center')
    with left:
        st.html('''
        <div class="cw-setup-notes">
          <div><span>01</span><strong>本地知识库</strong><small>文件与索引保存在当前工作区。</small></div>
          <div><span>02</span><strong>连接验证</strong><small>通过一次 API 请求确认 Key 可用。</small></div>
          <div><span>03</span><strong>仅本次运行</strong><small>Key 不写入 SQLite 或项目文件。</small></div>
        </div>
        ''')
    with form:
        with st.container(border=True):
            st.subheader('连接生成服务')
            st.caption('使用 DeepSeek API Key 完成一次连接检查。')
            with st.form('api-key-form'):
                api_key = st.text_input('API Key', type='password', placeholder='sk-...', autocomplete='off')
                submitted = st.form_submit_button('验证并进入', type='primary', use_container_width=True)
            if submitted:
                with st.spinner('正在检查连接…'):
                    ok, message = app.verify_api_key(api_key)
                if ok:
                    st.session_state.api_verified = True
                    st.session_state.api_error = None
                    st.rerun()
                st.session_state.api_error = message
            if st.session_state.api_error:
                st.error(st.session_state.api_error)
            elif not api_key and os.getenv('DEEPSEEK_API_KEY'):
                st.caption('已检测到运行环境中的 Key，可直接验证。')

if not st.session_state.api_verified:
    connection_gate()
    st.stop()

@st.dialog('删除会话')
def delete_conversation(identifier):
    st.write('将删除此会话和其中的所有消息。知识库文件不受影响。')
    if st.button('确认删除', type='primary'):
        app.delete_conversation(identifier)
        st.session_state.conversation_id = None
        st.rerun()

with st.sidebar:
    st.html('<div class="cw-window"><i></i><i></i><i></i><strong>Co-Work</strong></div>')
    st.caption('研究资料工作区')
    for page, icon in (('聊天', ':material/chat_bubble_outline:'), ('知识库', ':material/folder_open:')):
        kind = 'primary' if st.session_state.page == page else 'secondary'
        if st.button(page, icon=icon, type=kind, use_container_width=True):
            st.session_state.page = page
            st.rerun()
    st.divider()
    if st.button('新建会话', icon=':material/add:', use_container_width=True, disabled=app.busy):
        st.session_state.conversation_id = None
        st.session_state.selected_message = None
        st.session_state.page = '聊天'
        st.rerun()
    st.caption('最近会话')
    for c in app.list_conversations():
        if st.button(c['title'], key=c['conversation_id'], use_container_width=True):
            st.session_state.conversation_id = c['conversation_id']
            st.session_state.selected_message = None
            st.session_state.page = '聊天'
            st.rerun()
    if st.session_state.conversation_id:
        if st.button('删除当前会话', icon=':material/delete_outline:', disabled=app.busy, use_container_width=True):
            delete_conversation(st.session_state.conversation_id)
    st.html('<div class="cw-sidebar-spacer"></div>')
    ready_count = sum(d['status'] == 'ready' for d in app.list_documents())
    st.caption(f'已连接 · {ready_count} 份资料')

{'聊天': workspace.render, '知识库': library.render}[st.session_state.page](app)

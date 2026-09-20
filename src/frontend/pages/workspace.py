import streamlit as st

from src.frontend.components.answer import render_answer, render_copy_control
from src.frontend.components.details import inspector


def send(app, message, metadata=None):
    try:
        if not st.session_state.conversation_id:
            conversation = app.create_conversation("agent")
            st.session_state.conversation_id = conversation["conversation_id"]
        # The UI has one execution mode now, so neither an old shortcut nor a
        # historical conversation can route a new turn through the legacy
        # standalone RAG flow.
        app.start_turn(st.session_state.conversation_id, message, metadata, mode="agent")
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(str(exc))


def _go(page):
    st.session_state.page = page
    st.rerun()


def _empty_state():
    with st.container(key="cw_start_panel"):
        st.html('<div class="cw-empty-state"><h2>开始一轮论文研究</h2></div>')


def _quick_actions():
    with st.container(key="cw_quick_actions"):
        actions = st.columns(2, gap="small")
        with actions[0]:
            if st.button("上传论文", icon=":material/upload_file:", use_container_width=True):
                _go("知识库")
        with actions[1]:
            if st.button("比较论文", icon=":material/compare_arrows:", use_container_width=True):
                st.session_state.analysis_mode = "对比"
                _go("论文分析")


def render(app):
    if st.session_state.pop("open_inspector", False):
        st.session_state.inspector = True
    if not st.session_state.conversation_id:
        # A new/empty conversation has no message to inspect. Do not let a
        # previously opened inspector hide the start actions or composer.
        st.session_state.inspector = False

    status = app.get_status()
    if status.get("knowledge_base", {}).get("dirty"):
        st.warning("索引待修复")

    was_busy = app.busy

    @st.fragment(run_every=0.25)
    def conversation_panel():
        current = app.get_conversation(st.session_state.conversation_id) if st.session_state.conversation_id else None
        messages = current["messages"] if current else []
        if st.session_state.inspector and current:
            body, side = st.columns([2.25, 1], gap="large")
        else:
            body, side = st.container(), None
        with body:
            with st.container(key="cw_chat_column"):
                if not messages:
                    _empty_state()
                for message in messages:
                    avatar = ":material/person:" if message["role"] == "user" else ":material/auto_awesome:"
                    with st.chat_message(message["role"], avatar=avatar):
                        render_answer(message)
                        if message.get("error"):
                            st.error(message["error"])
                        if message["role"] == "assistant":
                            citations = message.get("citations") or []
                            retryable = message["status"] in ("failed", "interrupted", "max_iterations")
                            actions = st.columns([0.35, 1, 1, 1] if retryable else [0.35, 1, 1], gap="small")
                            with actions[0]:
                                if message.get("content"):
                                    render_copy_control(message["content"])
                            if actions[1].button(
                                f"来源 {len(citations)}",
                                key="cite-" + message["message_id"],
                                use_container_width=True,
                            ):
                                st.session_state.selected_message = message["message_id"]
                                st.session_state.open_inspector = True
                                st.rerun()
                            if actions[2].button(
                                "详情",
                                key="details-" + message["message_id"],
                                use_container_width=True,
                            ):
                                st.session_state.selected_message = message["message_id"]
                                st.session_state.open_inspector = True
                                st.rerun()
                            if retryable:
                                if actions[3].button(
                                    "重试",
                                    key="retry-" + message["message_id"],
                                    disabled=app.busy,
                                    use_container_width=True,
                                ):
                                    user = next(
                                        item for item in messages if item["run_id"] == message["run_id"] and item["role"] == "user"
                                    )
                                    run = app.db.get("run", message["run_id"]) or {}
                                    send(app, user["content"], metadata=run.get("metadata", {}))

        if side:
            with side:
                with st.container(key="cw_inspector_panel"):
                    answers = [message for message in messages if message["role"] == "assistant"]
                    selected = next(
                        (message for message in answers if message["message_id"] == st.session_state.selected_message),
                        answers[-1] if answers else None,
                    )
                    inspector(app, selected)
        if was_busy and not app.busy:
            st.rerun()

    with st.container(key="cw_body"):
        conversation_panel()
        if not st.session_state.inspector and not st.session_state.conversation_id:
            _quick_actions()
    if text := st.chat_input("发消息", disabled=app.busy, max_chars=8000):
        send(app, text)

"""Safe, shared Markdown rendering for the Streamlit frontend."""

import re

import streamlit as st


_FENCE_START = re.compile(r"^\s*(`{3,}|~{3,})([^\n]*)$")
_FENCE_BLOCK = re.compile(r"(?ms)^\s*(`{3,}|~{3,})([^\n]*)\n(.*?)^\s*\1\s*$")


def _unfinished_fence(content: str):
    """Return the safe text/code split when a streamed fence is still open."""
    marker = None
    language = ""
    code_start = None
    lines = content.splitlines()
    for index, line in enumerate(lines):
        match = _FENCE_START.match(line)
        if not match:
            continue
        fence = match.group(1)
        if marker is None:
            marker = fence[0]
            language = match.group(2).strip().split()[0] if match.group(2).strip() else ""
            code_start = index + 1
            continue
        if fence[0] == marker and len(fence) >= 3:
            marker = None
            language = ""
            code_start = None

    if marker is None or code_start is None:
        return None
    prefix = "\n".join(lines[: code_start - 1]).strip()
    code = "\n".join(lines[code_start:])
    return prefix, code, language


def render_markdown(
    content: str,
    *,
    citations: list[dict] | None,
    streaming: bool,
    key: str,
):
    """Render model content using Streamlit's native Markdown renderer.

    ``key`` is part of the shared renderer contract. Streamlit's Markdown
    element does not accept a key in all supported versions, so it is kept as
    a stable call-site identifier rather than passed to the component.
    """
    del citations, key
    text = str(content or "").strip()
    if not text:
        st.caption("正在生成回答" if streaming else "未产生回答")
        return

    partial = _unfinished_fence(text) if streaming else None
    if partial:
        prefix, code, language = partial
        if prefix:
            st.markdown(prefix, unsafe_allow_html=False)
        st.code(code, language=language or None, wrap_lines=True)
        return

    # Render fenced blocks with st.code so language information and the native
    # copy control remain available. Other content stays in native Markdown.
    matches = list(_FENCE_BLOCK.finditer(text))
    if not matches:
        st.markdown(text, unsafe_allow_html=False)
        return
    cursor = 0
    for match in matches:
        before = text[cursor : match.start()].strip()
        if before:
            st.markdown(before, unsafe_allow_html=False)
        language = match.group(2).strip().split()[0] if match.group(2).strip() else None
        st.code(match.group(3).rstrip("\n"), language=language, wrap_lines=True)
        cursor = match.end()
    after = text[cursor:].strip()
    if after:
        st.markdown(after, unsafe_allow_html=False)

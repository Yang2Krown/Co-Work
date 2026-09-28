import html

import streamlit as st


def render_page_header(title, meta="", *, key):
    """Render the compact header shared by non-chat pages."""
    meta_markup = (
        f'<span class="cw-page-meta">{html.escape(str(meta))}</span>'
        if meta
        else ""
    )
    with st.container(key=key):
        st.html(
            '<div class="cw-page-topbar">'
            f'<h1>{html.escape(str(title))}</h1>'
            f"{meta_markup}"
            "</div>"
        )

import os
from pathlib import Path
import streamlit as st
from src.application import Application
from src.application.bootstrap import ROOT

@st.cache_resource
def application():
    return Application(Path(os.getenv('COWORK_DATA_DIR', str(ROOT / 'data/workspace'))))

def initialize():
    defaults = {
        'page': '聊天',
        'conversation_id': None,
        'inspector': False,
        'selected_message': None,
        'api_verified': False,
        'api_error': None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

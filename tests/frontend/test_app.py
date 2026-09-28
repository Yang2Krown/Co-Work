"""UI reruns must not create work; deterministic Agent paths work without a key."""
import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest

@pytest.fixture
def page(tmp_path, monkeypatch):
    monkeypatch.setenv('COWORK_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    import src.application.runtime as runtime
    monkeypatch.setattr(runtime, 'load_dotenv', lambda: None)
    Application = runtime.Application
    monkeypatch.setattr(Application, 'verify_api_key', lambda self, api_key=None: (True, '连接成功'))
    from src.frontend.state import application
    application.clear()
    at = AppTest.from_file(Path(__file__).resolve().parents[2] / 'app.py', default_timeout=15).run()
    at.text_input[0].set_value('test-key')
    button(at, '验证并进入').click().run()
    yield at
    application().close()
    application.clear()


def button(page, label):
    return next(b for b in page.button if b.label == label)


def test_pages_and_empty_state(page):
    assert not page.exception
    button(page, '知识库').click().run()
    assert not page.exception
    assert any('知识库为空' in i.value for i in page.info)
    button(page, '聊天').click().run()
    assert not page.exception
    assert not page.radio
    assert not any(button.label == '查询知识库' for button in page.button)
    button(page, '论文分析').click().run()
    assert not page.exception
    assert any('没有已就绪论文' in i.value for i in page.info)
    button(page, '系统状态').click().run()
    assert not page.exception


def test_chat_reruns_and_inspector(page):
    from src.frontend.state import application
    app = application()
    page.chat_input[0].set_value('3 * 7').run()
    app.executor.submit(lambda: None).result(timeout=10)
    page.run()
    assert not page.exception
    assert len(app.db.list('run')) == 1
    assert app.db.list('run')[0]['mode'] == 'agent'
    assert app.list_conversations()[0]['mode'] == 'agent'
    assert any('21' in m.value for m in page.markdown)
    page.run()
    assert len(app.db.list('run')) == 1
    button(page, '详情').click().run()
    assert not page.exception
    assert page.session_state['inspector']
    assert len(app.list_conversations()) == 1
    assert len(app.db.list('run')) == 1

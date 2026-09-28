"""Answer shell: classify structured results and delegate body rendering."""

import base64
import html
import json

import streamlit as st

from src.frontend.components.markdown import render_markdown


_SUMMARY_FIELDS = (
    ("background", "研究背景"),
    ("method", "研究方法"),
    ("results", "实验结果"),
    ("conclusion", "结论"),
)


_CITATION_INTERACTION_SCRIPT = """
<script>
(() => {
  if (!window.__cwDecorateCitations) {
    window.__cwDecorateCitations = (root) => {
      const messages = root.querySelectorAll('[data-testid="stChatMessage"]');
      const sourceCards = () => Array.from(document.querySelectorAll('.cw-source-card[data-citation-id]'));

      messages.forEach((message) => {
        const chips = Array.from(message.querySelectorAll('.cw-chip[data-citation-id]'));
        if (!chips.length) return;

        const related = (citationId) => [
          ...Array.from(message.querySelectorAll('[data-citation-id]')),
          ...sourceCards(),
        ].filter((element) => element.dataset.citationId === citationId);

        const bind = (element, citationId) => {
          if (element.dataset.cwCitationBound === '1') return;
          element.dataset.cwCitationBound = '1';
          const setActive = (active) => {
            related(citationId).forEach((item) => item.classList.toggle('is-highlighted', active));
          };
          element.addEventListener('mouseenter', () => setActive(true));
          element.addEventListener('mouseleave', () => setActive(false));
          element.addEventListener('focus', () => setActive(true));
          element.addEventListener('blur', () => setActive(false));
        };

        const walker = document.createTreeWalker(message, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        let node;
        while ((node = walker.nextNode())) {
          const parent = node.parentElement;
          if (!parent || parent.closest('script,style,pre,code,button,iframe,.cw-citation-strip,.cw-inline-citation')) continue;
          if (/\[\d+\]/.test(node.nodeValue || '')) textNodes.push(node);
        }

        textNodes.forEach((textNode) => {
          const text = textNode.nodeValue || '';
          const matcher = /\[(\d+)\]/g;
          let cursor = 0;
          let match;
          const fragment = document.createDocumentFragment();
          let changed = false;
          while ((match = matcher.exec(text))) {
            const citationId = match[1];
            const chip = chips.find((item) => item.dataset.citationId === citationId);
            if (!chip) continue;
            if (match.index > cursor) fragment.appendChild(document.createTextNode(text.slice(cursor, match.index)));
            const marker = document.createElement('span');
            const source = chip.textContent.replace(/^\s*\[\d+\]\s*/, '').trim();
            marker.className = 'cw-inline-citation';
            marker.dataset.citationId = citationId;
            marker.dataset.source = source;
            marker.title = `来源 ${citationId}：${source}`;
            marker.setAttribute('aria-label', `引用 ${citationId}，${source}`);
            marker.tabIndex = 0;
            marker.textContent = match[0];
            bind(marker, citationId);
            fragment.appendChild(marker);
            cursor = match.index + match[0].length;
            changed = true;
          }
          if (!changed) return;
          if (cursor < text.length) fragment.appendChild(document.createTextNode(text.slice(cursor)));
          textNode.replaceWith(fragment);
        });

        chips.forEach((chip) => bind(chip, chip.dataset.citationId));
      });

      sourceCards().forEach((card) => bindSourceCard(card));

      function bindSourceCard(card) {
        if (card.dataset.cwCitationBound === '1') return;
        const citationId = card.dataset.citationId;
        card.dataset.cwCitationBound = '1';
        const setActive = (active) => {
          root.querySelectorAll(`.cw-inline-citation[data-citation-id="${citationId}"], .cw-chip[data-citation-id="${citationId}"]`)
            .forEach((item) => item.classList.toggle('is-highlighted', active));
          card.classList.toggle('is-highlighted', active);
        };
        card.addEventListener('mouseenter', () => setActive(true));
        card.addEventListener('mouseleave', () => setActive(false));
      }
    };
  }

  const install = () => {
    const root = document.querySelector('.st-key-cw_chat_column');
    if (!root) return;
    if (!window.__cwCitationObserver) {
      window.__cwCitationObserver = new MutationObserver(() => {
        window.requestAnimationFrame(() => {
          if (window.__cwCitationRoot) window.__cwDecorateCitations(window.__cwCitationRoot);
        });
      });
    }
    if (window.__cwCitationRoot !== root) {
      window.__cwCitationObserver.disconnect();
      window.__cwCitationObserver.observe(root, {childList: true, subtree: true});
      window.__cwCitationRoot = root;
    }
    window.__cwDecorateCitations(root);
  };

  install();
  window.setTimeout(install, 80);
})();
</script>
"""


def _parse_json(content):
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return None


def _display(value):
    if value in (None, "", [], {}):
        return "未提取到"
    if isinstance(value, list):
        return "、".join(map(str, value))
    return str(value)


def _render_compare(data):
    labels = {
        "title": "标题",
        "year": "年份",
        "authors": "作者",
        "method": "方法",
        "datasets": "数据集",
        "results": "实验结果",
        "abstract": "摘要",
    }
    rows = [
        {
            "对比维度": label,
            "论文 A": _display(data["paper_a"].get(field)),
            "论文 B": _display(data["paper_b"].get(field)),
        }
        for field, label in labels.items()
    ]
    st.table(rows)


def _render_summary(data):
    for field, title in _SUMMARY_FIELDS:
        st.markdown(f"### {title}")
        render_markdown(str(data.get(field) or "未提取到"), citations=[], streaming=False, key=f"summary-{field}")


def _usage_label(usage):
    """Turn provider usage into a compact UI label instead of dumping JSON."""

    if not isinstance(usage, dict):
        return "Token 未提供"
    total = usage.get("total_tokens")
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    calls = usage.get("model_calls")
    if isinstance(total, (int, float)) and not isinstance(total, bool):
        label = f"Token {int(total):,}"
    elif isinstance(prompt, (int, float)) and isinstance(completion, (int, float)):
        label = f"Token {int(prompt + completion):,}"
    else:
        label = "Token 未提供"
    if isinstance(calls, (int, float)) and not isinstance(calls, bool) and calls > 1:
        label += f" · {int(calls)} 次模型调用"
    return label


def _render_meta(message):
    citations = message.get("citations") or []
    latency = message.get("latency_ms")
    usage = message.get("token_usage")
    parts = [f"引用 {len(citations)}"]
    if latency is not None:
        parts.append(f"{float(latency) / 1000:.2f} 秒")
    else:
        parts.append("耗时 未提供")
    parts.append(_usage_label(usage))
    st.html('<div class="cw-answer-meta">' + "".join(f"<span>{html.escape(part)}</span>" for part in parts) + "</div>")
    if citations:
        chips = []
        for citation in citations:
            number = citation.get("citation_id", "?")
            name = citation.get("file_name", "来源")
            citation_id = html.escape(str(number), quote=True)
            chips.append(
                f'<span class="cw-chip" data-citation-id="{citation_id}">'
                f'[{html.escape(str(number))}] {html.escape(str(name))}</span>'
            )
        st.html('<div class="cw-citation-strip">' + "".join(chips) + "</div>")
        st.html(_CITATION_INTERACTION_SCRIPT, unsafe_allow_javascript=True)


def render_copy_control(content):
    """Render a compact, browser-side copy control for the final answer."""

    # Base64 keeps model output out of the HTML/JavaScript syntax. The iframe
    # still performs the actual clipboard write in the browser on click.
    value = base64.b64encode(str(content).encode("utf-8")).decode("ascii")
    st.iframe(
        f"""
        <style>
          html,body {{ margin:0; padding:0; background:transparent; overflow:hidden; }}
          body {{ display:flex; align-items:center; height:36px; font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC",sans-serif; }}
          button {{ width:100%; height:36px; display:flex; align-items:center; justify-content:flex-start; padding:0; border:0; border-radius:5px; background:transparent; color:#6b7280; cursor:pointer; }}
          button:hover {{ background:#f1f3f5; color:#202124; }}
          button:focus-visible {{ outline:2px solid #9db8e8; outline-offset:1px; }}
          svg {{ width:20px; height:20px; }}
        </style>
        <button id="copy-answer" type="button" title="复制回答" aria-label="复制回答">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1Zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2Zm0 16H8V7h11v14Z"/></svg>
        </button>
        <script>
          const encodedAnswer = "{value}";
          const binaryAnswer = atob(encodedAnswer);
          const answerText = new TextDecoder("utf-8").decode(
            Uint8Array.from(binaryAnswer, character => character.charCodeAt(0))
          );
          const button = document.getElementById("copy-answer");
          const copyIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';
          const originalIcon = button.innerHTML;
          const fallbackCopy = () => {{
            const area = document.createElement("textarea");
            area.value = answerText;
            area.style.position = "fixed";
            area.style.opacity = "0";
            document.body.appendChild(area);
            area.focus();
            area.select();
            const copied = document.execCommand("copy");
            area.remove();
            return copied;
          }};
          button.addEventListener("click", async () => {{
            let copied = false;
            try {{
              if (navigator.clipboard?.writeText) {{
                await navigator.clipboard.writeText(answerText);
                copied = true;
              }}
            }} catch (error) {{
              copied = false;
            }}
            if (!copied) copied = fallbackCopy();
            if (copied) {{
              button.innerHTML = copyIcon;
              button.title = "已复制";
              button.setAttribute("aria-label", "已复制");
              window.setTimeout(() => {{
                button.innerHTML = originalIcon;
                button.title = "复制回答";
                button.setAttribute("aria-label", "复制回答");
              }}, 1400);
            }}
          }});
        </script>
        """,
        width="stretch",
        height=36,
    )


def render_answer(message):
    content = message.get("content") or ""
    streaming = message.get("status") in ("queued", "running")
    if message.get("role") == "user":
        safe_content = html.escape(str(content)).replace("\n", "<br>")
        st.html(f'<div class="cw-user-message">{safe_content}</div>')
        return

    if message.get("role") == "assistant":
        st.html('<div class="cw-answer-label"><strong>DeepSeek</strong></div>')

    if not content and streaming:
        st.html(
            '<div class="cw-answer-pending">'
            '<span class="cw-pending-spinner" aria-hidden="true"></span>'
            '<span>正在生成回答</span>'
            "</div>"
        )
    else:
        data = _parse_json(content)
        if isinstance(data, dict) and isinstance(data.get("paper_a"), dict) and isinstance(data.get("paper_b"), dict):
            _render_compare(data)
        elif isinstance(data, dict) and any(field in data for field, _ in _SUMMARY_FIELDS):
            _render_summary(data)
        else:
            render_markdown(
                content,
                citations=message.get("citations") or [],
                streaming=streaming,
                key=f"answer-{message.get('message_id', 'current')}",
            )
        if streaming:
            st.html(
                '<div class="cw-answer-pending">'
                '<span class="cw-pending-spinner" aria-hidden="true"></span>'
                '<span>正在生成回答</span>'
                "</div>"
            )

    if message.get("role") == "assistant" and not streaming:
        _render_meta(message)

import streamlit as st


def apply_theme():
    st.html(
        '''<style>
        :root {
          --cw-sidebar-width:250px;
          --cw-ink:#202124;
          --cw-muted:#6b7280;
          --cw-faint:#9aa0a6;
          --cw-line:#e2e5e9;
          --cw-soft-line:#eef0f2;
          --cw-blue:#2563eb;
          --cw-blue-hover:#1d4ed8;
          --cw-sidebar:#f7f8fa;
          --cw-paper:#ffffff;
          --cw-soft:#f8fafc;
          --cw-code:#f5f7fa;
          --cw-success:#18864b;
          --cw-warning:#9a6700;
          --cw-danger:#c9362b;
          --cw-font:-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Helvetica Neue",Arial,sans-serif;
          --cw-mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
        }
        html,body,[data-testid="stApp"] {font-family:var(--cw-font);color:var(--cw-ink);background:var(--cw-paper);}
        [data-testid="stAppViewContainer"] {background:var(--cw-paper);}
        [data-testid="stHeader"] {background:transparent;height:2.1rem;}
        [data-testid="stToolbar"] {display:flex!important;}
        [data-testid="stAppDeployButton"],[data-testid="stMainMenu"],[data-testid="stStatusWidget"] {display:none!important;}
        .block-container {max-width:1420px;min-height:calc(100vh - 3rem);padding:1.35rem 2.5rem 4.5rem;}
        /* Keep the sticky chat composer from making the empty state open at the bottom. */
        [data-testid="stMainBlockContainer"] {min-height:calc(100vh - 13rem)!important;}
        h1,h2,h3,h4 {font-family:var(--cw-font);color:var(--cw-ink);letter-spacing:-.02em;}
        h1 {font-size:1.72rem!important;font-weight:700!important;margin:0!important;}
        h2 {font-size:1.16rem!important;font-weight:680!important;}
        h3 {font-size:1rem!important;font-weight:650!important;}
        h4 {font-size:.9rem!important;font-weight:650!important;}
        [data-testid="stCaptionContainer"],small {color:var(--cw-muted)!important;}
        [data-testid="stMarkdownContainer"] {line-height:1.62;}
        [data-testid="stMarkdownContainer"] h1,[data-testid="stMarkdownContainer"] h2,[data-testid="stMarkdownContainer"] h3 {margin-top:1.25em;}
        [data-testid="stMarkdownContainer"] p {margin:.6rem 0;}
        [data-testid="stMarkdownContainer"] ul,[data-testid="stMarkdownContainer"] ol {padding-left:1.45rem;}
        [data-testid="stMarkdownContainer"] blockquote {margin:1rem 0;padding:.1rem .9rem;border-left:3px solid #c8d0da;color:#4b5563;background:#fafbfc;}
        [data-testid="stMarkdownContainer"] code {font-family:var(--cw-mono);font-size:.86em;background:var(--cw-code);border:1px solid #e6e9ed;border-radius:4px;padding:.1em .34em;}
        [data-testid="stMarkdownContainer"] pre {margin:1rem 0;padding:0;background:var(--cw-code);border:1px solid #e3e7eb;border-radius:7px;overflow:auto;}
        [data-testid="stMarkdownContainer"] pre code {display:block;padding:1rem;border:0;background:transparent;line-height:1.55;}
        [data-testid="stMarkdownContainer"] table {display:block;max-width:100%;overflow:auto;border-collapse:collapse;font-size:.9rem;}
        [data-testid="stMarkdownContainer"] th,[data-testid="stMarkdownContainer"] td {white-space:nowrap;border:1px solid #e1e5e9;padding:.5rem .7rem;}
        [data-testid="stMarkdownContainer"] th {background:#f7f8fa;font-weight:650;}
        [data-testid="stMarkdownContainer"] a {color:var(--cw-blue);text-decoration:none;}
        [data-testid="stMarkdownContainer"] a:hover {text-decoration:underline;}

        [data-testid="stSidebar"] {background:var(--cw-sidebar);border-right:1px solid var(--cw-line);width:250px!important;min-width:250px!important;max-width:250px!important;}
        [data-testid="stSidebar"] [data-testid="stSidebarHeader"] {height:0!important;min-height:0!important;margin:0!important;position:absolute;top:0;right:0;z-index:3;}
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {display:none!important;}
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding:.9rem .8rem .9rem;min-height:100vh;}
        [data-testid="stSidebar"] .block-container {min-height:0;padding:.9rem .8rem 1rem;max-width:none;}
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.25rem;}
        [data-testid="stSidebar"] hr {margin:.72rem .3rem;border-color:var(--cw-line);}
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {border:0;box-shadow:none;justify-content:flex-start;text-align:left;min-height:2.05rem;border-radius:6px;}
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {background:transparent;color:#353942;}
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {background:#eceff3;}
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {background:#e7efff;color:#1549a3;}
        [data-testid="stSidebarCollapseButton"] button {border-radius:6px;color:var(--cw-muted);}
        [data-testid="stExpandSidebarButton"] {position:fixed!important;top:12px!important;left:12px!important;z-index:999999!important;width:32px!important;height:32px!important;border:1px solid var(--cw-line)!important;border-radius:6px!important;background:var(--cw-sidebar)!important;color:#3a3f47!important;box-shadow:none!important;}
        .cw-brand {display:flex;align-items:center;gap:10px;padding:.2rem .35rem 1rem;border-bottom:1px solid var(--cw-line);}
        .cw-brand:before {content:"";width:13px;height:13px;border:2.5px solid var(--cw-blue);transform:rotate(45deg);margin:0 2px 0 3px;flex:0 0 auto;}
        .cw-brand strong {font-size:17px;font-weight:700;letter-spacing:-.025em;}
        .cw-brand small {font-size:11px;color:var(--cw-muted);}
        .cw-sidebar-label {font-size:.7rem;color:var(--cw-faint);text-transform:uppercase;letter-spacing:.08em;margin:.8rem .35rem .25rem;}
        .cw-sidebar-status {font-size:.75rem;color:var(--cw-muted);padding:.7rem .35rem 0;border-top:1px solid var(--cw-line);margin-top:1rem;}

        [data-testid="stButton"] button {border-radius:6px;box-shadow:none;transition:background-color .12s,border-color .12s,color .12s;}
        [data-testid="stButton"] button:active {transform:translateY(1px);}
        [data-testid="stBaseButton-primary"] {background:var(--cw-blue);border-color:var(--cw-blue);}
        [data-testid="stBaseButton-primary"]:hover {background:var(--cw-blue-hover);border-color:var(--cw-blue-hover);}
        [data-testid="stButton"] button:focus-visible,[data-testid="stTextInput"] input:focus-visible,[data-testid="stChatInput"]:focus-within {outline:3px solid rgba(37,99,235,.2);outline-offset:1px;}
        /* Streamlit already draws the expander panel border; adding one to
           the wrapper creates the doubled outline seen in source details. */
        [data-testid="stExpander"] {border:0!important;border-radius:0;box-shadow:none;}
        [data-testid="stExpander"] > details {border:1px solid var(--cw-line);border-radius:6px;overflow:hidden;}
        [data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--cw-line);border-radius:7px;box-shadow:none;}
        [data-testid="stAlert"] {border-radius:6px;}
        [data-testid="stMetric"] {background:#fff;border:1px solid var(--cw-line);border-radius:6px;padding:.75rem .8rem;}

        .cw-page-header {display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;border-bottom:1px solid var(--cw-line);padding-bottom:1rem;margin-bottom:1.2rem;}
        .cw-page-kicker {font-size:.7rem;line-height:1.2;color:var(--cw-muted);letter-spacing:.09em;text-transform:uppercase;margin-bottom:.35rem;}
        .cw-page-subtitle {font-size:.85rem;color:var(--cw-muted);margin-top:.35rem;}
        .cw-rule {height:1px;background:var(--cw-line);margin:1rem 0 1.2rem;}
        .cw-section-label {font-size:.72rem;color:var(--cw-muted);text-transform:uppercase;letter-spacing:.08em;margin:1rem 0 .35rem;}
        .cw-empty-state {max-width:650px;margin:1.35rem 0 0;text-align:left;}
        .cw-empty-kicker {font-size:.68rem;color:var(--cw-muted);letter-spacing:.13em;text-transform:uppercase;margin-bottom:.55rem;}
        .cw-empty-state h2 {font-size:1.9rem!important;margin:.5rem 0!important;letter-spacing:-.045em;}
        .cw-empty-state p {color:var(--cw-muted);font-size:.9rem;margin:.4rem 0 1.2rem;}
        .cw-action-row {display:flex;justify-content:flex-start;gap:.55rem;}
        .cw-answer-label {display:flex;align-items:center;gap:.45rem;font-size:.74rem;color:var(--cw-muted);letter-spacing:.04em;text-transform:uppercase;margin-bottom:.6rem;}
        .cw-answer-pending {display:flex;align-items:center;gap:.55rem;color:var(--cw-muted);font-size:.86rem;padding:.35rem 0 .15rem;}
        .cw-pending-spinner {width:11px;height:11px;border:2px solid #d8dee7;border-top-color:var(--cw-blue);border-radius:50%;animation:cw-spin .8s linear infinite;flex:0 0 auto;}
        @keyframes cw-spin {to{transform:rotate(360deg)}}
        @media (prefers-reduced-motion:reduce) {.cw-pending-spinner{animation:none;}}
        .cw-chip {display:inline-flex;align-items:center;border:1px solid #dce2e8;border-radius:999px;padding:.16rem .5rem;color:#4c5865;font-size:.72rem;background:#fafbfc;transition:background .15s,border-color .15s,color .15s,box-shadow .15s;}
        .cw-chip.is-highlighted {border-color:#7aa7f5;background:#e8f0ff;color:#174ea6;box-shadow:0 0 0 2px rgba(37,99,235,.08);}
        .cw-inline-citation {position:relative;display:inline-block;color:#174ea6;background:#eef4ff;border-radius:3px;padding:0 .18em;cursor:help;line-height:1.3;transition:background .15s,color .15s,box-shadow .15s;}
        .cw-inline-citation:hover,.cw-inline-citation:focus,.cw-inline-citation.is-highlighted {background:#dbe9ff;color:#123f8c;box-shadow:0 0 0 2px rgba(37,99,235,.12);outline:none;}
        .cw-inline-citation::after {content:attr(data-source);position:absolute;left:50%;bottom:calc(100% + .45rem);z-index:20;max-width:240px;min-width:max-content;padding:.35rem .5rem;border:1px solid #cbd8ed;border-radius:5px;background:#fff;color:#26364d;box-shadow:0 5px 18px rgba(32,33,36,.14);font-size:.72rem;font-weight:500;line-height:1.35;white-space:nowrap;opacity:0;pointer-events:none;transform:translate(-50%,3px);transition:opacity .12s,transform .12s;}
        .cw-inline-citation:hover::after,.cw-inline-citation:focus::after {opacity:1;transform:translate(-50%,0);}
        .cw-answer-meta {display:flex;flex-wrap:wrap;gap:.7rem;margin-top:.85rem;padding-top:.7rem;border-top:1px solid var(--cw-soft-line);font-size:.74rem;color:var(--cw-muted);}
        .cw-process-box {border:1px solid var(--cw-line);border-radius:7px;background:#fff;max-height:min(360px,42vh);overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;}
        .cw-process-title {padding:.7rem .85rem;border-bottom:1px solid var(--cw-soft-line);font-size:.75rem;color:var(--cw-muted);text-transform:uppercase;letter-spacing:.08em;}
        .cw-process-row {display:grid;grid-template-columns:12px minmax(0,1fr) auto;gap:.65rem;align-items:center;padding:.6rem .85rem;border-bottom:1px solid var(--cw-soft-line);font-size:.82rem;}
        .cw-process-row:last-child {border-bottom:0;}
        .cw-process-marker {width:8px;height:8px;border-radius:50%;background:#a8b0ba;}
        .cw-process-marker.done {background:var(--cw-success);}.cw-process-marker.active {background:var(--cw-blue);}.cw-process-marker.failed {background:var(--cw-danger);}
        .cw-process-detail {color:var(--cw-muted);font-size:.73rem;white-space:nowrap;}
        .cw-citation-strip {display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.8rem;}
        .cw-composer-space {height:clamp(70px,16vh,180px);}
        [data-testid="stChatMessage"] {background:transparent;border-bottom:1px solid var(--cw-soft-line);border-radius:0;padding:0 0 .9rem;}
        [data-testid="stChatMessageAvatarUser"] {background:#eef0f2;color:#555b65;}
        [data-testid="stChatMessageAvatarAssistant"] {background:#e7efff;color:#1549a3;}
        /* Keep the avatar and the compact user message on the same center line. */
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {display:flex!important;align-items:center!important;min-height:32px!important;padding:0 0 .8rem!important;}
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageAvatarUser"] {align-self:center!important;transform:none!important;margin:0!important;}
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {display:flex!important;align-items:center!important;align-self:center!important;height:auto!important;min-height:32px!important;margin:0!important;padding:0!important;}
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] > div {display:flex!important;align-items:center!important;height:auto!important;min-height:32px!important;margin:0!important;padding:0!important;}
        .cw-user-message {display:flex!important;align-items:center!important;height:auto!important;min-height:32px!important;margin:0!important;padding:0!important;line-height:1.25!important;white-space:pre-wrap;}
        [data-testid="stChatMessage"] .cw-answer-label {position:relative;top:.65rem;}
        [data-testid="stChatInput"] {min-height:72px;background:#fff;border:1px solid #cbd2da;border-radius:8px;box-shadow:none;padding:8px 10px 7px 13px;}
        [data-testid="stChatInput"] > div {width:100%!important;}
        [data-testid="stChatInput"] textarea {background:transparent!important;min-height:44px!important;padding:6px 2px!important;line-height:1.45!important;box-shadow:none!important;outline:none!important;}
        [data-testid="stChatInput"] button {width:32px!important;height:32px!important;border-radius:6px!important;margin-bottom:2px!important;background:#202124!important;color:#fff!important;}
        [data-testid="stChatInput"] button:disabled {background:#e5e7eb!important;color:#a1a7af!important;}
        [data-testid="stBottomBlockContainer"] {padding-bottom:2rem!important;}

        .cw-inspector-header {border-bottom:1px solid var(--cw-line);padding-bottom:.8rem;margin-bottom:.8rem;}
        .cw-inspector-header strong {font-size:.95rem;}
        .st-key-cw_inspector_panel {height:calc(100vh - 10rem)!important;max-height:calc(100vh - 10rem)!important;flex:0 0 calc(100vh - 10rem)!important;overflow-y:auto!important;overflow-x:hidden!important;padding:0 .25rem .5rem 0;scrollbar-width:thin;scrollbar-color:#c4cad3 transparent;}
        .st-key-cw_inspector_panel::-webkit-scrollbar {width:8px;}.st-key-cw_inspector_panel::-webkit-scrollbar-thumb {background:#c4cad3;border-radius:8px;}.st-key-cw_inspector_panel::-webkit-scrollbar-track {background:transparent;}
        .cw-source-card {border:1px solid var(--cw-line);border-radius:6px;padding:.7rem .75rem;margin:.5rem 0;background:#fff;transition:background .15s,border-color .15s,box-shadow .15s;}
        .cw-source-card.is-highlighted {border-color:#7aa7f5;background:#f5f8ff;box-shadow:0 0 0 2px rgba(37,99,235,.08);}
        .cw-source-card strong {font-size:.83rem;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
        .cw-source-card small {display:block;margin-top:.28rem;line-height:1.4;}
        .cw-source-preview {font-size:.78rem;line-height:1.55;color:#4b5563;margin:.55rem 0 .35rem;display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden;}
        .cw-trajectory {border-left:1px solid #d9dee5;margin:.35rem 0 0 .35rem;padding-left:.8rem;}
        .cw-trajectory-step {position:relative;padding:0 0 .75rem;font-size:.8rem;}
        .cw-trajectory-step:before {content:"";position:absolute;left:-1.12rem;top:.25rem;width:7px;height:7px;border-radius:50%;background:#a8b0ba;}
        .cw-trajectory-step.done:before {background:var(--cw-success);}.cw-trajectory-step.active:before {background:var(--cw-blue);}.cw-trajectory-step.failed:before {background:var(--cw-danger);}
        .cw-trajectory-step small {display:block;margin-top:.2rem;}
        .cw-metric-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem;}
        .cw-metric {border:1px solid var(--cw-line);border-radius:6px;padding:.65rem .7rem;}
        .cw-metric small {display:block;font-size:.7rem;}.cw-metric strong {display:block;margin-top:.2rem;font-size:.95rem;font-weight:650;}

        [data-testid="stFileUploaderDropzone"] {background:var(--cw-soft);border:1px dashed #b8c0ca;border-radius:7px;min-height:120px;}
        [data-testid="stFileUploaderDropzone"] button {background:#fff;border-color:#b8c0ca;color:var(--cw-ink);}
        .cw-document-header,.cw-document-row {display:grid;grid-template-columns:minmax(0,2.5fr) .8fr .7fr .8fr 1fr;gap:.75rem;align-items:center;}
        .cw-document-header {font-size:.7rem;color:var(--cw-muted);text-transform:uppercase;letter-spacing:.05em;padding:.45rem .75rem;border-bottom:1px solid var(--cw-line);}
        .cw-document-row {padding:.75rem;border-bottom:1px solid var(--cw-soft-line);font-size:.82rem;}
        .cw-document-name {min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
        .cw-document-name strong {font-weight:620;}.cw-document-name small {display:block;margin-top:.18rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
        .cw-ready {color:var(--cw-success);}.cw-pending,.cw-warning {color:var(--cw-warning);}.cw-failed {color:var(--cw-danger);}
        .cw-job {border:1px solid var(--cw-line);border-radius:6px;padding:.65rem .75rem;margin:.45rem 0;background:#fff;}
        .cw-status-card {border:1px solid var(--cw-line);border-radius:7px;padding:.8rem .9rem;margin-bottom:.75rem;background:#fff;}
        .cw-status-row {display:flex;justify-content:space-between;gap:1rem;padding:.48rem 0;border-bottom:1px solid var(--cw-soft-line);font-size:.82rem;}
        .cw-status-row:last-child {border-bottom:0;}.cw-status-ok{color:var(--cw-success);}.cw-status-pending{color:var(--cw-warning);}.cw-status-error{color:var(--cw-danger);}

        /* Shared layout for the library, analysis and status workspaces. */
        .st-key-cw_library_header,.st-key-cw_analysis_header,.st-key-cw_status_header {max-width:1120px!important;margin:0 auto .35rem!important;padding:0 0 .72rem!important;border-bottom:1px solid var(--cw-line);}
        .cw-page-topbar {display:flex;align-items:baseline;gap:.7rem;min-height:2.55rem;}
        .cw-page-topbar h1 {font-size:1.55rem!important;line-height:1.1!important;letter-spacing:-.045em!important;margin:0!important;}
        .cw-page-meta {color:var(--cw-muted);font-size:.78rem;line-height:1;border-left:1px solid var(--cw-line);padding-left:.7rem;}
        .st-key-cw_library_body,.st-key-cw_analysis_body,.st-key-cw_status_body {max-width:1120px!important;margin:0 auto!important;padding-top:.8rem!important;}
        .st-key-cw_library_body [data-testid="stHorizontalBlock"],.st-key-cw_status_body [data-testid="stHorizontalBlock"] {gap:1.25rem!important;}
        .st-key-cw_library_body h2,.st-key-cw_analysis_body h2,.st-key-cw_status_body h2 {margin:.1rem 0 .65rem!important;font-size:1rem!important;letter-spacing:-.015em!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stHorizontalBlock"] {align-items:center!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFileUploaderDropzone"] {min-height:94px;display:flex!important;align-items:center!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFileUploaderDropzone"]>div {display:flex!important;align-items:center!important;min-height:100%!important;width:100%!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFileUploaderDropzoneInstructions"] {display:flex!important;align-items:center!important;align-self:center!important;min-height:100%!important;margin:0!important;padding:.55rem .75rem!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFileUploaderDropzone"] button {align-self:center!important;margin:0!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFormSubmitButton"] {display:flex!important;align-items:center!important;height:100%!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {width:100%!important;min-height:46px!important;}
        /* Keep both actions on the same visual center line inside the shared
           upload panel. */
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stHorizontalBlock"] {background:var(--cw-soft)!important;border:1px dashed #b8c0ca!important;border-radius:7px!important;overflow:hidden!important;padding:.45rem .55rem!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFileUploaderDropzone"] {background:transparent!important;border:0!important;border-radius:0!important;}
        .st-key-cw_library_body [data-testid="stFileUploaderDropzone"] button {width:6.25rem!important;height:3.5rem!important;min-height:3.5rem!important;}
        .st-key-cw_library_body [data-testid="stFormSubmitButton"] {position:static!important;transform:none!important;}
        .st-key-cw_library_body [data-testid="stFormSubmitButton"] button {width:6.25rem!important;height:3.5rem!important;min-height:3.5rem!important;}
        .st-key-cw_library_body [data-testid="stFileUploaderDropzoneInstructions"]>div {font-size:.8rem!important;}
        .st-key-cw_library_body [data-testid="stForm"] [data-testid="stFileUploaderDropzone"] button {padding:.45rem .7rem!important;}
        .cw-limit-list {border-top:1px solid var(--cw-line);margin-top:.15rem;}
        .cw-limit-list>div {display:flex;justify-content:space-between;align-items:baseline;gap:.75rem;padding:.62rem 0;border-bottom:1px solid var(--cw-soft-line);font-size:.8rem;}
        .cw-limit-list span {color:var(--cw-muted);}.cw-limit-list strong {font-weight:550;text-align:right;}
        .cw-content-rule {height:1px;background:var(--cw-line);margin:1.35rem 0 .9rem;}
        .cw-list-heading {display:flex;align-items:baseline;gap:.65rem;margin:.85rem 0 .5rem;}
        .cw-list-heading strong {font-size:.95rem;font-weight:680;}.cw-list-heading span {font-size:.74rem;color:var(--cw-muted);}
        .cw-documents-heading {margin-top:1.15rem;}
        .cw-job-summary {display:flex;align-items:baseline;gap:.45rem;margin:.45rem 0 .35rem;font-size:.8rem;}
        .cw-job-summary strong {font-weight:620;}.cw-job-summary span {color:var(--cw-muted);}
        .cw-inline-error {color:var(--cw-danger);background:#fff7f6;border:1px solid #f1d3d0;border-radius:5px;padding:.5rem .65rem;margin:.35rem 0;font-size:.76rem;line-height:1.45;}
        .st-key-cw_documents_list {border-top:1px solid var(--cw-line);border-bottom:1px solid var(--cw-line);}
        .st-key-cw_documents_list [data-testid="stVerticalBlock"] {gap:0!important;}
        .st-key-cw_documents_list [data-testid="stVerticalBlock"] [data-testid="stHorizontalBlock"] {padding:.15rem .75rem;border-bottom:1px solid var(--cw-soft-line);}
        .st-key-cw_documents_list [data-testid="stVerticalBlock"] [data-testid="stHorizontalBlock"]:last-child {border-bottom:0;}
        .st-key-cw_documents_list [data-testid="stCaptionContainer"] {font-size:.78rem;}
        .st-key-cw_analysis_body [data-testid="stRadio"] {margin:0 0 .95rem;}
        .st-key-cw_analysis_body [data-testid="stRadio"]>label {display:none;}
        .st-key-cw_analysis_body [role="radiogroup"] {display:inline-flex;gap:.15rem;border:1px solid var(--cw-line);border-radius:7px;padding:3px;background:#f7f8fa;}
        .st-key-cw_analysis_body [role="radiogroup"] label {margin:0!important;padding:.42rem .72rem!important;border-radius:4px!important;color:var(--cw-muted);font-size:.82rem;}
        .st-key-cw_analysis_body [role="radiogroup"] label:has(input:checked) {background:#fff;color:var(--cw-ink);box-shadow:0 1px 2px rgba(32,33,36,.08);}
        .st-key-cw_analysis_body [data-testid="stSelectbox"] label {font-size:.76rem;color:var(--cw-muted);margin-bottom:.25rem;}
        .st-key-cw_analysis_result {border-top:1px solid var(--cw-line);margin-top:1.55rem;padding-top:1rem;}
        .cw-result-heading {font-size:.95rem;margin-bottom:.7rem;}
        .st-key-cw_analysis_result h3 {font-size:1rem!important;margin-top:1.15rem!important;}
        .st-key-cw_status_body {padding-top:.95rem!important;}
        .st-key-cw_status_body> [data-testid="stHorizontalBlock"]:first-child {margin-bottom:1.15rem;}
        .st-key-cw_status_body .cw-status-card {margin-bottom:0;}
        .st-key-cw_status_body [data-testid="stMetric"] {min-height:92px;padding:.7rem .75rem;}
        .st-key-cw_status_body [data-testid="stMetricLabel"] {font-size:.75rem;}
        .st-key-cw_status_body [data-testid="stMetricValue"] {font-size:1.35rem;line-height:1.15;white-space:normal;overflow-wrap:anywhere;}

        .cw-setup-kicker {color:var(--cw-muted);font-size:.72rem;letter-spacing:.12em;margin-top:5vh;}
        .cw-setup-title {font-size:clamp(2.5rem,5vw,5rem);letter-spacing:-.06em;font-weight:700;line-height:.95;margin:1rem 0 .9rem;max-width:760px;}
        .cw-setup-copy {color:var(--cw-muted);font-size:.98rem;line-height:1.55;max-width:580px;margin-bottom:3rem;}
        .cw-setup-notes {border-top:1px solid var(--cw-line);}
        .cw-setup-notes>div {display:grid;grid-template-columns:38px 150px 1fr;align-items:baseline;padding:1rem 0;border-bottom:1px solid var(--cw-line);}
        .cw-setup-notes span {color:var(--cw-faint);font-variant-numeric:tabular-nums;font-size:.78rem;}.cw-setup-notes strong {font-size:.9rem;font-weight:620;}.cw-setup-notes small {font-size:.82rem;line-height:1.4;}
        [data-testid="stForm"] {border:0;padding:0;}

        @media (max-width:1100px) {
          :root {--cw-sidebar-width:228px;}
          [data-testid="stSidebar"] {width:228px!important;min-width:228px!important;max-width:228px!important;}
          .block-container {padding-left:1.8rem;padding-right:1.8rem;}
        }
        @media (max-width:800px) {
          .block-container{padding:2.4rem 1rem 4rem;}.cw-setup-copy{margin-bottom:2rem;}
          .cw-setup-notes>div{grid-template-columns:32px 1fr;}.cw-setup-notes small{grid-column:2;margin-top:4px;}
          .cw-document-header {display:none;}.cw-document-row {grid-template-columns:minmax(0,1fr) auto;gap:.35rem;}.cw-document-row>*:not(:first-child):not(:last-child){font-size:.75rem;}
          .st-key-cw_library_header,.st-key-cw_analysis_header,.st-key-cw_status_header {margin-left:0!important;margin-right:0!important;}
          .st-key-cw_library_body,.st-key-cw_analysis_body,.st-key-cw_status_body {padding-top:.35rem!important;}
          .cw-limit-list>div {justify-content:flex-start;gap:.75rem;}.cw-limit-list strong {text-align:left;}
          .st-key-cw_library_body [data-testid="stFileUploaderDropzone"] button,.st-key-cw_library_body [data-testid="stFormSubmitButton"] {top:0!important;transform:none!important;}
          .st-key-cw_analysis_body [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
        }

        /* Workspace v2: one compact header, one readable start panel, one composer width. */
        .st-key-cw_start_panel {width:100%!important;max-width:900px!important;margin:1.85rem auto 0!important;padding:0!important;}
        .st-key-cw_start_panel .cw-empty-state {max-width:none;margin:0 0 1.2rem;text-align:left;}
        .st-key-cw_start_panel .cw-empty-state h2 {font-size:2.15rem!important;line-height:1.1!important;margin:0!important;letter-spacing:-.055em;}
        .st-key-cw_start_panel [data-testid="stRadio"] {margin:0 0 1.15rem;}
        .st-key-cw_start_panel [data-testid="stRadio"] > label {display:none;}
        .st-key-cw_start_panel [role="radiogroup"] {display:inline-flex;gap:.15rem;border:1px solid var(--cw-line);border-radius:7px;padding:3px;background:#f7f8fa;}
        .st-key-cw_start_panel [role="radiogroup"] label {margin:0!important;padding:.42rem .72rem!important;border-radius:4px!important;color:var(--cw-muted);font-size:.82rem;}
        .st-key-cw_start_panel [role="radiogroup"] label:has(input:checked) {background:#fff;color:var(--cw-ink);box-shadow:0 1px 2px rgba(32,33,36,.08);}
        .st-key-cw_start_panel [data-testid="stHorizontalBlock"] {gap:.65rem!important;}
        .st-key-cw_start_panel [data-testid="stButton"] button {height:48px!important;justify-content:center;border-color:#cfd5dc;background:#fff;color:var(--cw-ink);font-size:.84rem;}
        .st-key-cw_start_panel [data-testid="stButton"] button:hover {border-color:#9db8e8;background:#f7faff;color:#174ea6;}
        [data-testid="stBottom"] [data-testid="stChatInput"] {width:min(900px,calc(100% - 2rem))!important;margin-left:auto!important;margin-right:auto!important;}
        .st-key-cw_body {width:100%!important;min-height:calc(100vh - 18rem)!important;display:flex!important;flex-direction:column!important;}
        .st-key-cw_body:has([data-testid="stChatMessage"]) {min-height:0!important;display:block!important;}
        .st-key-cw_body:has(.st-key-cw_chat_column [data-testid="stChatMessage"]) {height:calc(100vh - 10rem)!important;max-height:calc(100vh - 10rem)!important;min-height:0!important;overflow:hidden!important;}
        .st-key-cw_body:has(.st-key-cw_chat_column [data-testid="stChatMessage"]) > [data-testid="stVerticalBlock"] {height:100%!important;max-height:100%!important;min-height:0!important;overflow:hidden!important;}
        .st-key-cw_body:has(.st-key-cw_inspector_panel) [data-testid="stHorizontalBlock"]:has(.st-key-cw_inspector_panel) {height:calc(100vh - 10rem)!important;max-height:calc(100vh - 10rem)!important;min-height:0!important;overflow:hidden!important;align-items:stretch!important;}
        .st-key-cw_body:has(.st-key-cw_inspector_panel) [data-testid="stHorizontalBlock"]:has(.st-key-cw_inspector_panel) > [data-testid="stColumn"] {height:calc(100vh - 10rem)!important;max-height:calc(100vh - 10rem)!important;min-height:0!important;overflow:hidden!important;align-self:stretch!important;}
        .st-key-cw_chat_column {height:calc(100vh - 10rem)!important;max-height:calc(100vh - 10rem)!important;flex:0 0 calc(100vh - 10rem)!important;overflow-y:auto!important;overflow-x:hidden!important;padding-right:1rem;scrollbar-width:thin;scrollbar-color:#c4cad3 transparent;}
        .st-key-cw_chat_column::-webkit-scrollbar {width:8px;}.st-key-cw_chat_column::-webkit-scrollbar-thumb {background:#c4cad3;border-radius:8px;}.st-key-cw_chat_column::-webkit-scrollbar-track {background:transparent;}
        .st-key-cw_body:not(:has(.st-key-cw_inspector_panel)) .st-key-cw_chat_column {height:calc(100vh - 10rem - 70px)!important;max-height:calc(100vh - 10rem - 70px)!important;flex-basis:calc(100vh - 10rem - 70px)!important;padding-bottom:9rem!important;}
        .st-key-cw_body:has(.st-key-cw_chat_column [data-testid="stChatMessage"]):not(:has(.st-key-cw_inspector_panel)) .st-key-cw_chat_column {height:calc(100vh - 10rem)!important;max-height:calc(100vh - 10rem)!important;flex-basis:calc(100vh - 10rem)!important;padding-bottom:2rem!important;}
        .stMain:has(.st-key-cw_chat_column [data-testid="stChatMessage"]) {overflow:hidden!important;}
        .st-key-cw_quick_actions {position:fixed!important;left:calc(var(--cw-sidebar-width) + (100vw - var(--cw-sidebar-width))/2)!important;bottom:8.5rem!important;transform:translateX(-50%)!important;width:min(900px,calc(100vw - var(--cw-sidebar-width) - 2rem))!important;max-width:none!important;margin:0!important;padding:.25rem 0;background:var(--cw-paper);z-index:5;}
        .st-key-cw_quick_actions [data-testid="stHorizontalBlock"] {gap:.65rem!important;}
        .st-key-cw_quick_actions [data-testid="stButton"] button {height:46px!important;justify-content:center;border-color:#cfd5dc;background:#fff;color:var(--cw-ink);font-size:.84rem;}
        .st-key-cw_quick_actions [data-testid="stButton"] button:hover {border-color:#9db8e8;background:#f7faff;color:#174ea6;}
        [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"] {max-width:420px!important;gap:.55rem!important;margin-top:.65rem;}
        [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"] [data-testid="stButton"] button {height:36px!important;padding:.25rem .55rem!important;justify-content:center;font-size:.78rem!important;white-space:nowrap;}
        [data-testid="stChatMessage"] {max-width:900px;margin-left:auto!important;margin-right:auto!important;}
        [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {width:100%;min-width:0;}
        [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] li {text-align:justify;text-justify:inter-character;text-align-last:left;}
        [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] pre,
        [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] code,
        [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] table {text-align:left;}
        [data-testid="stChatMessage"] .cw-answer-meta,
        [data-testid="stChatMessage"] .cw-citation-strip {text-align:left;}
        [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"] {width:100%!important;max-width:420px!important;margin-left:0!important;margin-right:auto!important;}
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p,
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p {white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

        @media (max-width:800px) {
          .st-key-cw_start_panel {margin-top:1.6rem!important;}
          .st-key-cw_body:has(.st-key-cw_chat_column [data-testid="stChatMessage"]) {height:auto!important;overflow:visible!important;}
          .st-key-cw_body:has(.st-key-cw_inspector_panel) [data-testid="stHorizontalBlock"]:has(.st-key-cw_inspector_panel) {height:auto!important;overflow:visible!important;}
          .st-key-cw_body:has(.st-key-cw_inspector_panel) [data-testid="stHorizontalBlock"]:has(.st-key-cw_inspector_panel) > [data-testid="stColumn"] {height:auto!important;overflow:visible!important;}
          .st-key-cw_chat_column,.st-key-cw_inspector_panel {height:auto!important;max-height:none!important;overflow:visible!important;}
          .st-key-cw_body:not(:has(.st-key-cw_inspector_panel)) .st-key-cw_chat_column {height:auto!important;max-height:none!important;flex-basis:auto!important;padding-bottom:1rem!important;}
          .st-key-cw_quick_actions {position:static!important;transform:none!important;width:100%!important;margin:1rem 0 .7rem!important;padding:.15rem 0 .35rem;}
          .stMain:has(.st-key-cw_chat_column [data-testid="stChatMessage"]) {overflow:auto!important;}
          .st-key-cw_start_panel [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
          .st-key-cw_start_panel [data-testid="stHorizontalBlock"] > div {min-width:calc(50% - .4rem);}
          .st-key-cw_start_panel [data-testid="stHorizontalBlock"] > div:last-child {min-width:100%;}
        }
        </style>'''
    )

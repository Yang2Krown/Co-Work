import streamlit as st


def apply_theme():
    st.html('''<style>
    :root {
      --cw-ink:#1d1d1f; --cw-muted:#6e6e73; --cw-faint:#8e8e93;
      --cw-line:#d8d8dc; --cw-soft-line:#ececef; --cw-blue:#0071e3;
      --cw-blue-hover:#0077ed; --cw-sidebar:#f2f2f4; --cw-paper:#ffffff;
      --cw-soft:#f7f7f8; --cw-success:#248a3d;
      --cw-font:-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Helvetica Neue",Arial,sans-serif;
    }
    html,body,[data-testid="stApp"] {font-family:var(--cw-font);color:var(--cw-ink);background:var(--cw-paper);}
    [data-testid="stAppViewContainer"] {background:var(--cw-paper);}
    [data-testid="stHeader"] {background:transparent;height:2.25rem;}
    [data-testid="stToolbar"] {display:flex!important;}
    [data-testid="stAppDeployButton"],[data-testid="stMainMenu"],[data-testid="stStatusWidget"] {display:none!important;}
    .block-container {max-width:1180px;padding:3.2rem 3rem 6rem;}
    h1,h2,h3 {font-family:var(--cw-font);color:var(--cw-ink);letter-spacing:-.025em;}
    h1 {font-size:1.8rem!important;font-weight:680!important;margin-bottom:.15rem!important;}
    h2 {font-size:1.16rem!important;font-weight:650!important;}
    h3 {font-size:1rem!important;font-weight:650!important;}
    [data-testid="stCaptionContainer"],small {color:var(--cw-muted)!important;}

    [data-testid="stSidebar"] {background:var(--cw-sidebar);border-right:1px solid #d1d1d6;width:260px!important;min-width:260px!important;max-width:260px!important;}
    [data-testid="stSidebarUserContent"] {padding:1.15rem .85rem 1rem;min-height:100vh;}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.3rem;}
    [data-testid="stSidebar"] hr {margin:.75rem .35rem;border-color:#d6d6da;}
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {background:transparent;border:0;box-shadow:none;color:#343438;justify-content:flex-start;text-align:left;min-height:2.15rem;}
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {background:#e4e4e8;}
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {background:#dce9f8;border:0;box-shadow:none;color:#0759a7;justify-content:flex-start;text-align:left;min-height:2.15rem;}
    [data-testid="stSidebarCollapseButton"] button {border-radius:7px;color:#6e6e73;}
    [data-testid="stExpandSidebarButton"] {position:fixed!important;top:14px!important;left:14px!important;z-index:999999!important;width:34px!important;height:34px!important;border:1px solid #d1d1d6!important;border-radius:8px!important;background:#f2f2f4!important;color:#3a3a3c!important;box-shadow:0 1px 3px rgba(0,0,0,.08)!important;}
    .cw-window {display:flex;align-items:center;height:25px;gap:7px;margin:0 .35rem .05rem;}
    .cw-window i {display:block;width:11px;height:11px;border-radius:50%;background:#ff5f57;border:1px solid rgba(0,0,0,.08);}
    .cw-window i:nth-child(2){background:#febc2e}.cw-window i:nth-child(3){background:#28c840}
    .cw-window strong {margin-left:8px;font-size:14px;letter-spacing:-.01em;}
    .cw-sidebar-spacer {height:clamp(40px,18vh,190px);}

    [data-testid="stButton"] button {border-radius:7px;box-shadow:none;transition:background-color .12s,border-color .12s;}
    [data-testid="stButton"] button:active {transform:translateY(1px);}
    [data-testid="stButton"] button:focus-visible,[data-testid="stTextInput"] input:focus-visible {outline:3px solid rgba(0,113,227,.25);outline-offset:1px;}
    [data-testid="stBaseButton-primary"] {background:var(--cw-blue);border-color:var(--cw-blue);}
    [data-testid="stBaseButton-primary"]:hover {background:var(--cw-blue-hover);border-color:var(--cw-blue-hover);}

    .cw-toolbar {display:flex;align-items:center;gap:9px;color:var(--cw-muted);font-size:.76rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.35rem;}
    .cw-toolbar:before {content:"";width:7px;height:7px;border-radius:50%;background:var(--cw-success);}
    .cw-rule {height:1px;background:var(--cw-line);margin:1rem 0 1.35rem;}
    .cw-section-label {font-size:.76rem;color:var(--cw-muted);text-transform:uppercase;letter-spacing:.08em;margin:1.1rem 0 .35rem;}

    [data-testid="stChatMessage"] {background:transparent;border-bottom:1px solid var(--cw-soft-line);border-radius:0;padding:1.25rem .1rem;}
    [data-testid="stChatMessageAvatarUser"] {background:#e9e9ec;color:#55555a;}
    [data-testid="stChatMessageAvatarAssistant"] {background:#dce9f8;color:#0759a7;}
    .cw-composer-space {height:clamp(110px,28vh,290px);}
    [data-testid="stChatInput"] {min-height:86px;background:#fff;border:1px solid #c7c7cc;border-radius:18px;box-shadow:0 8px 28px rgba(0,0,0,.09);padding:10px 12px 8px 16px;}
    [data-testid="stChatInput"] > div {width:100%!important;}
    [data-testid="stChatInput"]:focus-within {border-color:#8e8e93;box-shadow:0 8px 28px rgba(0,0,0,.11);}
    [data-testid="stChatInput"] textarea {background:transparent!important;min-height:54px!important;padding:7px 2px!important;line-height:1.45!important;box-shadow:none!important;outline:none!important;}
    [data-testid="stChatInput"] textarea:focus {box-shadow:none!important;outline:none!important;}
    [data-testid="stChatInput"] button {width:34px!important;height:34px!important;border-radius:50%!important;margin-bottom:2px!important;background:#1d1d1f!important;color:#fff!important;}
    [data-testid="stChatInput"] button:disabled {background:#e5e5e7!important;color:#a1a1a6!important;}
    [data-testid="stExpander"] {border:1px solid var(--cw-line);border-radius:7px;box-shadow:none;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--cw-line);border-radius:10px;box-shadow:0 1px 2px rgba(0,0,0,.035);}

    [data-testid="stFileUploaderDropzone"] {background:var(--cw-soft);border:1px dashed #b7b7bd;border-radius:8px;min-height:132px;}
    [data-testid="stFileUploaderDropzone"] button {background:#fff;border-color:#b8b8bd;color:var(--cw-ink);}
    .cw-doc-row {border-top:1px solid var(--cw-soft-line);padding:14px 0 5px;}
    .cw-doc-row strong {font-size:.95rem;font-weight:590;}
    .cw-doc-row small {display:block;margin-top:3px;}

    .cw-setup-kicker {color:var(--cw-muted);font-size:.75rem;letter-spacing:.14em;margin-top:5vh;}
    .cw-setup-title {font-size:clamp(2.7rem,6vw,5.6rem);letter-spacing:-.065em;font-weight:700;line-height:.95;margin:1rem 0 .9rem;max-width:760px;}
    .cw-setup-copy {color:var(--cw-muted);font-size:1.03rem;line-height:1.55;max-width:580px;margin-bottom:4.2rem;}
    .cw-setup-notes {border-top:1px solid var(--cw-line);}
    .cw-setup-notes>div {display:grid;grid-template-columns:38px 150px 1fr;align-items:baseline;padding:1rem 0;border-bottom:1px solid var(--cw-line);}
    .cw-setup-notes span {color:var(--cw-faint);font-variant-numeric:tabular-nums;font-size:.78rem;}
    .cw-setup-notes strong {font-size:.94rem;font-weight:620;}
    .cw-setup-notes small {font-size:.86rem;line-height:1.4;}
    [data-testid="stForm"] {border:0;padding:0;}

    @media (max-width:800px) {
      .block-container{padding:2.6rem 1.15rem 5rem}.cw-setup-copy{margin-bottom:2rem}
      .cw-setup-notes>div{grid-template-columns:32px 1fr}.cw-setup-notes small{grid-column:2;margin-top:4px}
    }
    </style>''')

from __future__ import annotations

import base64
import html
import os
import shutil
import socket
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.engine import WarehouseAI, build_inventory_snapshot
from utils.gpu_manager import clear_gpu_memory


TEXT_EXAMPLES = [
    "What info can you provide about the data?",
    "What aisles in the full warehouse have boxes in them?",
    "Give the exact number of boxes in each aisle.",
    "What about aisle 9 10 11 12?",
    "Summarize the warehouse layout for me.",
]

SNAPSHOT = build_inventory_snapshot()


def _in_streamlit_runtime() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def _pick_streamlit_port(preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find a free port in range {preferred_port}-{preferred_port + 24}.")


def launch_streamlit():
    env = os.environ.copy()
    env["RS_RAG_STREAMLIT_LAUNCHED"] = "1"
    env["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    preferred_port = int(env.get("RS_RAG_SERVER_PORT", "18080"))
    chosen_port = _pick_streamlit_port(preferred_port)
    env["RS_RAG_SERVER_PORT"] = str(chosen_port)
    if chosen_port != preferred_port:
        print(f"Port {preferred_port} is busy, starting Streamlit on {chosen_port} instead.")
    streamlit_cmd = shutil.which("streamlit")
    if streamlit_cmd:
        command = [streamlit_cmd, "run", str(Path(__file__).resolve())]
    else:
        # Fall back to the current Python environment when streamlit is not on PATH.
        command = [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())]

    command.extend(
        [
            "--server.port",
            str(chosen_port),
            "--server.address",
            "0.0.0.0",
            "--server.fileWatcherType",
            "none",
        ]
    )
    subprocess.run(command, check=True, env=env)


if __name__ == "__main__" and not _in_streamlit_runtime() and os.environ.get("RS_RAG_STREAMLIT_LAUNCHED") != "1":
    launch_streamlit()
    raise SystemExit(0)


st.set_page_config(
    page_title="Warehouse Intelligence Chat",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)


CSS = """
<style>
  :root {
    --bg-0: #06111b;
    --bg-1: #091725;
    --panel: rgba(9, 20, 31, 0.82);
    --panel-strong: rgba(7, 16, 26, 0.96);
    --line: rgba(116, 188, 255, 0.14);
    --line-strong: rgba(88, 216, 167, 0.22);
    --text: #ecf6ff;
    --muted: #8baac0;
    --accent: #6bd2ff;
    --accent-2: #47d89f;
    --shadow: 0 24px 80px rgba(0, 0, 0, 0.28);
  }

  .stApp {
    background:
      radial-gradient(circle at top left, rgba(107, 210, 255, 0.12), transparent 22%),
      radial-gradient(circle at top right, rgba(71, 216, 159, 0.10), transparent 20%),
      linear-gradient(180deg, var(--bg-0), var(--bg-1));
    color: var(--text);
  }

  [data-testid="stAppViewContainer"],
  [data-testid="stMain"],
  [data-testid="stMainBlockContainer"] {
    background: transparent !important;
  }

  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  #MainMenu,
  footer {
    display: none !important;
  }

  .block-container {
    max-width: 1180px;
    padding-top: 2rem;
    padding-bottom: 2rem;
  }

  .hero {
    background: linear-gradient(135deg, rgba(9, 24, 39, 0.95), rgba(6, 16, 26, 0.96));
    border: 1px solid var(--line);
    border-radius: 32px;
    box-shadow: var(--shadow);
    padding: 30px 32px 26px;
    margin-bottom: 18px;
  }

  .hero-kicker {
    margin: 0;
    color: var(--accent-2);
    font-size: 0.84rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .hero h1 {
    margin: 8px 0 0;
    font-size: 3rem;
    letter-spacing: -0.04em;
    color: var(--text);
  }

  .hero p {
    margin: 8px 0 0;
    max-width: 840px;
    color: var(--muted);
    line-height: 1.55;
    font-size: 0.98rem;
  }

  .chip-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin-top: 22px;
  }

  .chip {
    background: rgba(10, 24, 37, 0.92);
    border: 1px solid var(--line);
    border-radius: 14px;
    color: var(--text);
    padding: 12px 14px;
    font-size: 0.9rem;
    line-height: 1.4;
  }

  .chat-shell {
    background: linear-gradient(180deg, rgba(9, 20, 31, 0.90), rgba(6, 13, 21, 0.96));
    border: 1px solid var(--line);
    border-radius: 32px;
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  .chat-shell-inner {
    padding: 18px 18px 0;
  }

  .chat-header {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 16px;
    padding: 2px 6px 16px;
  }

  .chat-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--text);
  }

  .chat-header p {
    margin: 6px 0 0;
    color: var(--muted);
  }

  .chat-feed {
    min-height: 240px;
    max-height: 58vh;
    overflow-y: auto;
    padding: 10px 6px 2px;
  }

  .message-row {
    display: flex;
    margin-bottom: 16px;
  }

  .message-row.user {
    justify-content: flex-end;
  }

  .message-row.assistant {
    justify-content: flex-start;
  }

  .bubble {
    max-width: 82%;
    padding: 14px 16px;
    border-radius: 22px;
    line-height: 1.68;
    font-size: 1rem;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.16);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .bubble.user {
    background: linear-gradient(135deg, rgba(107, 210, 255, 0.22), rgba(71, 216, 159, 0.20));
    border: 1px solid rgba(107, 210, 255, 0.28);
    color: var(--text);
  }

  .bubble.assistant {
    background: rgba(13, 26, 40, 0.96);
    border: 1px solid rgba(116, 188, 255, 0.10);
    color: var(--text);
  }

  .bubble-image {
    width: min(100%, 360px);
    display: block;
    margin-bottom: 12px;
    border-radius: 18px;
    border: 1px solid rgba(116, 188, 255, 0.16);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.24);
    object-fit: cover;
  }

  .bubble-caption {
    font-size: 0.82rem;
    color: var(--muted);
    margin-bottom: 8px;
  }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 220px;
    text-align: center;
    color: var(--muted);
    padding: 20px;
  }

  .composer {
    border-top: 1px solid rgba(116, 188, 255, 0.08);
    background: linear-gradient(180deg, rgba(8, 17, 27, 0.72), rgba(5, 12, 19, 0.94));
    padding: 16px 18px 18px;
  }

  [data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
  }

  .helper-chip {
    display: inline-flex;
    margin-bottom: 8px;
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(9, 20, 31, 0.86);
    border: 1px solid rgba(116, 188, 255, 0.12);
    color: var(--muted);
    font-size: 0.9rem;
  }

  .attachment-strip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;
    padding: 12px 14px;
    border-radius: 18px;
    background: rgba(9, 20, 31, 0.86);
    border: 1px solid rgba(116, 188, 255, 0.12);
  }

  .attachment-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    color: var(--text);
  }

  .attachment-thumb {
    width: 54px;
    height: 54px;
    border-radius: 14px;
    object-fit: cover;
    border: 1px solid rgba(116, 188, 255, 0.14);
  }

  .attachment-label {
    font-size: 0.92rem;
    color: var(--text);
  }

  .attachment-sub {
    font-size: 0.8rem;
    color: var(--muted);
  }

  .composer-tools {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
  }

  .plus-note {
    color: var(--muted);
    font-size: 0.88rem;
  }

  .stTextArea textarea,
  [data-baseweb="textarea"] textarea {
    background: rgba(8, 18, 28, 0.98) !important;
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
    border: 1px solid rgba(116, 188, 255, 0.18) !important;
    border-radius: 22px !important;
    min-height: 110px !important;
    padding-top: 14px !important;
    box-shadow: none !important;
  }

  [data-baseweb="textarea"] {
    background: rgba(8, 18, 28, 0.98) !important;
    border-radius: 22px !important;
  }

  [data-baseweb="base-input"] {
    background: transparent !important;
  }

  .stTextArea label,
  .stMarkdown,
  .stCaption,
  .stButton button,
  .st-emotion-cache-10trblm,
  .st-emotion-cache-16idsys p,
  [data-testid="stMarkdownContainer"] p,
  [data-testid="stMarkdownContainer"] span,
  [data-testid="stMarkdownContainer"] li {
    color: var(--text) !important;
  }

  .stButton button,
  [data-testid="stFormSubmitButton"] button,
  [data-testid="stPopoverButton"] button {
    border-radius: 16px !important;
    min-height: 50px;
    font-weight: 700;
    border: 1px solid rgba(116, 188, 255, 0.12) !important;
    box-shadow: none !important;
    color: var(--text) !important;
    background: rgba(10, 20, 31, 0.94) !important;
  }

  .primary-btn button,
  .primary-btn [data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, var(--accent), var(--accent-2)) !important;
    color: #04121b !important;
    border-color: transparent !important;
  }

  .secondary-btn button,
  .secondary-btn [data-testid="stFormSubmitButton"] button {
    background: rgba(10, 20, 31, 0.94) !important;
    color: var(--text) !important;
    border: 1px solid var(--line) !important;
  }

  .stButton button:hover,
  [data-testid="stFormSubmitButton"] button:hover,
  [data-testid="stPopoverButton"] button:hover {
    border-color: rgba(116, 188, 255, 0.24) !important;
    color: var(--text) !important;
  }

  .stButton button p,
  [data-testid="stFormSubmitButton"] button p,
  [data-testid="stPopoverButton"] button p,
  .stButton button span,
  [data-testid="stFormSubmitButton"] button span,
  [data-testid="stPopoverButton"] button span {
    color: inherit !important;
  }

  [data-testid="stFileUploader"] {
    background: rgba(8, 18, 28, 0.92) !important;
    border: 1px dashed rgba(116, 188, 255, 0.22) !important;
    border-radius: 20px !important;
    padding: 6px !important;
  }

  [data-testid="stFileUploader"] section {
    background: transparent !important;
  }

  [data-testid="stFileUploader"] small,
  [data-testid="stFileUploader"] span,
  [data-testid="stFileUploader"] label {
    color: var(--muted) !important;
  }

  .stTextArea textarea::placeholder,
  [data-baseweb="textarea"] textarea::placeholder {
    color: rgba(139, 170, 192, 0.72) !important;
  }

  .example-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 8px;
  }

  .example-pill {
    background: rgba(10, 20, 31, 0.92);
    border: 1px solid rgba(116, 188, 255, 0.10);
    color: var(--muted);
    border-radius: 999px;
    padding: 8px 12px;
    font-size: 0.88rem;
  }

  @media (max-width: 780px) {
    .hero {
      padding: 22px 18px 18px;
      border-radius: 24px;
    }

    .hero h1 {
      font-size: 2.1rem;
    }
  }
</style>
"""


def get_brain() -> WarehouseAI:
    kill_external = os.environ.get("RS_RAG_KILL_EXTERNAL_GPU", "1") == "1"
    clear_gpu_memory(kill_external=kill_external)
    return WarehouseAI()


def reset_chat():
    if "brain" in st.session_state:
        del st.session_state["brain"]
    st.session_state["messages"] = []
    st.session_state["refined_query"] = ""
    st.session_state["pending_image_bytes"] = None
    st.session_state["pending_image_name"] = ""
    st.session_state["active_image_bytes"] = None
    st.session_state["active_image_name"] = ""
    st.session_state["uploader_nonce"] = st.session_state.get("uploader_nonce", 0) + 1
    kill_external = os.environ.get("RS_RAG_KILL_EXTERNAL_GPU", "1") == "1"
    clear_gpu_memory(kill_external=kill_external)


def ensure_state():
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "refined_query" not in st.session_state:
        st.session_state["refined_query"] = ""
    if "pending_image_bytes" not in st.session_state:
        st.session_state["pending_image_bytes"] = None
    if "pending_image_name" not in st.session_state:
        st.session_state["pending_image_name"] = ""
    if "active_image_bytes" not in st.session_state:
        st.session_state["active_image_bytes"] = None
    if "active_image_name" not in st.session_state:
        st.session_state["active_image_name"] = ""
    if "uploader_nonce" not in st.session_state:
        st.session_state["uploader_nonce"] = 0


def to_png_data_url(image_bytes: bytes) -> str:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def render_message(role: str, content: str, image_bytes: bytes | None = None, image_name: str | None = None):
    safe = html.escape(content).replace("\n", "<br>")

    if role == "user":
        spacer, content_col = st.columns([1.3, 2.2])
    else:
        content_col, spacer = st.columns([2.2, 1.3])

    with content_col:
        if image_bytes:
            st.caption(image_name or "Image")
            st.image(image_bytes, width="stretch")
        st.markdown(
            f"""
            <div class="message-row {role}">
              <div class="bubble {role}">{safe}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat():
    messages = st.session_state["messages"]
    if not messages:
        st.markdown(
            """
            <div class="empty-state">
              <div>
                <div style="font-size:1.2rem;color:#ecf6ff;margin-bottom:8px;">Start a warehouse conversation</div>
                <div>Ask for aisle counts, layout summaries, object totals, or anything grounded in the indexed data.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for item in messages:
        render_message(
            item["role"],
            item["content"],
            item.get("image_bytes"),
            item.get("image_name"),
        )


def clear_pending_image():
    st.session_state["pending_image_bytes"] = None
    st.session_state["pending_image_name"] = ""
    st.session_state["uploader_nonce"] += 1


def clear_active_image_context():
  st.session_state["active_image_bytes"] = None
  st.session_state["active_image_name"] = ""


def _image_context_status() -> str:
  if st.session_state.get("pending_image_bytes"):
    return "Attachment queued"
  if st.session_state.get("active_image_bytes"):
    return "Image context active"
  return "No active image"


def _chat_turn_count() -> int:
    return sum(1 for item in st.session_state.get("messages", []) if item.get("role") == "user")


def build_hero_chips() -> list[str]:
  return [
    f"Indexed objects: {SNAPSHOT['total_items']}",
    f"Boxes: {SNAPSHOT['category_counts'].get('box', 0)}",
    f"Inferred aisles: {SNAPSHOT['inferred_aisle_count']}",
    f"Chat turns: {_chat_turn_count()}",
    f"Image mode: {_image_context_status()}",
  ]


def submit_message(prompt: str, image_bytes: bytes | None = None, image_name: str | None = None):
    prompt = prompt.strip()
    if not prompt and image_bytes is None:
        return

    if "brain" not in st.session_state:
        st.session_state["brain"] = get_brain()

    brain: WarehouseAI = st.session_state["brain"]
    if image_bytes is None and st.session_state.get("active_image_bytes") and brain.should_use_image_context(prompt, st.session_state["messages"]):
        image_bytes = st.session_state["active_image_bytes"]
        image_name = st.session_state.get("active_image_name")

    user_text = prompt or "What objects are in this image?"
    user_message = {
        "role": "user",
        "content": user_text,
        "image_bytes": image_bytes,
        "image_name": image_name,
    }

    if image_bytes is not None:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        answer, metadata, annotated_bytes = brain.process_image_query(image, user_text, st.session_state["messages"])
        st.session_state["active_image_bytes"] = image_bytes
        st.session_state["active_image_name"] = image_name or "Current image"
        assistant_message = {
            "role": "assistant",
            "content": answer,
            "image_bytes": annotated_bytes,
            "image_name": "Annotated detection result" if annotated_bytes else None,
        }
    else:
        answer, metadata = brain.process_text_query(user_text, st.session_state["messages"])
        assistant_message = {"role": "assistant", "content": answer}

    st.session_state["messages"].append(user_message)
    st.session_state["messages"].append(assistant_message)
    st.session_state["refined_query"] = metadata.get("refined_query", "")
    clear_pending_image()


ensure_state()
st.markdown(CSS, unsafe_allow_html=True)

hero_chips = build_hero_chips()

st.markdown(
    f"""
    <div class="hero">
      <div class="hero-kicker">Warehouse Vision + RAG</div>
      <h1>Warehouse Intelligence Chat</h1>
      <p>Ask about inventory, aisles, detected objects, and scene-grounded locations in one place.</p>
      <div class="chip-row">
        {''.join(f'<div class="chip">{html.escape(chip)}</div>' for chip in hero_chips)}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="chat-shell"><div class="chat-shell-inner">', unsafe_allow_html=True)
st.markdown('<div class="chat-feed">', unsafe_allow_html=True)
render_chat()
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="composer">', unsafe_allow_html=True)
if st.session_state.get("refined_query"):
    st.caption(f"Refined query: {st.session_state['refined_query']}")

st.markdown(
    """
    <div class="composer-tools">
      <div class="plus-note">Attach an image and ask about objects, likely warehouse positions, or request highlighted detections. Follow-up image questions will keep using the current image until you clear the chat.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.popover("＋", width="content"):
    uploaded_file = st.file_uploader(
        "Attach warehouse image",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"chat_uploader_{st.session_state['uploader_nonce']}",
        label_visibility="collapsed",
    )
    if uploaded_file is not None:
        uploaded_bytes = uploaded_file.getvalue()
        st.session_state["pending_image_bytes"] = uploaded_bytes
        st.session_state["pending_image_name"] = uploaded_file.name
        st.image(uploaded_bytes, caption=uploaded_file.name, width="stretch")

if st.session_state.get("pending_image_bytes"):
    preview_url = to_png_data_url(st.session_state["pending_image_bytes"])
    st.markdown(
        f"""
        <div class="attachment-strip">
          <div class="attachment-meta">
            <img class="attachment-thumb" src="{preview_url}" alt="attachment preview">
            <div>
              <div class="attachment-label">{html.escape(st.session_state.get("pending_image_name") or "Attached image")}</div>
              <div class="attachment-sub">This image will be sent with your next message.</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    remove_attachment = st.button("Remove Attachment", width="stretch", key="remove_attachment")
    if remove_attachment:
        clear_pending_image()
        st.rerun()

if st.session_state.get("active_image_bytes") and not st.session_state.get("pending_image_bytes"):
    active_preview_url = to_png_data_url(st.session_state["active_image_bytes"])
    st.markdown(
        f"""
        <div class="attachment-strip">
          <div class="attachment-meta">
            <img class="attachment-thumb" src="{active_preview_url}" alt="active image preview">
            <div>
              <div class="attachment-label">{html.escape(st.session_state.get("active_image_name") or "Current image")}</div>
              <div class="attachment-sub">Image context is active for follow-up visual questions.</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    remove_active_context = st.button("Remove Image Context", width="stretch", key="remove_active_image_context")
    if remove_active_context:
        clear_active_image_context()
        st.rerun()

with st.form("warehouse-chat-form", clear_on_submit=True):
    prompt = st.text_area(
        "Ask about the warehouse",
        placeholder="Message Warehouse Copilot...",
        label_visibility="collapsed",
    )
    col1, col2, col3 = st.columns([1.1, 1, 1])
    with col1:
        st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
        ask_clicked = st.form_submit_button("Ask Copilot", width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
        clear_clicked = st.form_submit_button("Clear Chat", width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
        reset_clicked = st.form_submit_button("Reset Model Cache", width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)

if ask_clicked:
    with st.spinner("Thinking through the warehouse data and image..."):
        submit_message(
            prompt,
            st.session_state.get("pending_image_bytes"),
            st.session_state.get("pending_image_name"),
        )
    st.rerun()

if clear_clicked:
    st.session_state["messages"] = []
    st.session_state["refined_query"] = ""
    st.rerun()

if reset_clicked:
    reset_chat()
    st.rerun()

st.caption("Examples")
st.markdown(
    '<div class="example-grid">' + "".join(f'<div class="example-pill">{html.escape(example)}</div>' for example in TEXT_EXAMPLES) + "</div>",
    unsafe_allow_html=True,
)
st.markdown("</div></div>", unsafe_allow_html=True)

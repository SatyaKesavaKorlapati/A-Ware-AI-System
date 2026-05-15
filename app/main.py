import sys
import os
import io
import re
from pathlib import Path

# --- 1. Fix OS File Watcher Error ---
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import streamlit as st
from PIL import Image

# Add project root to path for relative imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.engine import WarehouseAI

# --- 2. Page Configuration ---
st.set_page_config(
    page_title="A-Ware",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="expanded" 
)

# --- 3. UI CSS Injection ---
st.markdown("""
<style>
    /* Absolute Dark Mode */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0d0d0e !important;
        color: #e3e3e3 !important;
        font-family: 'Inter', 'Roboto', sans-serif;
    }
    
    .main .block-container { background-color: #0d0d0e !important; }
    [data-testid="stBottom"], [data-testid="stBottomBlock"] { background-color: #0d0d0e !important; }
    
    /* FIX: Hide branding but KEEP the sidebar toggle visible */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { background: transparent !important; }

    /* Sidebar Dark */
    [data-testid="stSidebar"] {
        background-color: #0d0d0e !important;
        border-right: 1px solid #2a2b2c !important;
    }
    [data-testid="stSidebar"] > div { background-color: #0d0d0e !important; }
    
    /* Custom Title Header */
    .a-ware-title {
        font-size: 2.2rem;
        font-weight: 500;
        padding-top: 10px;
        padding-bottom: 30px;
        color: #e3e3e3 !important;
    }

    /* Chat Input Container */
    .stChatInputContainer {
        background-color: #1a1b1c !important;
        border-radius: 30px !important;
        border: 1px solid #2a2b2c !important;
    }
    .stChatInputContainer textarea {
        background-color: #1a1b1c !important;
        color: #e3e3e3 !important;
        -webkit-text-fill-color: #e3e3e3 !important;
        border: none !important;
    }
    
    /* Assistant Message Block */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: transparent !important;
        border: none !important;
        padding: 0px 10px;
        margin-bottom: 24px;
        margin-left: 0 !important;
        width: 100% !important;
    }

    /* Expander Styling for Collapsed Thinking */
    [data-testid="stExpander"] {
        background-color: #1a1b1c !important;
        border: 1px solid #2a2b2c !important;
        border-radius: 12px;
        margin-bottom: 15px;
    }
    [data-testid="stExpander"] p, [data-testid="stExpander"] span {
        color: #a8c7fa !important;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. Engine & State Initialization ---
@st.cache_resource(show_spinner=False)
def load_engine():
    return WarehouseAI()

engine = load_engine()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_images" not in st.session_state:
    st.session_state.active_images = [] 

# --- 5. Sidebar Controls ---
with st.sidebar:
    st.markdown("## A-Ware Controls")
    
    if st.button("🗑️ Clear All Chat & Context", use_container_width=True):
        st.session_state.messages = []
        st.session_state.active_images = []
        st.rerun()

    st.markdown("---")
    
    with st.expander("🖼️ Manage Active Images", expanded=True):
        if not st.session_state.active_images:
            st.info("No active images.")
        else:
            for idx, img_bytes in enumerate(st.session_state.active_images):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.image(img_bytes, caption=f"View {idx+1}", use_container_width=True)
                with col2:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.active_images.pop(idx)
                        st.rerun()
            st.caption(f"Count: {len(st.session_state.active_images)} / 5")

# --- 6. Helper Function to Render Thinking Blocks ---
def render_message_content(content):
    """Extracts <thinking> blocks and renders them inside a collapsed expander."""
    # Robust fallback just in case tags are missing or malformed
    if "<thinking>" in content:
        match = re.search(r"<thinking>(.*?)(?:</thinking>|$)", content, flags=re.DOTALL)
        if match:
            thinking_text = match.group(1).strip()
            clean_content = re.sub(r"<thinking>.*?(?:</thinking>|$)", "", content, flags=re.DOTALL).strip()
            
            with st.expander("Thought Process"):
                st.markdown(thinking_text)
            st.markdown(clean_content)
        else:
            st.markdown(content)
    else:
        st.markdown(content)

# --- 7. Main Chat Interface ---
st.markdown('<div class="a-ware-title">A-Ware</div>', unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("image_list"):
            cols = st.columns(min(len(msg["image_list"]), 3))
            for i, img_b in enumerate(msg["image_list"]):
                cols[i % 3].image(img_b, use_container_width=True)
        
        render_message_content(msg["content"])
        
        if msg.get("annotated_list"):
            st.markdown("### Vision Annotations")
            for i, ann_img in enumerate(msg["annotated_list"]):
                st.image(ann_img, caption=f"View {i+1} Detection", use_container_width=True)

# --- 8. Input & Processing ---
prompt_data = st.chat_input("Ask about spatial data or multiple viewpoints...", accept_file=True, file_type=['png', 'jpg', 'jpeg', 'webp'])

if prompt_data:
    prompt_text = prompt_data.text.strip() if hasattr(prompt_data, 'text') and prompt_data.text else ""
    uploaded_files = prompt_data.get("files") if hasattr(prompt_data, "get") else getattr(prompt_data, "files", [])
    
    just_uploaded_list = []
    if uploaded_files:
        for file in uploaded_files:
            if len(st.session_state.active_images) < 5:
                img_data = file.getvalue()
                st.session_state.active_images.append(img_data)
                just_uploaded_list.append(img_data)
        
        if not prompt_text:
            prompt_text = "Perform an inventory scan on these views."

    if not prompt_text and not st.session_state.active_images:
        st.stop()

    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    
    with st.chat_message("user"):
        if just_uploaded_list:
            cols = st.columns(min(len(just_uploaded_list), 3))
            for i, img_b in enumerate(just_uploaded_list):
                cols[i % 3].image(img_b, use_container_width=True)
        st.markdown(prompt_text)
    
    st.session_state.messages.append({
        "role": "user", 
        "content": prompt_text, 
        "image_list": just_uploaded_list if just_uploaded_list else None
    })

    with st.chat_message("assistant"):
        all_metadata = []
        all_annotations = []
        combined_answers = []
        
        with st.status("✨ Analyzing Facility...", expanded=True) as status:
            if st.session_state.active_images:
                for idx, img_bytes in enumerate(st.session_state.active_images):
                    img_obj = Image.open(io.BytesIO(img_bytes))
                    ans, meta, ann = engine.process_image_query(img_obj, prompt_text, history)
                    
                    # Only prepend "View X" if we actually have multiple images to prevent annoyance on single images
                    prefix = f"**View {idx+1}:**\n" if len(st.session_state.active_images) > 1 else ""
                    combined_answers.append(f"{prefix}{ans}")
                    all_metadata.append(meta)
                    if ann: all_annotations.append(ann)
            else:
                ans, meta = engine.process_text_query(prompt_text, history)
                combined_answers.append(ans)
                all_metadata.append(meta)
            
            status.update(label="Scan Complete", state="complete", expanded=False)

        final_response = "\n\n---\n\n".join(combined_answers)
        render_message_content(final_response)
        
        if all_annotations:
            st.markdown("### Aggregated Detections")
            for i, ann in enumerate(all_annotations):
                st.image(ann, caption=f"Annotated View {i+1}", use_container_width=True)

    st.session_state.messages.append({
        "role": "assistant",
        "content": final_response,
        "annotated_list": all_annotations if all_annotations else None,
        "metadata": all_metadata
    })
    
    st.rerun()
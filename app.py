"""
Streamlit app for interactive PDF structure navigation.

Run with:
    streamlit run app.py
"""

import os
import tempfile
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="PDF Structure Navigator", layout="wide")
st.title("PDF Structure Navigator")


# ── helpers ──────────────────────────────────────────────────────────────────

def _run_agent(pdf_path: str):
    from src.agent import get_config
    from src.doc_parser import build_tree
    config = get_config(pdf_path)
    roots = build_tree(pdf_path, config)
    return config, roots


def _run_baseline(pdf_path: str):
    from baseline import get_config_baseline
    from src.doc_parser import build_tree
    config = get_config_baseline(pdf_path)
    roots = build_tree(pdf_path, config)
    return config, roots


def _render_node(node, depth: int = 0):
    """Render a Node as an expander with body text and children."""
    prefix = "\u00a0" * (depth * 4)
    label = f"{prefix}{node.text}"
    with st.expander(label, expanded=(depth == 0)):
        if node.body:
            for para in node.body:
                st.markdown(para)
        for child in node.children:
            _render_node(child, depth + 1)


def _render_tree(roots):
    if not roots:
        st.warning("No structural nodes found.")
        return
    for root in roots:
        _render_node(root, depth=0)


# ── sidebar: upload + options ─────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")
    uploaded = st.file_uploader("Upload PDF", type="pdf")
    method = st.radio(
        "Method",
        ["Agent (docling + LLM rules)", "Baseline (full text → LLM)"],
        help=(
            "Agent: docling extracts structural elements, LLM infers rules, "
            "deterministic parser builds the tree.\n\n"
            "Baseline: full PDF text sent directly to GPT-4o-mini."
        ),
    )
    run_btn = st.button("Run", type="primary", disabled=(uploaded is None))

# ── main area ─────────────────────────────────────────────────────────────────

if uploaded is None:
    st.info("Upload a PDF in the sidebar to get started.")
    st.stop()

# Write upload to a temp file once per session / per file change
file_key = f"{uploaded.name}_{uploaded.size}"
if st.session_state.get("file_key") != file_key:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(uploaded.read())
    tmp.flush()
    st.session_state["tmp_path"] = tmp.name
    st.session_state["file_key"] = file_key
    # clear previous results when a new file is uploaded
    st.session_state.pop("result", None)

pdf_path = st.session_state["tmp_path"]

if run_btn:
    with st.spinner("Processing…"):
        try:
            if method.startswith("Agent"):
                config, roots = _run_agent(pdf_path)
            else:
                config, roots = _run_baseline(pdf_path)
            st.session_state["result"] = (config, roots, method)
        except Exception as exc:
            st.error(f"Error: {exc}")
            st.stop()

if "result" in st.session_state:
    config, roots, used_method = st.session_state["result"]

    col_info, col_tree = st.columns([1, 3])

    with col_info:
        st.subheader("Document info")
        st.markdown(f"**Domain:** {config.get('domain', '—')}")
        if config.get("notes"):
            st.markdown(f"**Notes:** {config['notes']}")
        st.markdown(f"**Method:** {used_method}")
        st.markdown("---")
        st.subheader("Rules")
        for r in config.get("rules", []):
            st.markdown(f"- `{r['pattern']}` ({r['type']}, depth {r['depth']})")

    with col_tree:
        st.subheader("Document tree")
        st.caption("Expand a heading to see its body text and sub-sections.")
        _render_tree(roots)

"""
Group Project — RAG Chatbot với Hybrid Search + Generation + Conversation Memory

Chạy:
    streamlit run group_project/app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.supervisor_workers import SupervisorAgent


@st.cache_resource
def get_supervisor() -> SupervisorAgent:
    """Create one reusable Supervisor for the Streamlit process."""
    return SupervisorAgent()

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(page_title="DrugLaw Chatbot", page_icon="🤖", layout="wide")

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.header("⚙️ Settings")

    top_k = st.slider("Top K chunks", 1, 20, 5)
    score_threshold = st.slider("Score Threshold", 0.0, 1.0, 0.3, 0.05)
    use_reranking = st.checkbox("Cross-Encoder Reranking", value=True)

    st.divider()

    mimo_key = os.getenv("MIMO_API_KEY", "")
    mimo_url = os.getenv("MIMO_BASE_URL", "")
    if mimo_key and mimo_url:
        st.success("Mimo API: Connected")
    else:
        st.error("Mimo API: Not configured\n\nAdd MIMO_API_KEY + MIMO_BASE_URL to .env")

    st.divider()

    if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.header("📊 Index Stats")
    try:
        from src.task4_chunking_indexing import get_chroma_collection
        col = get_chroma_collection()
        st.metric("Chunks Indexed", col.count())
    except Exception:
        st.warning("Chưa index data")

# =============================================================================
# SESSION STATE
# =============================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# =============================================================================
# HEADER
# =============================================================================
st.title("🤖 DrugLaw Chatbot")
st.caption(
    "Supervisor điều phối Legal, News và Evidence Workers "
    "| Hybrid RAG + Mimo LLM"
)

# =============================================================================
# DISPLAY CHAT HISTORY
# =============================================================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"📚 Sources ({len(msg['sources'])} chunks)"):
                for i, src in enumerate(msg["sources"], 1):
                    s = src.get("metadata", {}).get("source", "?")
                    t = src.get("metadata", {}).get("type", "?")
                    score = src.get("score", 0)
                    emoji = "📜" if t == "legal" else "📰"
                    st.markdown(f"**{emoji} [{i}] {s}** (score: {score:.4f})")
                    st.caption(src["content"][:200] + "...")
        if msg.get("worker_reports"):
            with st.expander("🧭 Supervisor execution"):
                st.caption(msg.get("supervisor_plan", ""))
                for report in msg["worker_reports"]:
                    st.markdown(
                        f"**{report['name']}** · {report['status']} · "
                        f"{len(report['sources'])} sources · "
                        f"{report['latency_seconds']:.3f}s"
                    )

# =============================================================================
# CHAT INPUT
# =============================================================================
query = st.chat_input("Hỏi về pháp luật ma tuý, nghệ sĩ liên quan...")

if query:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Generate answer
    with st.chat_message("assistant"):
        with st.spinner("Supervisor đang điều phối các workers..."):
            supervisor = get_supervisor()
            result = supervisor.run(
                query,
                top_k=top_k,
                score_threshold=score_threshold,
                use_reranking=use_reranking,
                history=st.session_state.messages[:-1],
            )

            st.markdown(result.answer)
            st.caption(
                f"Intent: {result.plan.intent} · "
                f"{len(result.worker_reports)} workers · "
                f"{result.total_seconds:.2f}s total"
            )

            with st.expander("🧭 Supervisor plan & worker reports", expanded=True):
                st.markdown(f"**Routing:** {result.plan.rationale}")
                for report in result.worker_reports:
                    icon = "✅" if report.status == "completed" else "⚠️"
                    st.markdown(
                        f"{icon} **{report.name}** — {report.role}  \n"
                        f"Status: `{report.status}` · "
                        f"Sources: `{len(report.sources)}` · "
                        f"Confidence: `{report.confidence:.2f}` · "
                        f"Latency: `{report.latency_seconds:.3f}s`"
                    )
                    if report.error:
                        st.error(report.error)

            with st.expander(f"📚 Sources ({len(result.sources)} chunks)"):
                for i, src in enumerate(result.sources, 1):
                    s = src.get("metadata", {}).get("source", "?")
                    t = src.get("metadata", {}).get("type", "?")
                    score = src.get("score", 0)
                    emoji = "📜" if t == "legal" else "📰"
                    st.markdown(f"**{emoji} [{i}] {s}** (score: {score:.4f})")
                    st.caption(src["content"][:200] + "...")

            st.session_state.messages.append({
                "role": "assistant",
                "content": result.answer,
                "sources": result.sources,
                "supervisor_plan": (
                    f"{result.plan.intent}: "
                    f"{', '.join(result.plan.worker_names)}"
                ),
                "worker_reports": [
                    {
                        "name": report.name,
                        "status": report.status,
                        "sources": report.sources,
                        "latency_seconds": report.latency_seconds,
                    }
                    for report in result.worker_reports
                ],
            })

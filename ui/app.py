import os

import httpx
import streamlit as st

st.set_page_config(page_title="WK15 AI Assistant", page_icon="🤖", layout="centered")

DEFAULT_BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")

with st.sidebar:
    st.header("Settings")
    backend = st.text_input("Backend URL", value=st.session_state.get("backend", DEFAULT_BACKEND))
    st.session_state.backend = backend
    use_rag = st.toggle("Use RAG", value=True)
    use_tools = st.toggle("Allow tool calling", value=True)
    st.divider()
    if st.button("Re-ingest documents"):
        try:
            with st.spinner("Indexing..."):
                stats = httpx.post(f"{backend}/ingest", timeout=300).json()
            st.success(f"Indexed {stats['files']} files into {stats['chunks']} chunks.")
        except Exception as exc:
            st.error(f"Ingest failed: {exc}")

st.title("WK15 AI Assistant")
st.caption("Gemini primary → vLLM local → Ollama fallback · RAG · structured output · tool calling")

if "messages" not in st.session_state:
    st.session_state.messages = []

for entry in st.session_state.messages:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])
    meta = entry.get("meta")
    if meta:
        details = st.expander("Details")
        details.caption(
            f"provider=`{meta.get('provider_used')}` · latency={meta.get('latency_ms')}ms · "
            f"cached={meta.get('cached')} · degraded={meta.get('degraded')}"
        )
        if meta.get("sources"):
            details.write("**Sources**")
            for src in meta["sources"]:
                details.write(f"- `{src['source']}` (score={src.get('score')})")
        if meta.get("tools_called"):
            details.write(f"**Tools called:** {', '.join(meta['tools_called'])}")

prompt = st.chat_input("Ask something...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = httpx.post(
                    f"{backend}/chat",
                    json={"message": prompt, "use_rag": use_rag, "use_tools": use_tools},
                    timeout=180,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                data = {
                    "answer": f"⚠️ Backend error: {exc}",
                    "provider_used": "none",
                    "sources": [],
                    "tools_called": [],
                    "latency_ms": 0,
                    "cached": False,
                    "degraded": True,
                }
        st.markdown(data["answer"])
    st.session_state.messages.append({"role": "assistant", "content": data["answer"], "meta": data})

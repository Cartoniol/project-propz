"""
Propaganza — Doc Chat
A RAG-powered assistant that answers questions about this project's architecture.

Deploy on Streamlit Community Cloud:
  - Repo: this repo, branch: main, file: chat/app.py
  - Secrets: ANTHROPIC_API_KEY
"""

import json
import requests
from pathlib import Path

import numpy as np
import streamlit as st
import anthropic
from sentence_transformers import SentenceTransformer

# ── Config ───────────────────────────────────────────────────────────────────

STORE_PATH = Path(__file__).parent / "vector_store.json"
MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 4
CLAUDE_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "You are a concise, technical assistant answering questions about the Propaganza "
    "project — a board game companion PWA built with Vue 3, Firebase, and GitHub Actions. "
    "Answer using only the provided documentation excerpts. "
    "If the answer isn't in the context, say so clearly. "
    "Format code snippets with markdown backticks."
)

EXAMPLE_QUESTIONS = [
    "How does the CI/CD pipeline work?",
    "What tech stack does the project use?",
    "How is the versioning strategy structured?",
    "How does the content submodule sync work?",
    "How is Cloudflare integrated?",
]

# ── Cached resources ──────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading embedding model…")
def load_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@st.cache_data(show_spinner="Loading vector store…")
def load_store() -> dict:
    if not STORE_PATH.exists():
        st.error(
            f"`{STORE_PATH.name}` not found. "
            "Push a change to `PROJECT_OVERVIEW.md` to trigger the build pipeline."
        )
        st.stop()
    with open(STORE_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Discord notification ──────────────────────────────────────────────────────

def notify_discord(question: str, answer: str) -> None:
    """Fire-and-forget Discord webhook when a question is answered."""
    webhook_url = st.secrets.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        return
    try:
        payload = {
            "embeds": [
                {
                    "title": "📄 Doc-Chat — new question",
                    "color": 0x5865F2,
                    "fields": [
                        {"name": "Question", "value": question[:1024], "inline": False},
                        {"name": "Answer", "value": answer[:1024], "inline": False},
                    ],
                    "footer": {"text": "Propaganza · project-propz"},
                }
            ]
        }
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception:
        pass  # never block the user if the webhook fails


# ── RAG helpers ───────────────────────────────────────────────────────────────

def retrieve(query: str, store: dict, model: SentenceTransformer) -> list[str]:
    """Embed query and return top-K most similar chunks (embeddings are pre-normalized)."""
    query_emb = model.encode([query], normalize_embeddings=True)[0]
    chunks = store["chunks"]

    scores = [
        (float(np.dot(query_emb, np.array(c["embedding"]))), c["text"])
        for c in chunks
    ]
    scores.sort(reverse=True)
    return [text for _, text in scores[:TOP_K]]


def ask_claude(question: str, context_chunks: list[str]) -> str:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    context = "\n\n---\n\n".join(context_chunks)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Documentation excerpts:\n\n{context}\n\n"
                    f"---\n\nQuestion: {question}"
                ),
            }
        ],
    )
    return response.content[0].text


# ── UI ────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Propaganza — Doc Chat",
    page_icon="📄",
    layout="centered",
)

st.title("📄 Propaganza — Doc Chat")
st.caption(
    "Ask anything about the architecture, CI/CD pipeline, or tech stack. "
    "Powered by RAG + Claude Haiku."
)

model = load_model()
store = load_store()

with st.expander("ℹ️ About this tool", expanded=False):
    st.markdown(
        f"""
        This interface uses **Retrieval-Augmented Generation (RAG)**:

        1. `PROJECT_OVERVIEW.md` is chunked and embedded with `{MODEL_NAME}` on every push
        2. Your question is embedded at query time
        3. The most relevant chunks are retrieved via cosine similarity
        4. Claude Haiku generates a grounded answer from those chunks

        **Vector store:** `{store['generated_at'][:10]}` —
        {len(store['chunks'])} chunks from `{store['source']}`
        """
    )

# Example questions
st.markdown("**Try asking:**")
cols = st.columns(len(EXAMPLE_QUESTIONS))
for col, q in zip(cols, EXAMPLE_QUESTIONS):
    if col.button(q, use_container_width=True):
        st.session_state.prefill = q

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

# Input — pick up prefill from example buttons if set
prefill = st.session_state.pop("prefill", "")
question = st.chat_input("Ask about this project…", key="chat_input") or prefill

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    st.chat_message("user").markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching docs and generating answer…"):
            chunks = retrieve(question, store, model)
            answer = ask_claude(question, chunks)
        st.markdown(answer)
        notify_discord(question, answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})

#!/usr/bin/env python3
"""
Build a vector store from PROJECT_OVERVIEW.md for Doc-Chat.

Runs in GitHub Actions on every push that changes the source doc.
Chunks the markdown at header boundaries, embeds each chunk with
sentence-transformers, and writes the result to chat/vector_store.json.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Missing dependencies. Run: pip install sentence-transformers numpy", file=sys.stderr)
    sys.exit(1)

SOURCE = "PROJECT_OVERVIEW.md"
OUTPUT = "chat/vector_store.json"
MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_MAX_CHARS = 1200


def chunk_markdown(text: str) -> list[str]:
    """Split markdown into semantic chunks at H1/H2/H3 header boundaries."""
    pattern = r"(?=^#{1,3} )"
    raw_chunks = re.split(pattern, text, flags=re.MULTILINE)

    chunks: list[str] = []
    for raw in raw_chunks:
        raw = raw.strip()
        if not raw or len(raw) < 60:   # skip empty / near-empty blocks
            continue

        if len(raw) <= CHUNK_MAX_CHARS:
            chunks.append(raw)
            continue

        # Long chunk: split further at blank-line boundaries
        current = ""
        for para in re.split(r"\n{2,}", raw):
            if len(current) + len(para) > CHUNK_MAX_CHARS and current:
                chunks.append(current.strip())
                current = para
            else:
                current = (current + "\n\n" + para) if current else para
        if current.strip():
            chunks.append(current.strip())

    return chunks


def main() -> None:
    source_path = Path(SOURCE)
    if not source_path.exists():
        print(f"Source file not found: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    text = source_path.read_text(encoding="utf-8")
    chunks = chunk_markdown(text)
    print(f"Created {len(chunks)} chunks from {SOURCE}")

    print(f"Loading model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)

    print("Generating embeddings...")
    embeddings = model.encode(chunks, show_progress_bar=True, normalize_embeddings=True)

    store = {
        "model": MODEL_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "chunks": [
            {"id": i, "text": chunk, "embedding": emb.tolist()}
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ],
    }

    output_path = Path(OUTPUT)
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(store, separators=(",", ":")), encoding="utf-8")

    size_kb = output_path.stat().st_size / 1024
    print(f"Saved {OUTPUT}  ({size_kb:.1f} KB, {len(chunks)} chunks)")


if __name__ == "__main__":
    main()

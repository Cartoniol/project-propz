#!/usr/bin/env python3
"""
VibeBot — AI commentary on every commit.

Gets the latest commit message + diff, sends it to Claude Haiku,
and prepends a witty vibe entry to VIBE_LOG.md.
"""

import os
import subprocess
import sys
from datetime import datetime

try:
    import anthropic
except ImportError:
    print("anthropic package not found. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

VIBE_LOG = "VIBE_LOG.md"
MAX_DIFF_LINES = 150
# Binary/generated files to exclude from the diff to keep prompts clean
DIFF_EXCLUDES = ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.ico", "*.woff*", "*.ttf"]


def run(cmd: str) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout.strip()


def get_commit_info() -> tuple[str, str, str, str]:
    message = run("git log -1 --pretty=%B")
    author = run("git log -1 --pretty=%an")
    changed_files = run("git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only HEAD")

    # Build exclude flags for binary/generated files
    excludes = " ".join(f"':(exclude){p}'" for p in DIFF_EXCLUDES)
    diff = run(f"git diff HEAD~1 HEAD -- . {excludes} 2>/dev/null || git show --stat HEAD")

    diff_lines = diff.splitlines()
    if len(diff_lines) > MAX_DIFF_LINES:
        diff = "\n".join(diff_lines[:MAX_DIFF_LINES])
        diff += f"\n\n[... diff truncated at {MAX_DIFF_LINES} lines ...]"

    return message, author, changed_files, diff


def call_claude(message: str, author: str, files: str, diff: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""You are VibeBot — a brutally honest, slightly sarcastic, but secretly supportive AI code reviewer.
You have been given the latest git commit from a developer. Your job: write a short, witty "vibe check" — a personality-driven micro-review of the commit.

Rules:
- Be funny, sharp, and specific to the actual changes. Never be generic.
- Mix technical insight with personality. Reference actual file names or patterns you see in the diff.
- Keep it to 2–4 sentences max.
- End with a vibe score: X/10 — One-Word-Label (e.g. "8/10 — Immaculate", "6/10 — Chaotic Neutral").
- Write in English.

Commit message: {message}
Author: {author}
Files changed:
{files}

Diff (may be truncated):
{diff}

Write the vibe check now:"""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def update_vibe_log(message: str, author: str, vibe_text: str) -> None:
    date = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")
    short_msg = message.split("\n")[0][:80]

    entry = (
        f"## {date}\n\n"
        f"**Commit:** `{short_msg}`  \n"
        f"**Author:** {author}\n\n"
        f"> {vibe_text}\n\n"
        f"---\n\n"
    )

    existing = ""
    if os.path.exists(VIBE_LOG):
        with open(VIBE_LOG, "r", encoding="utf-8") as f:
            existing = f.read()

    header = "# VIBE_LOG\n\n*Automated AI commentary on every commit. Powered by VibeBot + Claude Haiku.*\n\n---\n\n"

    if not existing.startswith("# VIBE_LOG"):
        existing = header + existing

    # Insert new entry right after the header separator
    split_marker = "---\n\n"
    idx = existing.index(split_marker) + len(split_marker)
    new_content = existing[:idx] + entry + existing[idx:]

    with open(VIBE_LOG, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("VIBE_LOG.md updated.")


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set — skipping vibe check.", file=sys.stderr)
        sys.exit(0)

    message, author, files, diff = get_commit_info()

    if not message:
        print("Could not read commit info — skipping.", file=sys.stderr)
        sys.exit(0)

    print(f"Checking vibe on: {message.splitlines()[0][:60]!r}")
    vibe = call_claude(message, author, files, diff)
    print(f"VibeBot says: {vibe}")

    update_vibe_log(message, author, vibe)


if __name__ == "__main__":
    main()

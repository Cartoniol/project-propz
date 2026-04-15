#!/usr/bin/env python3
"""
Auto-regenerate PIPELINES.md from the actual workflow files and scripts.
Runs whenever .github/workflows/* or .github/scripts/* changes.
"""

import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("anthropic package not found. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

WORKFLOWS_DIR = Path(".github/workflows")
SCRIPTS_DIR   = Path(".github/scripts")
PIPELINES_DOC = Path("PIPELINES.md")


def read_dir(directory: Path, glob: str) -> str:
    parts = []
    for f in sorted(directory.glob(glob)):
        ext = f.suffix.lstrip(".")
        parts.append(f"### {f.name}\n\n```{ext}\n{f.read_text(encoding='utf-8')}\n```")
    return "\n\n".join(parts)


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set — skipping PIPELINES.md update.", file=sys.stderr)
        sys.exit(0)

    current_doc = PIPELINES_DOC.read_text(encoding="utf-8") if PIPELINES_DOC.exists() else ""
    workflows   = read_dir(WORKFLOWS_DIR, "*.yml")
    scripts     = read_dir(SCRIPTS_DIR, "*.py")

    client = anthropic.Anthropic(api_key=api_key)

    system = (
        "You are a technical writer maintaining PIPELINES.md for the project-propz repository — "
        "a board game companion PWA with a fully automated GitHub Actions CI/CD showcase.\n\n"
        "Given the actual workflow YAML files and Python scripts, produce a complete, accurate "
        "PIPELINES.md that includes:\n"
        "1. A Mermaid overview diagram of all pipelines and their outputs\n"
        "2. One detailed section per pipeline: trigger, steps, key logic, output artifacts\n"
        "3. A trigger matrix table (all workflows × all event types)\n"
        "4. A secrets reference table\n"
        "5. A loop-prevention strategy section\n\n"
        "Style: match the depth and voice of the existing document — concise, technical, precise.\n"
        "Output ONLY the raw Markdown. No preamble, no explanation."
    )

    user = (
        f"## Current workflow files\n\n{workflows}\n\n"
        f"## Current CI scripts\n\n{scripts}\n\n"
        f"## Existing PIPELINES.md (for style reference)\n\n{current_doc}\n\n"
        "Write the updated PIPELINES.md now."
    )

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    updated = response.content[0].text.strip()
    PIPELINES_DOC.write_text(updated + "\n", encoding="utf-8")
    print("PIPELINES.md regenerated successfully.")


if __name__ == "__main__":
    main()

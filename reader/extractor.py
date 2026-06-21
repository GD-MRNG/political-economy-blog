"""Extraction module for Political Economy Blog briefing posts.

Each public function returns plain dicts so callers have no dependency on
internal regex state. All private symbols are prefixed with _.
"""

from __future__ import annotations

import re
from pathlib import Path

# ── Paths & post-type registry ────────────────────────────────────────────────

POSTS_DIR = Path(__file__).parent.parent / "_posts"

# key → (human label, filename substrings that identify the type)
POST_TYPES: dict[str, tuple[str, list[str]]] = {
    "global":    ("Global Briefing",     ["Global-Briefing"]),
    "singapore": ("Singapore Briefing",  ["Singapore-Briefing"]),
    "tech":      ("Technology Briefing", ["Tech-Briefing", "Technology-Briefing"]),
}

# ── Compiled regex patterns ───────────────────────────────────────────────────

_PREVIEW_RE     = re.compile(r"<!--\s*preview-start\s*-->")
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_REGION_RE      = re.compile(
    r"^#\s+(.+?)\s+<a\s+id=['\"][^'\"]+['\"]></a>",
    re.MULTILINE,
)
_DETAILS_RE     = re.compile(
    r"<details[^>]*>\s*<summary><b>Current Assessment</b></summary>(.*?)</details>",
    re.DOTALL,
)


# ── Public API ────────────────────────────────────────────────────────────────

def get_posts() -> dict[str, list[Path]]:
    """Return {type_key: [Path, ...]} sorted newest-first."""
    posts: dict[str, list[Path]] = {k: [] for k in POST_TYPES}
    for path in POSTS_DIR.glob("*.md"):
        for key, (_, patterns) in POST_TYPES.items():
            if any(p in path.name for p in patterns):
                posts[key].append(path)
                break
    for paths in posts.values():
        paths.sort(key=lambda p: p.name, reverse=True)
    return posts


def extract(filepath: str | Path) -> list[dict[str, str]]:
    """Parse a post and return a list of {"title": str, "text": str} dicts.

    - Global Briefing  → up to 15 entries (Executive Summary + 14 regions)
    - Singapore / Tech → 1 entry (full body text)
    """
    path = Path(filepath)
    content = path.read_text()
    for key, (label, patterns) in POST_TYPES.items():
        if any(p in path.name for p in patterns):
            return _extract_global(content) if key == "global" else _extract_simple(content, label)
    return _extract_simple(content, path.stem)


# ── Private helpers ───────────────────────────────────────────────────────────

def _extract_global(content: str) -> list[dict[str, str]]:
    regions = [
        (m.group(1).strip(), m.start(), m.end())
        for m in _REGION_RE.finditer(content)
    ]
    results: list[dict[str, str]] = []

    # Executive summary: everything between <!-- preview-start --> and first region heading
    preview = _PREVIEW_RE.search(content)
    if preview:
        exec_end = regions[0][1] if regions else len(content)
        text = content[preview.end():exec_end].strip()
        if text:
            results.append({"title": "Executive Summary", "text": text})

    # Each region's Current Assessment details block
    for i, (name, _, end_pos) in enumerate(regions):
        next_pos = regions[i + 1][1] if i + 1 < len(regions) else len(content)
        m = _DETAILS_RE.search(content[end_pos:next_pos])
        if m:
            results.append({"title": name, "text": m.group(1).strip()})

    return results


def _extract_simple(content: str, title: str) -> list[dict[str, str]]:
    preview = _PREVIEW_RE.search(content)
    body = content[preview.end():] if preview else _FRONTMATTER_RE.sub("", content, count=1)
    body = re.split(r"\[←\s*Back to Home\]", body)[0]
    return [{"title": title, "text": body.strip()}]

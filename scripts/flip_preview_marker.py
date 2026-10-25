"""
Put the preview marker after the executive-summary start marker.

    python scripts/flip_preview_marker.py audit
    python scripts/flip_preview_marker.py apply

Only the two comment lines in the header are exchanged. Posts that
have no preview marker are left unchanged.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "_posts"
SCAN = 80
PREVIEW = "<!-- preview-start -->"
START = "<!-- exec-summary-start -->"


def briefing_paths():
    return sorted(POSTS.glob("*Briefing.md"))


def read_post(path):
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")
    return text.splitlines(), newline, text.endswith("\n")


def write_post(path, lines, newline, ends_with_newline):
    text = newline.join(lines)
    if ends_with_newline:
        text += newline
    path.write_bytes(text.encode("utf-8"))


def locate(lines):
    preview_at = None
    start_at = None
    for index, line in enumerate(lines[:SCAN]):
        stripped = line.strip()
        if stripped == PREVIEW and preview_at is None:
            preview_at = index
        elif stripped == START and start_at is None:
            start_at = index
    return preview_at, start_at


def classify(lines):
    preview_at, start_at = locate(lines)
    if start_at is None:
        return "missing-start", None, None
    if preview_at is None:
        return "no-preview", None, None
    if preview_at > start_at:
        return "already", preview_at, start_at
    return "swap", preview_at, start_at


def main(argv):
    if len(argv) != 2 or argv[1] not in ("audit", "apply"):
        print("usage: python scripts/flip_preview_marker.py audit|apply")
        return 2
    apply = argv[1] == "apply"
    counts = {"swap": 0, "already": 0, "no-preview": 0, "missing-start": 0}
    for path in briefing_paths():
        lines, newline, ending = read_post(path)
        status, preview_at, start_at = classify(lines)
        counts[status] += 1
        if status == "swap" and apply:
            lines[preview_at], lines[start_at] = lines[start_at], lines[preview_at]
            write_post(path, lines, newline, ending)
        if status != "already":
            print("%-14s %s" % (status, path.name))
    print(
        "files=%d swap=%d already=%d no-preview=%d missing-start=%d"
        % (
            sum(counts.values()),
            counts["swap"],
            counts["already"],
            counts["no-preview"],
            counts["missing-start"],
        )
    )
    return 1 if counts["missing-start"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

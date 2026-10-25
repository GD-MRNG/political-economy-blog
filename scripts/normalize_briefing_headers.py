"""
Normalize the header of weekly briefing posts.

Modes:
    python scripts/normalize_briefing_headers.py audit
    python scripts/normalize_briefing_headers.py apply
    python scripts/normalize_briefing_headers.py verify

audit prints one line per briefing and writes nothing.
apply removes the deprecated share widget, sets the canonical
executive-summary block, and wraps it in HTML comments.
verify checks that every briefing extracts one summary.
A file audit would skip is not written.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "_posts"

HEADING_SCAN = 250
SECTION_SPAN = 150
CLOSE_SCAN = 300
SHARE_SCAN = 400
FOOTER_PREFIXES = (
    "<br",
    "<details",
    "[← Back to Home]",
    "<hr",
    "<div",
)

START_COMMENT = "<!-- exec-summary-start -->"
END_COMMENT = "<!-- exec-summary-end -->"
PREVIEW_COMMENT = "<!-- preview-start -->"
SHARE_OPEN = '<div style="margin: 16px 0 8px 0;">'

SUMMARY_HEADINGS = (
    "# Executive Summary",
    "## EXECUTIVE SUMMARY",
    "## THE GROUND PICTURE",
)

LEADS = {
    "global": "**The Global Operating Picture**",
    "singapore": "**The Singapore Operating Picture**",
    "technology": "**The Technology Operating Picture**",
}


def briefing_type(path):
    name = path.name
    if name.endswith("-Global-Briefing.md"):
        return "global"
    if name.endswith("-Singapore-Briefing.md"):
        return "singapore"
    if name.endswith("-Tech-Briefing.md") or name.endswith("-Technology-Briefing.md"):
        return "technology"
    return None


def read_post(path):
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")
    ends_with_newline = text.endswith("\n")
    return text.splitlines(), newline, ends_with_newline


def write_post(path, lines, newline, ends_with_newline):
    text = newline.join(lines)
    if ends_with_newline:
        text += newline
    path.write_bytes(text.encode("utf-8"))


def find_share(lines):
    """Return (start, end_exclusive) or None if absent.

    Raises ValueError when copyShareSummary is present but the wrapper
    does not match the known widget.
    """
    window = lines[:SHARE_SCAN]
    function_at = None
    for index, line in enumerate(window):
        if "copyShareSummary" in line:
            function_at = index
            break
    if function_at is None:
        return None

    open_at = None
    for index, line in enumerate(window[: function_at + 1]):
        if line.strip() == SHARE_OPEN:
            open_at = index
            break
    if open_at is None:
        raise ValueError("copyShareSummary present but share wrapper did not match")

    close_at = None
    for index in range(function_at, len(window)):
        if window[index].strip() == "</script>":
            close_at = index
            break
    if close_at is None:
        raise ValueError("copyShareSummary present but share wrapper did not match")

    span = window[open_at : close_at + 1]
    if not any('id="share-payload"' in line for line in span):
        raise ValueError("copyShareSummary present but share wrapper did not match")
    if not any("copyShareSummary" in line for line in span):
        raise ValueError("copyShareSummary present but share wrapper did not match")
    return open_at, close_at + 1


def remove_share(lines):
    span = find_share(lines)
    if span is None:
        return lines, False
    start, end = span
    return lines[:start] + lines[end:], True


def find_heading(lines, ignore=None):
    ignored = set(ignore or ())
    limit = min(len(lines), HEADING_SCAN)
    for index in range(limit):
        if index in ignored:
            continue
        if lines[index].strip() in SUMMARY_HEADINGS:
            return index
    return None


def is_markdown_heading(stripped):
    if not stripped.startswith("#") or stripped.startswith("<!--"):
        return False
    marker = stripped.split(" ", 1)[0]
    if not marker or set(marker) != {"#"} or len(marker) > 6:
        return False
    rest = stripped[len(marker) :]
    return rest.startswith(" ") and bool(rest.strip())


def find_next_heading(lines, heading_index):
    limit = min(len(lines), heading_index + 1 + SECTION_SPAN)
    for index in range(heading_index + 1, limit):
        if is_markdown_heading(lines[index].lstrip()):
            return index
    return None


def find_close_heading(lines, heading_index, kind):
    limit = min(len(lines), heading_index + 1 + CLOSE_SCAN)
    for index in range(heading_index + 1, limit):
        stripped = lines[index].strip()
        if kind == "singapore" and stripped == "## WHAT TO WATCH":
            return index
        if kind == "technology" and stripped.startswith("## WHAT THIS MEANS"):
            return index
    return None


def find_block_end(lines, heading_index, kind):
    """Line index where the delimited block stops, exclusive."""
    if kind == "global":
        return find_next_heading(lines, heading_index)
    close_heading = find_close_heading(lines, heading_index, kind)
    if close_heading is None:
        return None
    limit = min(len(lines), close_heading + 1 + 80)
    for index in range(close_heading + 1, limit):
        stripped = lines[index].strip()
        if not stripped or stripped in (END_COMMENT, START_COMMENT):
            continue
        if is_markdown_heading(stripped) or stripped.startswith(FOOTER_PREFIXES):
            return index
    return None


def section_body(lines, heading_index, next_index, collapse_blanks=False):
    body = []
    blank_run = 0
    for line in lines[heading_index + 1 : next_index]:
        if line.strip() in (END_COMMENT, START_COMMENT):
            continue
        if collapse_blanks and line.strip() == "":
            blank_run += 1
            if blank_run == 1:
                body.append("")
            continue
        blank_run = 0
        body.append(line)
    while body and body[-1].strip() == "":
        body.pop()
    separator = False
    if body and body[-1].strip() == "---":
        separator = True
        body.pop()
        while body and body[-1].strip() == "":
            body.pop()
    while body and body[0].strip() == "":
        body.pop(0)
    return body, separator


def lead_line(body, lead):
    for line in body:
        stripped = line.strip()
        if not stripped or stripped == END_COMMENT:
            continue
        return stripped == lead
    return False


def build_block(body, lead, separator, include_preview=False):
    prose = list(body)
    if prose and prose[0].strip() == lead:
        prose = prose[1:]
        while prose and prose[0].strip() == "":
            prose.pop(0)
    block = [START_COMMENT]
    if include_preview:
        block.extend(["", PREVIEW_COMMENT])
    block.extend([
        "# Executive Summary",
        "",
        lead,
        "",
    ])
    block.extend(prose)
    if prose:
        block.append("")
    block.append(END_COMMENT)
    if separator:
        block.extend(["", "---"])
    return block


def replacement_start(lines, heading_index):
    """Return the splice index and whether a preview marker sits above the heading."""
    start = heading_index
    include_preview = False
    while start > 0 and lines[start - 1].strip() in ("", PREVIEW_COMMENT, START_COMMENT, "---"):
        if lines[start - 1].strip() == PREVIEW_COMMENT:
            include_preview = True
        start -= 1
    return start, include_preview


def analyze(path, lines):
    kind = briefing_type(path)
    if kind is None:
        return {"path": path, "skip": "unknown briefing type"}
    try:
        share = find_share(lines)
    except ValueError as exc:
        return {"path": path, "kind": kind, "skip": str(exc)}

    ignored = range(share[0], share[1]) if share else ()
    heading_index = find_heading(lines, ignored)
    if heading_index is None:
        return {
            "path": path,
            "kind": kind,
            "share": share is not None,
            "skip": "summary heading not found in the first %d lines" % HEADING_SCAN,
        }
    next_index = find_block_end(lines, heading_index, kind)
    if next_index is None:
        return {
            "path": path,
            "kind": kind,
            "share": share is not None,
            "heading": lines[heading_index].strip(),
            "heading_line": heading_index + 1,
            "skip": "closing section not found in the early header",
        }
    body, _separator = section_body(lines, heading_index, next_index, collapse_blanks=kind != "global")
    return {
        "path": path,
        "kind": kind,
        "share": share is not None,
        "heading": lines[heading_index].strip(),
        "heading_line": heading_index + 1,
        "end_line": next_index + 1,
        "end_heading": lines[next_index].strip(),
        "lead_ok": lead_line(body, LEADS[kind]),
        "skip": None,
    }


def transform(lines, kind):
    without_share, _removed = remove_share(lines)
    heading_index = find_heading(without_share)
    next_index = find_block_end(without_share, heading_index, kind)
    body, separator = section_body(
        without_share, heading_index, next_index, collapse_blanks=kind != "global"
    )
    start, include_preview = replacement_start(without_share, heading_index)
    block = build_block(body, LEADS[kind], separator, include_preview=include_preview)
    updated = without_share[:start] + [""] + block + [""] + without_share[next_index:]
    return updated


def audit_line(info):
    path = info["path"].name
    if info.get("skip"):
        kind = info.get("kind") or "-"
        return "SKIP  %-12s %-68s %s" % (kind, info["skip"], path)
    lead = "yes" if info["lead_ok"] else "no"
    return (
        "%-12s share=%-3s heading=%-24s @%-4d ends@%-4d before %-28s lead=%-3s %s"
        % (
            info["kind"],
            "yes" if info["share"] else "no",
            '"%s"' % info["heading"],
            info["heading_line"],
            info["end_line"],
            '"%s"' % info["end_heading"][:28],
            lead,
            path,
        )
    )


def briefing_paths():
    return sorted(path for path in POSTS.glob("*Briefing.md") if briefing_type(path))


def cmd_audit():
    skipped = 0
    for path in briefing_paths():
        lines, _newline, _ending = read_post(path)
        info = analyze(path, lines)
        print(audit_line(info))
        if info.get("skip"):
            skipped += 1
    print("files=%d skipped=%d" % (len(briefing_paths()), skipped))
    return 1 if skipped else 0


def cmd_apply():
    skipped = 0
    written = 0
    unchanged = 0
    for path in briefing_paths():
        lines, newline, ending = read_post(path)
        info = analyze(path, lines)
        if info.get("skip"):
            print(audit_line(info))
            skipped += 1
            continue
        updated = transform(lines, info["kind"])
        if updated == lines:
            unchanged += 1
            continue
        write_post(path, updated, newline, ending)
        written += 1
        print("updated %s" % path.name)
    print("files=%d updated=%d unchanged=%d skipped=%d" % (
        len(briefing_paths()), written, unchanged, skipped
    ))
    return 1 if skipped else 0


def cmd_verify():
    failures = 0
    count = 0
    for path in briefing_paths():
        count += 1
        text_lines, _newline, _ending = read_post(path)
        text = "\n".join(text_lines)
        kind = briefing_type(path)
        lead = LEADS[kind]
        problems = []
        if text.count(START_COMMENT) != 1 or text.count(END_COMMENT) != 1:
            problems.append("comment markers are not a single pair")
        if "copyShareSummary" in text:
            problems.append("share widget remains")
        start = text.find(START_COMMENT)
        end = text.find(END_COMMENT)
        if start != -1 and end != -1 and start < end:
            summary = text[start + len(START_COMMENT) : end].strip("\n")
            body_lines = summary.splitlines()
            while body_lines and body_lines[0].strip() in ("", "---", PREVIEW_COMMENT):
                body_lines.pop(0)
            body = "\n".join(body_lines)
            expected_prefix = "# Executive Summary\n\n" + lead
            if not body.startswith(expected_prefix):
                problems.append("summary does not start with the h1 and lead line")
            if not summary.strip():
                problems.append("summary is empty")
            last_heading = ""
            for line in summary.splitlines():
                stripped = line.strip()
                if is_markdown_heading(stripped):
                    last_heading = stripped
            if kind == "singapore" and last_heading != "## WHAT TO WATCH":
                problems.append("summary does not end at What to Watch")
            if kind == "technology" and not last_heading.startswith("## WHAT THIS MEANS"):
                problems.append("summary does not end at What This Means")
            if "Sources & Intel" in summary:
                problems.append("sources are inside the summary")
        elif not problems:
            problems.append("comment markers are out of order")
        if problems:
            failures += 1
            print("FAIL  %s  %s" % (path.name, "; ".join(problems)))
        else:
            print("ok    %s" % path.name)
    print("files=%d failed=%d" % (count, failures))
    return 1 if failures else 0


def main(argv):
    if len(argv) != 2 or argv[1] not in ("audit", "apply", "verify"):
        print("usage: python scripts/normalize_briefing_headers.py audit|apply|verify")
        return 2
    if not POSTS.is_dir():
        print("posts directory not found: %s" % POSTS)
        return 2
    command = {"audit": cmd_audit, "apply": cmd_apply, "verify": cmd_verify}[argv[1]]
    return command()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

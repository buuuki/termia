"""Markdown editing and visual spans, independent of GTK and persisted metadata."""

from __future__ import annotations

import re


def markdown_edit(content: str, start: int, end: int, action: str) -> tuple[int, int, str]:
    """Return a replacement range and Markdown text using character offsets."""
    heading = action == "heading" or action in {f"heading{level}" for level in range(1, 7)}
    if heading or action in ("bullet", "numbered"):
        start = content.rfind("\n", 0, start) + 1
        limit = end - 1 if end > start and content[end - 1:end] == "\n" else end
        line_end = content.find("\n", limit)
        end = len(content) if line_end < 0 else line_end
        lines = content[start:end].split("\n")
        level = int(action[-1]) if heading and action != "heading" else 1
        replacement = "\n".join(
            ("#" * level + " " + re.sub(r"^ {0,3}#{1,6}[ \t]+", "", line)) if heading
            else (f"{index}. " if action == "numbered" else "- ") + line
            for index, line in enumerate(lines, 1)
        )
    elif action in ("bold", "italic"):
        marker = "**" if action == "bold" else "*"
        replacement = marker + content[start:end] + marker
    elif action == "code":
        before = "\n" if start and content[start - 1] != "\n" else ""
        after = "\n" if end < len(content) and content[end] != "\n" else ""
        fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", content[start:end])), default=0))
        replacement = before + fence + "\n" + content[start:end] + "\n" + fence + after
    else:
        raise ValueError("Unknown Markdown action")
    return start, end, replacement


def markdown_spans(content: str) -> list[tuple[str, int, int]]:
    """Style supported Markdown without rewriting its source; unknown syntax stays visible."""
    spans: list[tuple[str, int, int]] = []
    code_ranges: list[tuple[int, int]] = []
    position = 0
    opening = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n", re.MULTILINE)
    while match := opening.search(content, position):
        fence = match.group(1)
        closing = re.search(
            r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*(?=\n|$)",
            content[match.end():], re.MULTILINE,
        )
        close_start = match.end() + closing.start() if closing else len(content)
        close_end = match.end() + closing.end() if closing else len(content)
        spans.extend((("hide", match.start(), match.end()), ("code", match.end(), close_start)))
        if closing:
            spans.append(("hide", close_start, close_end))
        code_ranges.append((match.start(), close_end))
        position = max(close_end, match.end())

    def outside_code(start: int, end: int) -> bool:
        return all(end <= left or start >= right for left, right in code_ranges)

    for match in re.finditer(r"(`+)([^`\n]+)\1", content):
        if outside_code(*match.span()):
            spans.extend((("hide", match.start(), match.start(2)),
                          ("code", match.start(2), match.end(2)),
                          ("hide", match.end(2), match.end())))
            code_ranges.append(match.span())
    for match in re.finditer(r"^ {0,3}(#{1,6})[ \t]+([^\n]*)", content, re.MULTILINE):
        if outside_code(*match.span()):
            spans.extend((("hide", match.start(), match.start(2)),
                          ("heading" + str(len(match.group(1))), match.start(2), match.end())))
    patterns = {
        "bold": r"(?<!\\)(\*\*|__)(?=\S)(.+?)(?<=\S)\1",
        "italic": r"(?<![\\*\w])([*_])(?![*_])(?=\S)(.+?)(?<=\S)\1(?![*_\w])",
    }
    for style, pattern in patterns.items():
        for match in re.finditer(pattern, content):
            if outside_code(*match.span()):
                spans.extend((("hide", match.start(), match.start(2)),
                              (style, match.start(2), match.end(2)),
                              ("hide", match.end(2), match.end())))
    return spans

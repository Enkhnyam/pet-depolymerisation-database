"""A small markdown renderer for the chunked papers.

The corpus is markdown, and the part that matters most for judging a record is the tables --
reaction conditions live in them. A renderer that drops tables would make the left-hand pane
useless for exactly the records that are hardest to judge, so tables come first here and
everything else is best-effort.

Deliberately not a general markdown implementation: it handles what the parsers actually emit
(ATX headings, pipe tables, lists, paragraphs) and escapes everything else rather than guessing.
"""
import html
import re

TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
DIVIDER = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^\s*[-*]\s+(.*)$")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table(lines: list[str], start: int) -> tuple[str, int]:
    """One pipe table, from `start`, returning the html and the line after it."""
    rows, index = [], start
    while index < len(lines) and TABLE_ROW.match(lines[index]):
        if not DIVIDER.match(lines[index]):
            rows.append(_cells(lines[index]))
        index += 1

    if not rows:
        return "", start + 1

    head, *body = rows
    out = ["<table><thead><tr>"]
    out += [f"<th>{html.escape(cell)}</th>" for cell in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out), index


def render(text: str) -> str:
    """Markdown to html, with pipe tables preserved as real tables."""
    lines = text.splitlines()
    out, index, paragraph, bullets = [], 0, [], []

    def flush() -> None:
        if paragraph:
            out.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
            paragraph.clear()
        if bullets:
            out.append("<ul>" + "".join(f"<li>{html.escape(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    while index < len(lines):
        line = lines[index]

        if TABLE_ROW.match(line):
            flush()
            table, index = _table(lines, index)
            out.append(table)
            continue

        heading = HEADING.match(line)
        if heading:
            flush()
            level = min(len(heading.group(1)) + 2, 6)
            out.append(f"<h{level}>{html.escape(heading.group(2))}</h{level}>")
            index += 1
            continue

        bullet = BULLET.match(line)
        if bullet:
            if paragraph:
                flush()
            bullets.append(bullet.group(1))
            index += 1
            continue

        if not line.strip():
            flush()
        else:
            if bullets:
                flush()
            paragraph.append(line.strip())
        index += 1

    flush()
    return "".join(out)

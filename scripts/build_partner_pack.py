from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple
from xml.sax.saxutils import escape

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
    )
    from reportlab.platypus.tableofcontents import TableOfContents
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "reportlab is required. Install with: pip install reportlab"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "docs" / "partner_pack"
OUT_DIR = ROOT / "artifacts"
OUT_PATH = OUT_DIR / "partner_pack.pdf"


def _iter_markdown_files(folder: Path) -> List[Path]:
    return sorted([p for p in folder.glob("*.md") if p.is_file()])


def _escape_lines(lines: Iterable[str]) -> str:
    return "<br/>".join(escape(line.rstrip("\n")) for line in lines)


def _parse_markdown(md_text: str, styles) -> List:
    story = []
    lines = md_text.splitlines()
    i = 0

    def add_heading(level: int, text: str):
        style = styles[f"H{level}"]
        p = Paragraph(escape(text.strip()), style)
        story.append(p)
        story.append(Spacer(1, 8))

    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_text = _escape_lines(code_lines)
            story.append(Paragraph(code_text, styles["Code"]))
            story.append(Spacer(1, 8))
            i += 1
            continue

        if line.startswith("# "):
            add_heading(1, line[2:])
            i += 1
            continue
        if line.startswith("## "):
            add_heading(2, line[3:])
            i += 1
            continue
        if line.startswith("### "):
            add_heading(3, line[4:])
            i += 1
            continue

        if line.startswith("- ") or line.startswith("* "):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("* ")):
                items.append(lines[i][2:].strip())
                i += 1
            for item in items:
                story.append(Paragraph(escape(item), styles["Bullet"]))
            story.append(Spacer(1, 6))
            continue

        if not line.strip():
            story.append(Spacer(1, 6))
            i += 1
            continue

        story.append(Paragraph(escape(line), styles["Body"]))
        story.append(Spacer(1, 6))
        i += 1

    return story


class _DocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):  # noqa: N802
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            if style_name in ("H1", "H2"):
                level = 0 if style_name == "H1" else 1
                text = flowable.getPlainText()
                self.notify("TOCEntry", (level, text, self.page))


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitlePage", fontSize=28, leading=32, spaceAfter=12))
    styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], spaceAfter=10))
    styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], spaceAfter=8))
    styles.add(ParagraphStyle(name="H3", parent=styles["Heading3"], spaceAfter=6))
    styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], leading=14, spaceAfter=6))
    styles.add(
        ParagraphStyle(
            name="Bullet",
            parent=styles["BodyText"],
            leftIndent=14,
            bulletIndent=6,
            spaceAfter=4,
            bulletFontName="Helvetica",
            bulletFontSize=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Code",
            parent=styles["BodyText"],
            fontName="Courier",
            fontSize=9,
            leading=11,
            backColor="#f2f2f2",
            leftIndent=6,
            rightIndent=6,
            spaceBefore=4,
            spaceAfter=6,
        )
    )
    return styles


def build_pdf() -> None:
    files = _iter_markdown_files(PACK_DIR)
    if not files:
        raise SystemExit(f"No markdown files found in {PACK_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    doc = _DocTemplate(str(OUT_PATH), pagesize=LETTER)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="All", frames=[frame])])

    story = []

    title = "NepXy Partner Pack"
    story.append(Paragraph(title, styles["TitlePage"]))
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d')}", styles["Body"]))
    story.append(PageBreak())

    toc = TableOfContents()
    toc.levelStyles = [styles["Body"], styles["Body"]]
    story.append(Paragraph("Table of Contents", styles["H1"]))
    story.append(toc)
    story.append(PageBreak())

    for path in files:
        md_text = path.read_text(encoding="utf-8")
        story.append(Paragraph(path.stem.replace("_", " ").title(), styles["H1"]))
        story.append(Spacer(1, 6))
        story.extend(_parse_markdown(md_text, styles))
        story.append(PageBreak())

    doc.build(story)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build_pdf()

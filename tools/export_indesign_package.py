"""Export the portfolio as parts, for rebuilding by hand in a page layout app.

The generated PDF is fixed: changing a caption means editing a stylesheet and
reprinting. Sometimes you want to move a picture two picas and be done. InDesign
cannot be written to directly — .indd is closed and undocumented — so this hands
over everything the layout is made of instead, arranged so that rebuilding it is
placement rather than design.

    portfolio_package/
      LAYOUT.md          page-by-page: frames in inches, and what goes in them
      images/p03_1.jpg   every picture, numbered by the page and slot it sits in
      text/p03.txt       the copy for that page, in reading order
      research-map.svg   vector, places straight into InDesign

Geometry is read off the print stylesheet rather than retyped, so the measures
here and the PDF cannot disagree.

    python tools/export_indesign_package.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

sys_path_hack = Path(__file__).parent
import sys

sys.path.insert(0, str(sys_path_hack))

from build_portfolio import (  # noqa: E402
    EMAIL,
    NAME,
    PAGES,
    ROLE,
    SITE,
    bullets,
    credits,
    gallery,
    kicker,
    paragraphs,
    pick,
    read,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "portfolio_package"

# Read off tools/portfolio.css so the sheet and this cannot drift.
CSS = (ROOT / "tools" / "portfolio.css").read_text(encoding="utf-8")


def measure(pattern: str, default: float) -> float:
    found = re.search(pattern, CSS)
    return float(found.group(1)) if found else default


PAGE_W, PAGE_H = 11.0, 8.5
PAD_TOP = measure(r"\.page \{[^}]*padding:\s*([\d.]+)in", 0.62)
PAD_SIDE = measure(r"\.page \{[^}]*padding:\s*[\d.]+in\s+([\d.]+)in", 0.7)
PAD_BOTTOM = measure(r"\.page \{[^}]*padding:\s*[\d.]+in\s+[\d.]+in\s+([\d.]+)in", 0.55)
PROSE_W = measure(r"grid-template-columns:\s*([\d.]+)in", 3.05)
SPLIT_GAP = measure(r"\.split \{[^}]*gap:\s*([\d.]+)in", 0.36)
FIG_GAP = measure(r"\.figs \{[^}]*gap:\s*([\d.]+)in", 0.13)


def page_kind(spec: dict) -> str:
    return spec["kind"]


def page_images(spec: dict) -> list[tuple[str, str]]:
    kind = spec["kind"]
    if kind == "paper":
        return pick(read(spec["slug"]), spec["shots"], by_figure=True)
    if kind == "course":
        meta = read(spec["slug"])
        skip = spec["shots"] if spec.get("part") == 2 else 0
        return pick(meta, spec["shots"], skip=skip)
    if kind == "design":
        out: list[tuple[str, str]] = []
        for slug in spec["slugs"]:
            out += pick(read(slug), spec["shots"])
        return out
    if kind == "papers-three":
        return [pick(read(slug), 1, by_figure=True)[0] for slug in spec["slugs"]]
    if kind == "cover":
        return [
            ("assets/site_images/index/research/01.jpg", ""),
            ("assets/site_images/index/research/04.jpg", ""),
            ("assets/site_images/index/teaching/02.jpg", ""),
            ("assets/site_images/index/design/01.jpg", ""),
            ("assets/site_images/index/design/06.jpg", ""),
        ]
    if kind == "map":
        return [("assets/site_images/research-map.svg", "")]
    return []


def page_text(spec: dict) -> str:
    kind = spec["kind"]
    lines: list[str] = []

    if kind == "cover":
        lines += [NAME, "", ROLE, "", "PORTFOLIO / RESEARCH, TEACHING, DESIGN", "", f"{EMAIL} / {SITE}"]
    elif kind == "map":
        lines += ["Research", "", "Place research-map.svg full page. It carries its own type."]
    elif kind in {"paper", "course"}:
        meta = read(spec["slug"])
        if spec.get("part") == 2:
            lines += [f"{kicker(meta)} / STUDENT WORK", "", meta.get("title", ""), meta.get("subtitle", "")]
        else:
            lines += [kicker(meta), "", meta.get("title", "")]
            if meta.get("subtitle"):
                lines.append(meta["subtitle"])
            if meta.get("authors"):
                lines += ["", meta["authors"].replace(" | ", "  /  ")]
            lines += ["", meta.get("summary", "")]
            overview = paragraphs(meta, "Overview")
            if overview:
                lines += ["", overview[0]]
            focus = bullets(meta, "Focus")
            if focus:
                lines += ["", "FOCUS"] + [f"- {f}" for f in focus[:6]]
            role = paragraphs(meta, "Role")
            if role:
                lines += ["", "ROLE", role[0]]
    elif kind == "papers-three":
        for slug in spec["slugs"]:
            meta = read(slug)
            lines += [meta.get("year", ""), meta.get("title", ""), meta.get("authors", ""), meta.get("summary", ""), ""]
        text = (ROOT / "content" / "projects" / "publications.md").read_text(encoding="utf-8")
        body = text.split("---", 2)[2] if text.startswith("---") else text
        refs = [r.strip() for r in body.splitlines() if r.strip()]
        lines += ["PEER-REVIEWED PUBLICATIONS"] + [f"{i}. {r}" for i, r in enumerate(refs, 1)]
    elif kind == "teaching-overview":
        lines += ["Teaching", ""]
        for slug in ("arch-2017", "arch-6020", "arch-8833", "arch-2020"):
            meta = read(slug)
            role = paragraphs(meta, "Role")
            lines += [
                f"{meta.get('title','')} — {meta.get('subtitle','')}",
                f"  term: {meta.get('year','')}",
                f"  content: {meta.get('summary','')}",
                f"  role: {role[0] if role else ''}",
                "",
            ]
    elif kind == "design":
        for slug in spec["slugs"]:
            meta = read(slug)
            role = paragraphs(meta, "Role")
            lines += [kicker(meta), meta.get("title", ""), "", meta.get("summary", "")]
            if role:
                lines += ["", role[0]]
            lines.append("")
    elif kind == "cv":
        meta = read("cv")
        lines += ["Curriculum vitae", "Abridged. The full CV is submitted as a separate document.", ""]
        for name in ("Education", "Experience", "Academic Service", "Awards", "Methods and Tools"):
            rows = bullets(meta, name)
            if rows:
                lines += [name.upper()] + [f"- {r}" for r in rows] + [""]
    elif kind == "closing":
        about = read("about")
        lines += [NAME, "", about.get("summary", ""), "", EMAIL, SITE]

    return "\n".join(lines).strip() + "\n"


LAYOUT_HEAD = f"""# Portfolio layout

Twenty pages, US Letter landscape, {PAGE_W:g} x {PAGE_H:g} in.

## Document setup

| | |
|---|---|
| Page size | {PAGE_W:g} in x {PAGE_H:g} in, landscape |
| Pages | 20, single (not facing) |
| Margins | top {PAD_TOP:g} in, outside {PAD_SIDE:g} in, bottom {PAD_BOTTOM:g} in |
| Live area | {PAGE_W - 2 * PAD_SIDE:.2f} in x {PAGE_H - PAD_TOP - PAD_BOTTOM:.2f} in |
| Body font | Helvetica Neue, or Arial |

## The two-column page

Most pages run text down a fixed left column and pictures in the space that is
left. Both columns start at the top margin and run to the bottom one.

| Frame | x | width |
|---|---|---|
| Text | {PAD_SIDE:g} in | {PROSE_W:g} in |
| Pictures | {PAD_SIDE + PROSE_W + SPLIT_GAP:.2f} in | {PAGE_W - PAD_SIDE - (PAD_SIDE + PROSE_W + SPLIT_GAP):.2f} in |

Gutter between them {SPLIT_GAP:g} in. Gutter inside a picture grid {FIG_GAP:g} in,
both ways. Picture rows divide the height evenly, whatever the count.

## Type

| Role | Size | Leading | Colour |
|---|---|---|---|
| Page title | 20 pt bold | 1.12 | #151515 |
| Kicker above it | 9.5 pt, caps, tracked 40 | | #6B6B6B |
| Standfirst | 11.5 pt | 1.40 | #151515 |
| Body | 10 pt | 1.44 | #151515 |
| Focus list | 9.5 pt, two columns | 1.30 | #444444 |
| Credits and role | 9.5 pt | | #6B6B6B |
| Picture caption | 7.5 pt | 1.25 | #6B6B6B |

## Placing pictures

A photograph or a render fills its frame and crops. A conference slide or an A4
spread is placed whole inside the frame, on #FBFBFB with a 1 pt #ECECEC rule:
cropping one cuts a heading in half. Each page below says which it is.

## Pages
"""


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "images").mkdir(parents=True)
    (OUT / "text").mkdir(parents=True)

    notes = [LAYOUT_HEAD]
    for number, spec in enumerate(PAGES, 1):
        tag = f"p{number:02d}"
        (OUT / "text" / f"{tag}.txt").write_text(page_text(spec), encoding="utf-8")

        shots = page_images(spec)
        placed = []
        for slot, (src, caption) in enumerate(shots, 1):
            source = ROOT / src
            if not source.exists():
                continue
            target = OUT / "images" / f"{tag}_{slot}{source.suffix}"
            shutil.copy2(source, target)
            placed.append((target.name, caption))

        whole = spec["kind"] in {"paper"} or spec["kind"] == "design" and set(spec["slugs"]) & {"craftman", "street"}
        notes.append(f"\n### Page {number} — {page_kind(spec)}\n")
        notes.append(f"Text: `text/{tag}.txt`\n")
        if placed:
            notes.append(f"Pictures: {len(placed)}, {'placed whole' if whole else 'filling the frame'}\n")
            for name, caption in placed:
                notes.append(f"- `images/{name}`" + (f" — caption: {caption}" if caption else ""))
            notes.append("")

    (OUT / "LAYOUT.md").write_text("\n".join(notes), encoding="utf-8")
    shutil.copy2(ROOT / "assets" / "site_images" / "research-map.svg", OUT / "research-map.svg")

    count = len(list((OUT / "images").iterdir()))
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"  {OUT.name}/  {count} images, 20 text files, {size:.0f} MB")


if __name__ == "__main__":
    main()

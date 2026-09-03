"""Assemble the twenty-page application portfolio from the site's own content.

Faculty postings cap the portfolio — the one this is sized to says "maximum 20
letter sized pages" — and ask for the statements as separate documents. So this
book carries the work, not the argument: titles, a line of context, and
pictures. The reader has the research statement and the papers elsewhere.

It is built from content/projects/*.md and assets/site_images, the same sources
the website reads. That is the point: a student sends new images, the site and
the book both pick them up, and the two never drift into saying different
things about the same project.

Page order puts research first, which is the reverse of the website. The site
opens to whoever arrives; this opens to a search committee reading forty of
these, and for a tenure-track file the publication record is what carries.

    python tools/build_portfolio.py          # write portfolio.html
    python tools/build_portfolio.py --pdf    # and print it through headless Chrome
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
HTML_OUT = ROOT / "portfolio.html"
PDF_OUT = ROOT / "Yichao_Shi_Portfolio.pdf"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
SERVED = "http://127.0.0.1:5500/portfolio.html"

NAME = "Yichao Shi"
ROLE = "Instructor and PhD candidate, School of Architecture, Georgia Institute of Technology"
EMAIL = "yichao.shi@gatech.edu"
SITE = "yichaoshi.com"

# Twenty pages. Research leads and takes six; teaching takes six, with two on
# the design studio because that is the teaching a studio-based school hires
# for; design takes four and sits last, since it is pre-doctoral student work
# and reads as background rather than as practice.
PAGES: list[dict] = [
    {"kind": "cover"},
    {"kind": "map"},
    {"kind": "paper", "slug": "dcc-2026", "shots": 4},
    {"kind": "paper", "slug": "caadria-2026", "shots": 4},
    {"kind": "paper", "slug": "simaud-2026", "shots": 4},
    {"kind": "paper", "slug": "acadia-2022", "shots": 5},
    {"kind": "paper", "slug": "dcc-2024", "shots": 4},
    {"kind": "papers-three", "slugs": ["caadria-2025-1", "caadria-2025-2", "simaud-2023"]},
    {"kind": "teaching-overview"},
    {"kind": "course", "slug": "arch-2017", "shots": 5, "part": 1},
    {"kind": "course", "slug": "arch-2017", "shots": 6, "part": 2},
    {"kind": "course", "slug": "arch-6020", "shots": 6},
    {"kind": "course", "slug": "arch-8833", "shots": 6},
    {"kind": "course", "slug": "arch-2020", "shots": 6},
    {"kind": "design", "slugs": ["loops"], "shots": 5},
    {"kind": "design", "slugs": ["stadium", "street"], "shots": 3},
    {"kind": "design", "slugs": ["mars", "robotics"], "shots": 3},
    {"kind": "design", "slugs": ["craftman"], "shots": 4},
    {"kind": "cv"},
    {"kind": "closing"},
]


# ---------------------------------------------------------------- content ---

def read(slug: str) -> dict:
    text = (ROOT / "content" / "projects" / f"{slug}.md").read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        end = text.index("\n---", 3)
        for line in text[3:end].strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        body = text[end + 4 :].strip()

    sections: dict[str, list[str]] = {}
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current and line.strip():
            sections[current].append(line.strip())
    meta["_sections"] = sections  # type: ignore[assignment]
    return meta


def paragraphs(meta: dict, section: str) -> list[str]:
    return [row for row in meta["_sections"].get(section, []) if not row.startswith("- ")]


def bullets(meta: dict, section: str) -> list[str]:
    return [row[2:] for row in meta["_sections"].get(section, []) if row.startswith("- ")]


def gallery(meta: dict) -> list[str]:
    raw = meta.get("gallery") or meta.get("gallery_full") or ""
    return [i.strip() for i in raw.split("|") if i.strip()]


def credits(meta: dict) -> list[str]:
    raw = meta.get("gallery_credits", "")
    return [c.strip() for c in raw.split("|")] if raw else []


# ------------------------------------------------------------------ picks ---

def figure_score(path: Path) -> float:
    """Lower is more like a figure and less like a slide.

    Research folders are conference decks: mostly white, mostly type. Ranking on
    ink coverage against colour finds the frames that are a drawing or a render,
    which are the ones worth a page.
    """
    image = Image.open(path)
    image.thumbnail((160, 160))
    grey = list(image.convert("L").getdata())
    white = sum(1 for v in grey if v > 235) / len(grey)
    colour = sum(ImageStat.Stat(image.convert("RGB")).stddev) / 3
    return white - colour / 120


def pick(meta: dict, count: int, skip: int = 0, by_figure: bool = False) -> list[tuple[str, str]]:
    """Return (src, caption) pairs. Captions name a student where one is credited."""
    images = gallery(meta)
    names = credits(meta)
    label = meta.get("credit_label", "")
    pairs = [
        (src, f"{label} {names[i]}".strip() if i < len(names) and names[i] else "")
        for i, src in enumerate(images)
    ]
    if by_figure:
        pairs.sort(key=lambda pair: figure_score(ROOT / pair[0]))
    return pairs[skip : skip + count]


# ------------------------------------------------------------------- html ---

def esc(text: str) -> str:
    return html.escape(text, quote=False)


def inline(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)  # links carry nothing in print
    return re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)


def figures(pairs: list[tuple[str, str]], columns: int) -> str:
    """Lay pictures out, cropped or whole depending on what they are.

    A photograph or a render survives a crop: it is composed around its middle
    and its frame is arbitrary. A conference slide or an A4 spread does not —
    cropping one cuts a heading in half, and the picture reads as a fragment of
    a document rather than as a figure. A grid whose pictures are mostly wider
    than four to three is therefore shown whole, letterboxed; the rest crop.
    """
    wide = 0
    for src, _caption in pairs:
        try:
            width, height = Image.open(ROOT / src).size
            wide += width / height > 1.25
        except Exception:
            pass
    whole = " whole" if pairs and wide > len(pairs) / 2 else ""

    cells = []
    for src, caption in pairs:
        note = f"<figcaption>{esc(caption)}</figcaption>" if caption else ""
        cells.append(f'<figure><img src="{src}" alt="" />{note}</figure>')
    return f'<div class="figs cols-{columns}{whole}">{"".join(cells)}</div>'


def kicker(meta: dict) -> str:
    parts = [meta.get("year", ""), meta.get("type", "")]
    return " / ".join(p for p in parts if p)


def page_cover() -> str:
    strip = [
        "assets/site_images/index/research/01.jpg",
        "assets/site_images/index/research/04.jpg",
        "assets/site_images/index/teaching/02.jpg",
        "assets/site_images/index/design/01.jpg",
        "assets/site_images/index/design/06.jpg",
    ]
    tiles = "".join(f'<img src="{s}" alt="" />' for s in strip)
    return f"""<section class="page cover">
  <div class="cover-type">
    <h1>{NAME}</h1>
    <p class="cover-role">{esc(ROLE)}</p>
    <p class="cover-kind">Portfolio &#183; research, teaching, design</p>
  </div>
  <div class="cover-strip">{tiles}</div>
  <p class="cover-foot">{EMAIL} &#183; {SITE}</p>
</section>"""


def page_map() -> str:
    return """<section class="page map">
  <img src="assets/site_images/research-map.svg" alt="Research map" />
</section>"""


def page_paper(slug: str, shots: int) -> str:
    meta = read(slug)
    overview = paragraphs(meta, "Overview")
    focus = bullets(meta, "Focus")
    pairs = pick(meta, shots, by_figure=True)
    role = paragraphs(meta, "Role")
    return f"""<section class="page">
  <header class="head">
    <p class="kicker">{esc(kicker(meta))}</p>
    <h2>{inline(meta.get('title', ''))}</h2>
    <p class="authors">{inline(meta.get('authors', ''))}</p>
  </header>
  <div class="split">
    <div class="prose">
      <p class="lede">{inline(meta.get('summary', ''))}</p>
      {"".join(f"<p>{inline(p)}</p>" for p in overview[:1])}
      {"<p class='role'>" + inline(role[0]) + "</p>" if role else ""}
      {"<ul class='focus'>" + "".join(f"<li>{esc(f)}</li>" for f in focus[:6]) + "</ul>" if focus else ""}
    </div>
    {figures(pairs, 2)}
  </div>
</section>"""


def page_papers_three(slugs: list[str]) -> str:
    columns = []
    for slug in slugs:
        meta = read(slug)
        pairs = pick(meta, 1, by_figure=True)
        shot = f'<img src="{pairs[0][0]}" alt="" />' if pairs else ""
        columns.append(
            f"""<div class="third">
      {shot}
      <p class="kicker">{esc(meta.get('year',''))}</p>
      <h3>{inline(meta.get('title',''))}</h3>
      <p class="authors">{inline(meta.get('authors',''))}</p>
      <p>{inline(meta.get('summary',''))}</p>
    </div>"""
        )
    # publications.md is a run of paragraphs, one reference each, with no
    # headings and no list markers — reading it as a section of bullets
    # returned nothing and printed an empty list.
    text = (ROOT / "content" / "projects" / "publications.md").read_text(encoding="utf-8")
    body = text.split("---", 2)[2] if text.startswith("---") else text
    rows = [r.strip() for r in body.splitlines() if r.strip() and not r.startswith("#")]
    items = "".join(f"<li>{inline(r)}</li>" for r in rows)
    return f"""<section class="page">
  <header class="head"><h2>Further research</h2></header>
  <div class="thirds">{"".join(columns)}</div>
  <div class="pubs">
    <h4>Peer-reviewed publications</h4>
    <ol>{items}</ol>
  </div>
</section>"""


def page_teaching_overview() -> str:
    rows = []
    for slug in ("arch-2017", "arch-6020", "arch-8833", "arch-2020"):
        meta = read(slug)
        role = paragraphs(meta, "Role")
        rows.append(
            f"""<tr>
      <td class="course">{inline(meta.get('title',''))}<span>{inline(meta.get('subtitle',''))}</span></td>
      <td>{esc(meta.get('year',''))}</td>
      <td>{inline(meta.get('summary',''))}</td>
      <td class="role-cell">{inline(role[0]) if role else ''}</td>
    </tr>"""
        )
    return f"""<section class="page">
  <header class="head">
    <h2>Teaching</h2>
    <p class="lede">Four courses at Georgia Tech as a graduate student instructor, from the
    undergraduate computational design sequence to a graduate seminar on AI in design, and one
    section of the undergraduate design studio.</p>
  </header>
  <table class="courses">
    <thead><tr><th>Course</th><th>Term</th><th>Content</th><th>Role</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>"""


def page_course(slug: str, shots: int, part: int = 0) -> str:
    meta = read(slug)
    skip = shots if part == 2 else 0
    pairs = pick(meta, shots, skip=skip)
    overview = paragraphs(meta, "Overview")
    focus = bullets(meta, "Focus")
    role = paragraphs(meta, "Role")
    if part == 2:
        return f"""<section class="page">
  <header class="head thin">
    <p class="kicker">{esc(kicker(meta))} &#183; student work</p>
    <h2>{inline(meta.get('title',''))} <span class="sub">{inline(meta.get('subtitle',''))}</span></h2>
  </header>
  {figures(pairs, 3)}
</section>"""
    return f"""<section class="page">
  <header class="head">
    <p class="kicker">{esc(kicker(meta))}</p>
    <h2>{inline(meta.get('title',''))} <span class="sub">{inline(meta.get('subtitle',''))}</span></h2>
  </header>
  <div class="split">
    <div class="prose">
      <p class="lede">{inline(meta.get('summary',''))}</p>
      {"".join(f"<p>{inline(p)}</p>" for p in overview[:1])}
      {"<ul class='focus'>" + "".join(f"<li>{esc(f)}</li>" for f in focus[:6]) + "</ul>" if focus else ""}
      {"<p class='role'>" + inline(role[0]) + "</p>" if role else ""}
    </div>
    {figures(pairs, 2)}
  </div>
</section>"""


def page_design(slugs: list[str], shots: int) -> str:
    blocks = []
    for slug in slugs:
        meta = read(slug)
        pairs = pick(meta, shots)
        role = paragraphs(meta, "Role")
        blocks.append(
            f"""<div class="design-block">
      <header class="head thin">
        <p class="kicker">{esc(kicker(meta))}</p>
        <h3>{inline(meta.get('title',''))}</h3>
      </header>
      <p class="lede">{inline(meta.get('summary',''))}</p>
      {"<p class='role'>" + inline(role[0]) + "</p>" if role else ""}
      {figures(pairs, shots if shots <= 3 else 3)}
    </div>"""
        )
    return f'<section class="page design-page">{"".join(blocks)}</section>'


def page_cv() -> str:
    meta = read("cv")
    wanted = ("Education", "Experience", "Academic Service", "Awards", "Methods and Tools")
    blocks = []
    for name in wanted:
        rows = bullets(meta, name)
        if not rows:
            continue
        blocks.append(
            f'<div class="cv-block"><h4>{name}</h4><ul>'
            + "".join(f"<li>{inline(r)}</li>" for r in rows)
            + "</ul></div>"
        )
    return f"""<section class="page">
  <header class="head"><h2>Curriculum vitae</h2>
  <p class="lede">Abridged. The full CV is submitted as a separate document.</p></header>
  <div class="cv">{"".join(blocks)}</div>
</section>"""


def page_closing() -> str:
    about = read("about")
    return f"""<section class="page closing">
  <div class="closing-type">
    <h2>{NAME}</h2>
    <p class="lede">{inline(about.get('summary',''))}</p>
    <p class="closing-contact">{EMAIL}<br />{SITE}</p>
  </div>
</section>"""


BUILDERS = {
    "cover": lambda spec: page_cover(),
    "map": lambda spec: page_map(),
    "paper": lambda spec: page_paper(spec["slug"], spec["shots"]),
    "papers-three": lambda spec: page_papers_three(spec["slugs"]),
    "teaching-overview": lambda spec: page_teaching_overview(),
    "course": lambda spec: page_course(spec["slug"], spec["shots"], spec.get("part", 0)),
    "design": lambda spec: page_design(spec["slugs"], spec["shots"]),
    "cv": lambda spec: page_cv(),
    "closing": lambda spec: page_closing(),
}

STYLE = (ROOT / "tools" / "portfolio.css").read_text(encoding="utf-8")


def build() -> str:
    pages = [BUILDERS[spec["kind"]](spec) for spec in PAGES]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{NAME} &#183; Portfolio</title>
<style>{STYLE}</style>
</head>
<body>
{"".join(pages)}
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="store_true", help="Print the page through headless Chrome.")
    args = parser.parse_args()

    HTML_OUT.write_text(build(), encoding="utf-8")
    print(f"  {HTML_OUT.name}  {len(PAGES)} pages  {HTML_OUT.stat().st_size / 1024:.0f} KB")

    if not args.pdf:
        return
    if not CHROME.exists():
        sys.exit(f"chrome not found at {CHROME}")
    subprocess.run(
        [
            str(CHROME),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={PDF_OUT}",
            "--virtual-time-budget=20000",
            SERVED,
        ],
        check=True,
        capture_output=True,
    )
    print(f"  {PDF_OUT.name}  {PDF_OUT.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()

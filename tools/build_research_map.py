"""Draw the research map: one page that says what the work is and how it adds up.

A committee reads a portfolio in a stack of forty. The first spread decides
which frame they read the next nineteen pages in, so it has to answer "who is
this" before any single project does.

The map is the positioning sentence turned into a picture. Its three lanes are
the sentence's own verbs — represent, learn, evaluate — and its horizontal axis
is time, so one drawing carries the through-line and the rate of work. Papers
sit in the lane their contribution lands in, which is not always the one their
title suggests: the CAD inference work reads as learning, and what it returns
is a grammar.

LOOPS is not on the chart. It is robotic fabrication from the MArch, two years
before the grammar work, and giving it a lane would claim a continuity that is
not there. It goes underneath as a note, which says something truer: this
started in physical making.

Lanes are sized to the papers they hold rather than evenly, because two of them
carry a pair in the same year and one does not. Output is SVG: sharp at any
page size, and restyled by editing text rather than re-exporting.

    python tools/build_research_map.py
"""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "site_images" / "research-map.svg"

# Letter landscape.
W, H = 1100, 850
LEFT, RIGHT = 250, 1046

YEARS = (2023, 2024, 2025, 2026)
# (name, gloss, height). Height follows the load: a lane holding two papers in
# one year needs room to stack them, a lane holding one does not.
LANES = (
    ("REPRESENT", "making design knowledge explicit as rules", 150),
    ("LEARN", "recovering and generating it by machine", 205),
    ("EVALUATE", "testing what a system produces against it", 205),
)
LANE_TOP = 208

PAPERS = (
    (2023, 1, "ANNSIM 2023", ("Conditional shape embedding", "with GAN"), "fire-code checking"),
    (2024, 0, "DCC 2024", ("Dougong revisited",), "parametric grammar"),
    (2025, 1, "CAADRIA 2025", ("Concept to consistent", "multi-view renders"), "grammar + diffusion"),
    (2025, 1, "CAADRIA 2025", ("Reimagining Chinese", "garden design"), "interactive generation"),
    (2026, 0, "DCC 2026", ("Grammar inference", "from CAD drawings"), "rules recovered from data"),
    (2026, 2, "CAADRIA 2026", ("Benchmarking pix2pix", "on floor plans"), "grammar as ground truth"),
    (2026, 2, "ANNSIM 2026", ("Rule-level reasoning for", "performance-aware plans"), "daylight + explainability"),
)
# Two papers encode a traditional Chinese system rather than a generic one.
CULTURAL = {"Dougong revisited", "Reimagining Chinese"}

INK, MUTED, LINE, FAINT = "#151515", "#6b6b6b", "#d8d8d8", "#efefef"


def lane_bounds(index: int) -> tuple[float, float]:
    top = LANE_TOP + sum(h for _n, _g, h in LANES[:index])
    return top, top + LANES[index][2]


def year_x(year: int) -> float:
    step = (RIGHT - LEFT) / len(YEARS)
    return LEFT + step * (YEARS.index(year) + 0.5)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def build() -> str:
    out: list[str] = []
    add = out.append
    bottom = lane_bounds(len(LANES) - 1)[1]

    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    add('<rect width="100%" height="100%" fill="#ffffff"/>')
    add('<g font-family="Helvetica Neue, Helvetica, Arial, sans-serif">')

    add(f'<text x="60" y="88" font-size="27" font-weight="700" fill="{INK}">Research</text>')
    for offset, row in enumerate(
        (
            "How computational systems represent, learn, and evaluate architectural design",
            "knowledge, with shape grammar as the formal ground.",
        )
    ):
        add(f'<text x="60" y="{124 + offset * 23}" font-size="15.5" fill="{MUTED}">{esc(row)}</text>')

    # Year scale across the top, so nothing at the foot of the last lane
    # collides with it.
    for year in YEARS:
        x = year_x(year)
        add(f'<text x="{x:.0f}" y="182" font-size="12.5" fill="{MUTED}" text-anchor="middle">{year}</text>')
        add(f'<line x1="{x:.0f}" y1="{LANE_TOP:.0f}" x2="{x:.0f}" y2="{bottom:.0f}" stroke="{FAINT}" stroke-width="1"/>')

    # Lanes: a rule at the top of each, the label sitting in its own column.
    for index, (name, gloss, _height) in enumerate(LANES):
        top, low = lane_bounds(index)
        middle = (top + low) / 2
        add(f'<line x1="60" y1="{top:.0f}" x2="{RIGHT}" y2="{top:.0f}" stroke="{LINE}" stroke-width="1"/>')
        add(f'<text x="60" y="{middle - 6:.0f}" font-size="13" font-weight="700" letter-spacing="1.4" fill="{INK}">{name}</text>')
        add(f'<text x="60" y="{middle + 14:.0f}" font-size="11.5" fill="{MUTED}">{esc(gloss)}</text>')
    add(f'<line x1="60" y1="{bottom:.0f}" x2="{RIGHT}" y2="{bottom:.0f}" stroke="{LINE}" stroke-width="1"/>')

    for year, lane, venue, title, note in PAPERS:
        top, low = lane_bounds(lane)
        together = [p for p in PAPERS if p[0] == year and p[1] == lane]
        seat = together.index((year, lane, venue, title, note))
        y = (top + low) / 2 + (seat - (len(together) - 1) / 2) * 96
        x = year_x(year)

        add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="5" fill="{INK}"/>')
        if title[0] in CULTURAL:
            add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="12" fill="none" stroke="{INK}" stroke-width="1" stroke-dasharray="2 3"/>')
        add(f'<text x="{x:.0f}" y="{y - 24:.0f}" font-size="11.5" font-weight="700" fill="{INK}" text-anchor="middle">{venue}</text>')
        for offset, row in enumerate(title):
            add(f'<text x="{x:.0f}" y="{y + 26 + offset * 15:.0f}" font-size="12" fill="{INK}" text-anchor="middle">{esc(row)}</text>')
        add(
            f'<text x="{x:.0f}" y="{y + 28 + len(title) * 15:.0f}" font-size="10.5" fill="{MUTED}" '
            f'text-anchor="middle">{esc(note)}</text>'
        )

    # Foot: the ring key, LOOPS, and the count.
    add(f'<circle cx="66" cy="{bottom + 40:.0f}" r="6" fill="none" stroke="{INK}" stroke-width="1" stroke-dasharray="2 3"/>')
    add(f'<text x="82" y="{bottom + 44:.0f}" font-size="11" fill="{MUTED}">encodes a traditional Chinese design system</text>')
    add(
        f'<text x="60" y="{bottom + 74:.0f}" font-size="11" fill="{MUTED}">'
        "Before this line of work: ACADIA 2022, LOOPS &#8212; elastic robotic structures, built and tested at full scale (MArch, UCL)."
        "</text>"
    )
    add(
        f'<text x="{RIGHT}" y="{bottom + 44:.0f}" font-size="11" fill="{MUTED}" text-anchor="end">'
        "Yichao Shi &#183; eight peer-reviewed papers, 2022&#8211;2026"
        "</text>"
    )

    add("</g></svg>")
    return "\n".join(out)


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"  {OUT.relative_to(ROOT)}  {OUT.stat().st_size / 1024:.0f} KB")

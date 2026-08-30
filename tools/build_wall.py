"""Cut the homepage wall's three sections from the project libraries.

The wall is three sections — teaching, research, design — of six square tiles.
A tile is cut from an image that already lives on a project page, so nothing new
has to be exported by hand and a tile always links to work that is actually there.

Two things this does that a plain centre crop does not:

  Colour is read through export_web_images.load(), so CMYK and Display P3 sources
  keep their colour. A plain convert("RGB") drops the red channel on those and the
  wall goes green.

  The square window is placed where the ink is, not in the middle. Research folders
  hold conference slides, which are mostly white margin; a centred crop of one is a
  blank tile.

    python tools/build_wall.py            # write the tiles
    python tools/build_wall.py --preview  # contact sheet only, write nothing
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))

from export_web_images import load  # colour-managed read

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "site_images" / "index"
TILE = 1000

# (section, project slug, source image, alt text). Six per section: two rows of
# three. The design row reuses the picks already cut for the old single wall,
# one per project, so those tiles are unchanged.
PICKS = {
    "teaching": [
        ("arch-2017", "teaching/arch-2017/10.jpg", "ARCH 2017 studio work"),
        ("arch-6020", "teaching/arch-6020/10.jpg", "ARCH 6020 student work"),
        ("arch-8833", "teaching/arch-8833/10.jpg", "ARCH 8833 student work"),
        ("arch-2020", "teaching/arch-2020/06.jpg", "ARCH 2020 student work"),
        ("arch-2017", "teaching/arch-2017/03.jpg", "ARCH 2017 studio drawing"),
        ("arch-6020", "teaching/arch-6020/03.jpg", "ARCH 6020 student model"),
    ],
    "research": [
        ("acadia-2022", "research/acadia-2022/grid/02.jpg", "Elastic robotic structure prototype"),
        ("caadria-2026", "research/caadria-2026/full/06.jpg", "Floor-plan benchmarking"),
        ("caadria-2025-2", "research/caadria-2025-2/full/02.jpg", "Chinese garden design study"),
        ("dcc-2026", "research/dcc-2026/full/07.jpg", "Shape grammar inference from CAD"),
        ("caadria-2025-1", "research/caadria-2025-1/full/07.jpg", "Shape grammar to rendered views"),
        ("simaud-2026", "research/simaud-2026/full/07.jpg", "Performance-aware floor-plan generation"),
    ],
    "design": [
        ("loops", "index/01.jpg", "LOOPS six-unit aggregation study"),
        ("stadium", "index/02.jpg", "Stadium Design for a University axonometric"),
        ("craftman", "index/03.jpg", "Porcelain Handicraft Workshop exterior view"),
        ("mars", "index/04.jpg", "Conquer the Mars megastructure interior"),
        ("street", "index/05.jpg", "School Gate Street Reconstruction street view"),
        ("robotics", "index/06.jpg", "Overnight House robotic arm inside an inflatable dome"),
    ],
}


def looks_like_a_slide(image: Image.Image) -> bool:
    """True for a presentation frame: wide, and mostly paper."""
    if image.width < image.height * 1.2:
        return False
    small = image.convert("L").resize((160, 90))
    grey = list(small.getdata())
    return sum(1 for v in grey if v > 235) / len(grey) > 0.5


def ink_window(image: Image.Image) -> Image.Image:
    """Crop square where the image carries its content.

    A slide is mostly margin, so the centre of the frame is often empty. Scoring
    columns (or rows) by how many pixels are not near-white and taking the densest
    run of them lands the window on the diagram instead.

    A full-height window on a slide always swallows the title band above the
    figure and the footer below it, and the tile then reads as a screenshot of
    half a sentence. Dropping those bands first leaves the figure alone.
    """
    if looks_like_a_slide(image):
        top = round(image.height * 0.19)
        bottom = round(image.height * 0.89)
        image = image.crop((0, top, image.width, bottom))

    width, height = image.size
    side = min(width, height)
    if width == height:
        return image

    small = image.convert("L").resize((240, max(1, round(240 * height / width))))
    pixels = small.load()
    horizontal = width > height

    if horizontal:
        counts = [sum(1 for y in range(small.height) if pixels[x, y] < 235) for x in range(small.width)]
        span = min(small.width, max(1, round(small.width * side / width)))
        total = small.width
    else:
        counts = [sum(1 for x in range(small.width) if pixels[x, y] < 235) for y in range(small.height)]
        span = min(small.height, max(1, round(small.height * side / height)))
        total = small.height

    running = [0]
    for value in counts:
        running.append(running[-1] + value)
    best_index, best_score = 0, -1
    for index in range(total - span + 1):
        score = running[index + span] - running[index]
        if score > best_score:
            best_score, best_index = score, index

    if horizontal:
        left = min(round(best_index / total * width), width - side)
        return image.crop((left, 0, left + side, side))
    top = min(round(best_index / total * height), height - side)
    return image.crop((0, top, side, top + side))


def cut(source: Path) -> Image.Image:
    image = load(source)
    square = ink_window(image)
    if square.width > TILE:
        square = square.resize((TILE, TILE), Image.Resampling.LANCZOS)
        square = square.filter(ImageFilter.UnsharpMask(radius=0.8, percent=55, threshold=3))
    return square


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="Write a contact sheet and nothing else.")
    args = parser.parse_args()

    cuts: list[tuple[str, int, str, Image.Image]] = []
    for section, picks in PICKS.items():
        for index, (slug, relative, _alt) in enumerate(picks, 1):
            source = ROOT / "assets" / "site_images" / relative
            if not source.exists():
                sys.exit(f"missing source: {relative}")
            cuts.append((section, index, slug, cut(source)))

    if args.preview:
        cell = 240
        sheet = Image.new("RGB", (cell * 6, (cell + 26) * 3), "white")
        draw = ImageDraw.Draw(sheet)
        for row, section in enumerate(PICKS):
            draw.text((4, row * (cell + 26) + 6), f"{section} — {len(PICKS[section])} tiles", fill="red")
            column = 0
            for sec, index, slug, image in cuts:
                if sec != section:
                    continue
                thumb = image.copy()
                thumb.thumbnail((cell - 6, cell - 6))
                sheet.paste(thumb, (column * cell + 3, row * (cell + 26) + 24))
                draw.text((column * cell + 5, row * (cell + 26) + 26), f"{index}. {slug}", fill="blue")
                column += 1
        out = ROOT.parent / "wall_preview.jpg"
        sheet.save(out, "JPEG", quality=88)
        print(f"  {out}")
        return

    for section in PICKS:
        folder = OUT / section
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
    for section, index, _slug, image in cuts:
        target = OUT / section / f"{index:02d}.jpg"
        image.save(target, "JPEG", quality=88, optimize=True, progressive=True)
        print(f"  {target.relative_to(ROOT)}  {image.size[0]}x{image.size[1]}")


if __name__ == "__main__":
    main()

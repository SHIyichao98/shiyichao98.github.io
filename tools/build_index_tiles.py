"""Build the homepage image wall from a folder of hand-picked images.

Every pick is matched back to the project it belongs to by image content, cropped
square, and written to assets/site_images/index. Tiles are interleaved by project
so no two images from the same project end up adjacent in the three-column grid.

Colour is handled by export_web_images.load(), not by PIL's plain convert("RGB").
That matters: of one seventeen-image pick set, six were CMYK press files and three
were tagged Apple RGB or Display P3. Converting those without their ICC profile
dropped the red channel by up to sixteen points, which reads on screen as a green
cast, and flattened the Apple RGB files by a further twelve points of gamma.

Usage:
    python tools/build_index_tiles.py assets/index_of_images
    python tools/build_index_tiles.py assets/index_of_images --print-html
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))

from export_web_images import load  # colour-managed read
from match_homepage_picks import SOURCE_SUFFIXES, build_library, dhash

Image.MAX_IMAGE_PIXELS = None

TILE_SIZE = 1200
OUT_DIR = Path("assets/site_images/index")
# Design first, teaching after, matching the sidebar's own emphasis. Projects
# not listed here keep their discovered order and follow.
PROJECT_ORDER = ("loops", "stadium", "craftman", "mars", "street", "robotics", "arch-6020", "arch-2017")


def match_to_project(pick: Path, library) -> tuple[str, int]:
    """Nearest project in the published library, by difference hash."""
    fingerprint = dhash(pick)
    if not fingerprint:
        return "?", 99
    bits, _ = fingerprint
    best = ("?", 99)
    for lib_bits, _, path, slug in library:
        # Only site_images decides identity; the source folders are unpublished
        # and several projects share a source tree.
        if "site_images" not in str(path):
            continue
        distance = bin(bits ^ lib_bits).count("1")
        if distance < best[1]:
            best = (slug, distance)
    return best


def square(image: Image.Image) -> tuple[Image.Image, bool]:
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    cropped = image.crop((left, top, left + side, top + side))
    if side <= TILE_SIZE:
        return cropped, False
    return cropped.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS), True


def interleave(matched: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in matched:
        grouped.setdefault(item["slug"], []).append(item)
    ordered = [grouped[s] for s in PROJECT_ORDER if s in grouped]
    ordered += [v for k, v in grouped.items() if k not in PROJECT_ORDER]
    return [x for x in itertools.chain.from_iterable(itertools.zip_longest(*ordered)) if x]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("picks", type=Path)
    parser.add_argument("--quality", type=int, default=88)
    parser.add_argument("--print-html", action="store_true", help="Emit the gallery markup.")
    args = parser.parse_args()

    picks = sorted(p for p in args.picks.iterdir() if p.suffix.lower() in SOURCE_SUFFIXES)
    if not picks:
        raise SystemExit(f"No images in {args.picks}")

    library = build_library()
    matched = []
    for pick in picks:
        slug, bits = match_to_project(pick, library)
        if bits > 12:
            print(f"  [!] {pick.name}: no confident match (nearest {slug}, {bits} bits) — SKIPPED")
            continue
        matched.append({"file": pick, "slug": slug, "bits": bits})

    tiles = interleave(matched)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(tiles, start=1):
        image = load(item["file"])
        cropped, resampled = square(image)
        if resampled:
            cropped = cropped.filter(ImageFilter.UnsharpMask(radius=0.8, percent=60, threshold=3))
        target = OUT_DIR / f"{index:02d}.jpg"
        cropped.save(target, "JPEG", quality=args.quality, optimize=True, progressive=True)
        item["n"] = index
        short = "" if cropped.width == TILE_SIZE else f"  [!] only {cropped.width}px, source-limited"
        print(f"  {index:02d}.jpg  {cropped.width}x{cropped.height}  {item['slug']:10s} {item['file'].name[:36]}{short}")

    order = [t["slug"] for t in tiles]
    clashes = [
        (i + 1, j + 1, order[i])
        for i in range(len(order))
        for j in (i + 1, i + 3)
        if j < len(order) and order[j] == order[i]
    ]
    print(f"\n  {len(tiles)} tiles across {len(set(order))} projects")
    print(f"  same-project neighbours in a three-column grid: {len(clashes)} {clashes if clashes else ''}")

    if args.print_html:
        print()
        for i, item in enumerate(tiles):
            lazy = "" if i < 3 else '\n          loading="lazy"'
            print(f'      <a class="tile" href="#project/{item["slug"]}" data-project="{item["slug"]}">')
            print(f'        <img\n          src="assets/site_images/index/{item["n"]:02d}.jpg"')
            print(f'          alt="TODO"{lazy}\n        />\n      </a>\n')


if __name__ == "__main__":
    main()

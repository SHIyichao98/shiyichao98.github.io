"""Match hand-picked homepage images back to the project they belong to.

The picks folder is curated by hand, so filenames carry no guarantee: an image
may be a crop, a re-export, a different resolution, or renamed entirely. Rather
than trust the name, every candidate is fingerprinted and compared against every
image already in the project library.

The fingerprint is a difference hash: the image is reduced to greyscale at
9x8, then each pixel is compared with its right-hand neighbour to give 64 bits.
That survives rescaling, re-encoding, and moderate colour shifts, which is
exactly what separates a re-export of the same picture from a different one.
Aspect ratio is carried alongside as a tie-breaker, since a crop changes shape
while a re-export does not.

Usage:
    python tools/match_homepage_picks.py assets/homepage_picks
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

SOURCE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
# Where the project library lives. site_images first: a pick lifted from there
# should match its own project exactly rather than through the original source.
LIBRARY_ROOTS = (
    Path("assets/site_images"),
    Path("assets/my_design_works"),
    Path("assets/research_projects"),
)
# Under 12 differing bits is the same picture in practice; 12-20 is close enough
# to be worth a human glance; beyond that it is a different image.
CERTAIN_BITS = 12
LIKELY_BITS = 20


def dhash(path: Path) -> tuple[int, float] | None:
    try:
        with Image.open(path) as image:
            grey = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            ratio = image.width / image.height
    except OSError:
        return None
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = bits << 1 | (grey.getpixel((x, y)) > grey.getpixel((x + 1, y)))
    return bits, ratio


def project_of(path: Path) -> str:
    """The slug a library image belongs to, taken from its folder."""
    parts = path.parts
    if "site_images" in parts:
        # assets/site_images/<section>/<slug>/[thumbs/]file
        i = parts.index("site_images")
        return parts[i + 2] if len(parts) > i + 2 else "?"
    for root in ("my_design_works", "research_projects"):
        if root in parts:
            i = parts.index(root)
            return f"{root}:{parts[i + 1]}" if len(parts) > i + 1 else "?"
    return "?"


def build_library() -> list[tuple[int, float, Path, str]]:
    library = []
    for root in LIBRARY_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in SOURCE_SUFFIXES or not path.is_file():
                continue
            # site_images/index holds tiles derived from the picks themselves.
            # Leaving them in makes a pick match its own tile, and the folder
            # name becomes the "project", so every pick resolves to "07.jpg".
            if "index" in path.parts and "site_images" in path.parts:
                continue
            fingerprint = dhash(path)
            if fingerprint:
                library.append((*fingerprint, path, project_of(path)))
    return library


def match(pick: Path, library) -> list[tuple[int, Path, str, float]]:
    fingerprint = dhash(pick)
    if not fingerprint:
        return []
    bits, ratio = fingerprint
    scored = []
    for lib_bits, lib_ratio, path, slug in library:
        distance = bin(bits ^ lib_bits).count("1")
        # A crop keeps much of the content but changes shape; nudge those down
        # so an exact-shape re-export wins over a crop of the same picture.
        if abs(lib_ratio - ratio) > 0.02:
            distance += 1
        scored.append((distance, path, slug, lib_ratio))
    scored.sort(key=lambda row: row[0])
    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("picks", type=Path, help="Folder of hand-picked homepage images.")
    parser.add_argument("--show", type=int, default=3, help="Runner-up matches to print.")
    args = parser.parse_args()

    if not args.picks.is_dir():
        raise SystemExit(f"Not a folder: {args.picks}")

    library = build_library()
    print(f"Library: {len(library)} images across {len({row[3] for row in library})} projects\n")

    picks = sorted(p for p in args.picks.iterdir() if p.suffix.lower() in SOURCE_SUFFIXES)
    if not picks:
        raise SystemExit(f"No images in {args.picks}")

    for pick in picks:
        scored = match(pick, library)
        if not scored:
            print(f"  {pick.name}: unreadable")
            continue
        best, path, slug, _ = scored[0]
        verdict = "CERTAIN" if best <= CERTAIN_BITS else "CHECK" if best <= LIKELY_BITS else "NO MATCH"
        print(f"  {pick.name}")
        print(f"    -> {slug}   [{verdict}, {best} bits differ]")
        print(f"       {path.as_posix()}")
        # Show runners-up from other projects, so a close call is visible.
        seen = {slug}
        for distance, other_path, other_slug, _ in scored[1:]:
            if other_slug in seen:
                continue
            seen.add(other_slug)
            print(f"       next: {other_slug} ({distance} bits)")
            if len(seen) > args.show:
                break
        print()


if __name__ == "__main__":
    main()

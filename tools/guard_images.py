"""Cap the resolution of published images and stamp them with their attribution.

Nothing stops a visitor saving a picture: the browser has to download the file
before it can draw it, so the bytes are already on their machine. Blocking the
right-click menu, laying a transparent div over the image, or painting it into a
canvas all fail against the network panel, the direct URL, and the screenshot
key, while costing real visitors the ability to open an image in a new tab.

So this does the two things that are actually within reach.

Resolution. What can be taken is capped at what is needed to look right. The
carousel is 1120 CSS px wide, so a 1600px long edge is sharp on screen; at
300 dpi the same file prints 5.3 inches, which is a thumbnail. The 2240px
exports were 7.5 print inches, reproducible in a book.

Attribution. A mark in the top-left corner travels with the picture once it
leaves the site. On the teaching pages it carries the student's name, read from
that course's gallery_credits so the two can never disagree; elsewhere it
carries the author's. This does not prevent reuse. It makes uncredited reuse
visibly uncredited, which for student coursework is the more useful protection.

Thumbnails, the index wall, and the portrait are left alone: they are too small
for a legible mark, and stamping the homepage would clutter thirty tiles.

Idempotent. Each output's hash is recorded, so a second run is a no-op and a
picture is never stamped twice or resampled twice. Replace a source image and
only that one is redone.

    python tools/guard_images.py --dry-run
    python tools/guard_images.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "assets" / "site_images"
PROJECTS = ROOT / "content" / "projects"
MANIFEST = ROOT / "tools" / "image_guard.json"

# 1600 on the long edge. The widest slot on the site is the 1120 CSS px
# carousel, so this still oversamples every display; at 300 dpi it prints
# 5.3 in.
LONG_EDGE = 1600
QUALITY = 88

# Folders holding pictures too small to mark, or shown in a grid where a mark
# would read as noise rather than as a credit.
SKIP_PARTS = {"thumbs", "index", "profile"}

OWN_MARK = "\u00a9 Yichao Shi \u00b7 yichaoshi.com"
FONT_PATHS = (
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def credit_map() -> dict[str, str]:
    """Published image path -> the line to stamp on it.

    Built from the same front matter the page renders from, so a name shown
    under a picture and a name burned into it cannot drift apart.
    """
    marks: dict[str, str] = {}
    for md in sorted(PROJECTS.glob("*.md")):
        meta = front_matter(md)
        course = meta.get("title", "")
        for field, credit_field in (("gallery", "gallery_credits"), ("gallery_full", "gallery_full_credits")):
            if field not in meta:
                continue
            shots = [s.strip() for s in meta[field].split("|") if s.strip()]
            names = [c.strip() for c in meta.get(credit_field, "").split("|")] if meta.get(credit_field) else []
            for index, shot in enumerate(shots):
                key = shot.replace("\\", "/")
                if index < len(names) and names[index]:
                    marks[key] = f"Student work by {names[index]} \u00b7 {course} \u00b7 Georgia Tech"
                else:
                    marks[key] = OWN_MARK
    return marks


def mark_for(path: Path, marks: dict[str, str]) -> str:
    key = path.relative_to(ROOT).as_posix()
    if key in marks:
        return marks[key]
    # A cover crop has no entry of its own. On a teaching page it is still
    # student work, and saying so without a name is better than claiming it.
    if "teaching" in path.parts:
        slug = path.parent.name
        meta = front_matter(PROJECTS / f"{slug}.md") if (PROJECTS / f"{slug}.md").exists() else {}
        return f"Student work \u00b7 {meta.get('title', slug)} \u00b7 Georgia Tech"
    return OWN_MARK


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_PATHS:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def stamp(image: Image.Image, text: str) -> Image.Image:
    """Top-left corner mark, sized to the picture rather than fixed.

    Drawn white over a dark shadow: a single colour disappears into either a
    white drawing or a night render, and the pair reads on both.
    """
    long_edge = max(image.size)
    size = max(11, round(long_edge * 0.0155))
    inset = round(long_edge * 0.022)
    font = load_font(size)

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    offset = max(1, round(size * 0.075))
    draw.text((inset + offset, inset + offset), text, font=font, fill=(0, 0, 0, 110))
    draw.text((inset, inset), text, font=font, fill=(255, 255, 255, 205))

    out = image.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def digest(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing.")
    parser.add_argument("--force", action="store_true", help="Redo files the manifest says are done.")
    args = parser.parse_args()

    done: dict[str, str] = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    marks = credit_map()

    resized = stamped = skipped = 0
    for path in sorted(IMAGES.rglob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png"} or not path.is_file():
            continue
        if SKIP_PARTS & set(path.relative_to(IMAGES).parts):
            continue

        key = path.relative_to(ROOT).as_posix()
        if not args.force and done.get(key) == digest(path):
            skipped += 1
            continue

        image = Image.open(path)
        image = image.convert("RGB") if image.mode != "RGB" else image
        before = image.size

        scale = LONG_EDGE / max(image.size)
        if scale < 1:
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
            resized += 1

        text = mark_for(path, marks)
        image = stamp(image, text)
        stamped += 1

        note = f"{before[0]}x{before[1]}" + (f" -> {image.width}x{image.height}" if before != image.size else " kept")
        print(f"  {key}  {note}")
        print(f"      {text}")

        if not args.dry_run:
            image.save(path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            done[key] = digest(path)

    if not args.dry_run:
        MANIFEST.write_text(json.dumps(done, indent=1, sort_keys=True), encoding="utf-8")

    total = sum(f.stat().st_size for f in IMAGES.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"\n  stamped {stamped}, downscaled {resized}, already done {skipped}")
    print(f"  assets/site_images now {total:.1f} MB")


if __name__ == "__main__":
    main()

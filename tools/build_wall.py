"""Cut the homepage wall from the hand-picked images in assets/index_of_images.

The wall is three sections — teaching, research, design — of nine square tiles.
Each tile links to a project and names it on hover, so every pick has to be tied
to one. Two ways of doing that, because the two halves of the folder differ:

  Teaching and design picks are lifted from work already on the site, so they are
  matched by image content. A filename there is whatever the file was called when
  it was saved and proves nothing.

  Research picks are new crops from the papers and exist nowhere else, so content
  matching has nothing to match against — it once resolved a research figure to a
  headshot. Those are read from the filename, which names its project on purpose.

Colour goes through export_web_images.load(): a plain convert("RGB") drops the
red channel on CMYK and Display P3 files, which reads on screen as a green cast.

    python tools/build_wall.py            # write the tiles and the markup
    python tools/build_wall.py --preview  # contact sheet only, write nothing
    python tools/build_wall.py --match    # report how each pick was tied to a project
"""

from __future__ import annotations

import argparse
import collections
import random
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# Student phone photographs arrive as HEIC, sometimes already renamed .jpg.
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pip install pillow-heif
    pass

sys.path.insert(0, str(Path(__file__).parent))

from export_web_images import load  # colour-managed read
from match_homepage_picks import build_library, dhash

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
PICKS = ROOT / "assets" / "index_of_images"
OUT = ROOT / "assets" / "site_images" / "index"
TILE = 1000
# Rows of three, so a section keeps whatever it is given rounded down to a
# multiple of three. A part-filled last row reads as a gap rather than an end.
ROW = 3
# Order on the page: design, then teaching, then research.
SECTIONS = (
    ("design", "My Design Works", "my_design"),
    ("teaching", "My Teaching Works", "teaching"),
    ("research", "My Research Works", "research"),
)

# A research filename names its project; nothing else can. Longest first so
# caadria2025_02 is not read as caadria2025.
BY_NAME = (
    ("caadria2025_02", "caadria-2025-2"),
    ("caadria2025_01", "caadria-2025-1"),
    ("caadria2026", "caadria-2026"),
    ("simaud_2026", "simaud-2026"),
    ("simaud_2023", "simaud-2023"),
    ("dcc_2026", "dcc-2026"),
    ("dcc_2024", "dcc-2024"),
    ("acadia", "acadia-2022"),
)
# A library slug may be a page slug (acadia-2022) or a source folder name
# (ACADIA_2022, ucl_loops). Normalise before looking anything up.
def normalise(slug: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")


# The ACADIA paper and the LOOPS design project are the same work, so a design
# pick that matches the paper library belongs to the design page.
AS_DESIGN = {"acadia-2022": "loops", "ucl-loops": "loops"}
# Content matching cannot place a pick that exists nowhere else in the library,
# and at nineteen differing bits it guesses: 27-2-2 is the porcelain workshop,
# which it read as LOOPS. Anything it places past a dozen bits is worth an eye.
#
# Samuel Thurman_13 lands at 22 bits against its own published copy, because
# that copy now carries a corner credit (tools/guard_images.py) and the source
# here does not. A dHash is 9x8, so a mark in the top-left corner moves real
# bits. Expect more of these as the guarded set grows; the fix is a line here,
# not a looser threshold.
BY_HAND = {
    "01-01.jpg": "street",
    "27-2-2.jpg": "craftman",
    "dome.jpg": "mars",
    "Samuel Thurman_13.png": "arch-8833",
    "Samuel Thurman_01.png": "arch-8833",
    # Read as DCC 2024 at 18 bits. It is Lucas Nagel's axonometric from the
    # 2026 studio; the source folder says so and the published copy is
    # watermarked, which is what pushed the true match out of range.
    "Lucas Nagel_01.jpg": "arch-2017",
    # The studio's plaster models photographed together. No single student's
    # file, so no name on the caption, but the course is not in doubt: Lucas
    # Nagel's cast is in the middle of the group.
    "models01.jpg": "arch-2017",
    # Not in any course folder and matched at 16 bits. A brick gallery in
    # section is the 2026 studio's brief -- an art gallery in Sweet Auburn --
    # so it is placed there until the author says otherwise.
    "Rishi Patel_01.jpg": "arch-2017",
    # Page 22 of the Kokura portfolio, before that project was published.
    "housing.jpg": "kokura",
}
# Past this many differing bits the nearest neighbour is a coincidence, not the
# same picture. Cropping a pick square by hand pushes it up the scale, so a
# match that used to be exact can drift out of range; better to stop and be
# told than to ship a tile that links to the wrong project.
TRUST_BITS = 20
# Picks that open a section, in this order, before the shuffle places the rest.
# Keyed by section, valued by source filename. The first row is the one a
# visitor sees without scrolling, so it is chosen rather than drawn.
LEAD = {}
# A section listed here is laid out exactly as written and never shuffled.
# Written once the author has moved tiles by hand: a shuffle that reseeds
# would undo the move, and pinning only a first row leaves the rest loose.
# Every pick in the folder must appear once; the build refuses otherwise.
ORDER = {
    "teaching": (
        "models01.jpg",
        "Jonathan Caruso & Jiawei Gong01.png",
        "Lucas Nagel_01.jpg",
        "Jiawei Gong_01.jpeg",
        "Lydia Efthymiopoulou_05.jpg",
        "Chase Scholze_02.png",
        "Miguel Pita-Ruiz_04.png",
        "Samuel Thurman_01.png",
        "Rishi Patel_01.jpg",
    ),
}

TITLES = {
    "arch-2017": "Architectural Design Studio",
    "arch-2020": "Computational Design Foundations",
    "arch-6020": "Advanced Computational Design",
    "arch-8833": "AI & Computational Design",
    "acadia-2022": "Elastic Robotic Structures",
    "caadria-2025-1": "Shape Grammar + Generative AI",
    "caadria-2025-2": "Generative AI + Interactive Design",
    "caadria-2026": "Shape Grammar + AI Benchmarking",
    "dcc-2024": "Shape Grammar + Parametric Design",
    "dcc-2026": "Shape Grammar + Inference",
    "simaud-2023": "Shape Grammar + Machine Learning",
    "simaud-2026": "Shape Grammar + Building Performance",
    "craftman": "Porcelain Handicraft Workshop",
    "loops": "LOOPS",
    "mars": "Conquer the Mars",
    "robotics": "Overnight House",
    "stadium": "Stadium Design for a University",
    "street": "School Gate Street Reconstruction",
    "kokura": "Kokura Station Modular Construction",
}


def project_by_name(path: Path) -> str | None:
    stem = re.sub(r"[^a-z0-9]+", "_", path.stem.lower())
    for needle, slug in BY_NAME:
        if needle in stem:
            return slug
    return None


def project_by_content(path: Path, library) -> tuple[str | None, int]:
    fingerprint = dhash(path)
    if fingerprint is None:
        return None, 99
    bits, _ratio = fingerprint
    best, best_bits = None, 99
    for other_bits, _ratio, _p, slug in library:
        differ = bin(bits ^ other_bits).count("1")
        if differ < best_bits:
            best, best_bits = slug, differ
    if best is None:
        return None, 99
    slug = normalise(best.split(":")[-1])
    return AS_DESIGN.get(slug, slug), best_bits


def resolve(section: str, path: Path, library):
    """Return (slug, how). Research reads its name; everything else its pixels."""
    if path.name in BY_HAND:
        return BY_HAND[path.name], "by hand"
    if section == "research":
        slug = project_by_name(path)
        if slug:
            return slug, "filename"
    slug, bits = project_by_content(path, library)
    if bits > TRUST_BITS:
        return None, f"no confident match, nearest {slug} at {bits} bits"
    return slug, f"content, {bits} bits"


def looks_like_a_slide(image: Image.Image) -> bool:
    """True for a presentation frame: wide, and mostly paper."""
    if image.width < image.height * 1.2:
        return False
    small = image.convert("L").resize((160, 90))
    grey = list(small.getdata())
    return sum(1 for v in grey if v > 235) / len(grey) > 0.5


def centre(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def square_crop(image: Image.Image) -> Image.Image:
    """Square. Centred, unless the source is a slide.

    Centred is what a picture wants: a render or a photograph is composed
    around its middle, and moving the window off it reads as a mistake even
    when the window is technically fuller. Chasing the ink through a wide
    render finds whatever corner holds the most contrast — one Mars view has a
    dark slab down its left edge, and the tile came back leaning on it.

    A slide is the exception: it is mostly white margin, so a centred window
    lands on nothing, and its title band has to come off first.
    """
    if not looks_like_a_slide(image):
        return centre(image)
    return ink_window(image.crop((0, round(image.height * 0.19), image.width, round(image.height * 0.89))))


def ink_window(image: Image.Image) -> Image.Image:
    """Place the square where the marks are densest. For slides only."""
    width, height = image.size
    side = min(width, height)
    if width == height:
        return image

    small = image.convert("L").resize((240, max(1, round(240 * height / width))))
    pixels = small.load()
    horizontal = width > height
    if horizontal:
        counts = [sum(1 for y in range(small.height) if pixels[x, y] < 235) for x in range(small.width)]
        span, total = min(small.width, max(1, round(small.width * side / width))), small.width
    else:
        counts = [sum(1 for x in range(small.width) if pixels[x, y] < 235) for y in range(small.height)]
        span, total = min(small.height, max(1, round(small.height * side / height))), small.height

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


def mix(items, cols=3, seed=5, head=()):
    """Order so no project sits beside its own work, or directly above it.

    The grid is three wide, so tile i touches i-1 and i-3. Guarding only against
    the first still stacks a project down a column.

    `head` is placed first, as given; the shuffle fills in after it and still
    avoids putting a project under one of the pinned tiles.
    """
    best = None
    for attempt in range(seed, seed + 400):
        rng = random.Random(attempt)
        pool = collections.defaultdict(list)
        for item in items:
            if item not in head:
                pool[item["slug"]].append(item)
        for group in pool.values():
            rng.shuffle(group)
        out = list(head)
        while any(pool.values()):
            banned = {out[-1]["slug"]} if out else set()
            if len(out) >= cols:
                banned.add(out[-cols]["slug"])
            options = [k for k, v in pool.items() if v and k not in banned] or [k for k, v in pool.items() if v]
            most = max(len(pool[k]) for k in options)
            out.append(pool[rng.choice([k for k in options if len(pool[k]) == most])].pop())
        slugs = [i["slug"] for i in out]
        clashes = sum(1 for i in range(1, len(slugs)) if slugs[i] == slugs[i - 1])
        clashes += sum(1 for i in range(cols, len(slugs)) if slugs[i] == slugs[i - cols])
        if best is None or clashes < best[0]:
            best = (clashes, out)
        if clashes == 0:
            break
    return best[1], best[0]


def gather(report: bool):
    library = build_library()
    sections = {}
    for key, _title, folder in SECTIONS:
        source = PICKS / folder
        if not source.is_dir():
            sys.exit(f"missing pick folder: {source}")
        items = []
        for path in sorted(p for p in source.iterdir() if p.is_file()):
            slug, how = resolve(key, path, library)
            if slug is None or slug not in TITLES:
                print(f"  [!] {path.name}: {how} — add it to BY_HAND", file=sys.stderr)
                continue
            items.append({"slug": slug, "path": path, "how": how})
        if report:
            print(f"  {key}: {len(items)} picks")
            for item in items:
                print(f"    {item['path'].name:<46} -> {item['slug']:<16} ({item['how']})")
            counts = collections.Counter(i["slug"] for i in items)
            missing = [s for s in TITLES if s not in counts and _section_of(s) == key]
            print(f"    projects: {dict(counts)}")
            if missing:
                print(f"    not represented: {', '.join(missing)}")
            print()
        sections[key] = items
    return sections


def _section_of(slug: str) -> str:
    if slug.startswith("arch-"):
        return "teaching"
    if slug in {"craftman", "loops", "mars", "robotics", "stadium", "street", "kokura"}:
        return "design"
    return "research"


def trim(items, limit):
    """Keep `limit`, dropping from whichever project has the most to spare."""
    dropped = []
    while len(items) > limit:
        counts = collections.Counter(i["slug"] for i in items)
        fattest = counts.most_common(1)[0][0]
        # Drop the one that would crop worst: furthest from square.
        worst, index = None, None
        for i, item in enumerate(items):
            if item["slug"] != fattest:
                continue
            width, height = Image.open(item["path"]).size
            skew = max(width / height, height / width)
            if worst is None or skew > worst:
                worst, index = skew, i
        dropped.append(items.pop(index))
    return items, dropped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="Contact sheet only, write nothing.")
    parser.add_argument("--match", action="store_true", help="Report how each pick was placed, write nothing.")
    args = parser.parse_args()

    sections = gather(report=args.match or args.preview)
    if args.match:
        return

    ordered = {}
    for key, _title, _folder in SECTIONS:
        kept, dropped = trim(sections[key], len(sections[key]) // ROW * ROW)
        if dropped:
            print(f"  {key}: kept {len(kept)}, left out {', '.join(d['path'].name for d in dropped)}")
        names = {item["path"].name: item for item in kept}
        if key in ORDER:
            wanted = ORDER[key]
            if sorted(wanted) != sorted(names):
                sys.exit(f"{key}: ORDER does not match the folder. "
                         f"missing {sorted(set(wanted) - set(names))}, extra {sorted(set(names) - set(wanted))}")
            ordered[key] = [names[n] for n in wanted]
            continue
        head = [names[n] for n in LEAD.get(key, ()) if n in names]
        absent = [n for n in LEAD.get(key, ()) if n not in names]
        if absent:
            print(f"  [!] {key}: lead pick(s) not in the section: {', '.join(absent)}", file=sys.stderr)
        mixed, clashes = mix(kept, head=head)
        if clashes:
            print(f"  {key}: {clashes} tile(s) still adjacent to their own project")
        ordered[key] = mixed

    cuts = {key: [(item["slug"], cut(item["path"])) for item in items] for key, items in ordered.items()}

    if args.preview:
        cell = 200
        rows = max(len(v) for v in cuts.values())
        sheet = Image.new("RGB", (cell * rows, (cell + 26) * len(SECTIONS)), "white")
        draw = ImageDraw.Draw(sheet)
        for row, (key, _title, _folder) in enumerate(SECTIONS):
            draw.text((4, row * (cell + 26) + 6), key, fill="red")
            for column, (slug, image) in enumerate(cuts[key]):
                thumb = image.copy()
                thumb.thumbnail((cell - 6, cell - 6))
                sheet.paste(thumb, (column * cell + 3, row * (cell + 26) + 24))
                draw.text((column * cell + 5, row * (cell + 26) + 26), f"{column+1}.{slug}", fill="blue")
        out = ROOT.parent / "wall_preview.jpg"
        sheet.save(out, "JPEG", quality=88)
        print(f"  {out}")
        return

    for key, _title, _folder in SECTIONS:
        folder = OUT / key
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        for index, (_slug, image) in enumerate(cuts[key], 1):
            target = folder / f"{index:02d}.jpg"
            image.save(target, "JPEG", quality=88, optimize=True, progressive=True)
        print(f"  {key}: {len(cuts[key])} tiles")

    write_markup(cuts)


def cut(source: Path) -> Image.Image:
    image = load(source)
    square = square_crop(image)
    if square.width > TILE:
        square = square.resize((TILE, TILE), Image.Resampling.LANCZOS)
        square = square.filter(ImageFilter.UnsharpMask(radius=0.8, percent=55, threshold=3))
    return square


def write_markup(cuts) -> None:
    index = ROOT / "index.html"
    text = index.read_text(encoding="utf-8")
    version = re.search(r"styles\.css\?v=(\d+)", text).group(1)

    lines = ['    <main class="gallery" aria-label="Selected work">']
    # The wall has no opening text now. If a hand-written header ever returns
    # it is carried across whole rather than rebuilt: rebuilding one from a
    # captured sentence silently dropped its keyword list the first time.
    opening = re.search(r'      <header class="masthead">[\s\S]*?</header>', text)
    if opening:
        lines += [opening.group(0), ""]

    for key, title, _folder in SECTIONS:
        lines.append(f'      <section class="wall" aria-labelledby="wall-{key}">')
        # Drawn nowhere -- styles.css hides it -- but named for screen readers.
        lines.append(f'        <h2 id="wall-{key}">{title}</h2>')
        lines.append('        <div class="wall-grid">')
        for i, (slug, _image) in enumerate(cuts[key], 1):
            eager = key == SECTIONS[0][0] and i <= 3
            lines.append(f'          <a class="tile" href="#project/{slug}" data-project="{slug}">')
            lines.append("            <img")
            lines.append(f'              src="assets/site_images/index/{key}/{i:02d}.jpg?v={version}"')
            lines.append(f'              alt="{TITLES[slug]}"' + ("" if eager else '\n              loading="lazy"'))
            lines.append("            />")
            lines.append("          </a>")
        lines += ["        </div>", "      </section>", ""]
    lines.append("    </main>")

    updated = re.sub(r'    <main class="gallery"[\s\S]*?\n    </main>', "\n".join(lines), text, count=1)
    index.write_text(updated, encoding="utf-8")
    print(f"  index.html: {sum(len(v) for v in cuts.values())} tiles")


if __name__ == "__main__":
    main()

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
import html
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
# Two tracks for teaching. The homepage shows the nine in index_of_images/
# teaching and nothing more; a category view (Architectural Design Studio and
# the rest) shows those plus whatever is in teaching_extra. Extra tiles are
# built into the same wall and hidden on the homepage, so a category view is
# still one wall cut by category, only a fuller one.
EXTRA_PICKS = PICKS / "teaching_extra"
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
    # Read as DCC 2024 at 18 bits. It is Lucas Nagel's axonometric from the
    # 2026 studio; the source folder says so and the published copy is
    # watermarked, which is what pushed the true match out of range.
    "Lucas Nagel_01.jpg": "arch-2017-lucas-nagel-final-drawings",
    # Each has its own page now; the published copies carry a corner credit,
    # which is what keeps content matching from placing them on its own.
    "models01.jpg": "arch-2017-lucas-nagel-physical-models",
    "Rishi Patel_00.png": "arch-2017-rishi-patel",
    "Samuel Thurman_01.png": "arch-8833-samuel-thurman",
    # The square version of this drawing was taken off the student's page, so
    # nothing published matches it any more and content matching drifted to
    # the nearest other picture.
    "Jiawei Gong_01.jpeg": "arch-6020-jiawei-gong-architectural-fields",
    # The course cover was cut from this picture, so content matching lands
    # on the course page at 3 bits; the project page is the one to open.
    "Jonathan Caruso & Jiawei Gong01.png": "arch-6020-jonathan-caruso-jiawei-gong-image-based-building-elements-and-systems",

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
LEAD = {
    # The research wall opens on the robotic structures; the rest shuffle.
    "research": ("acadia_02.jpg",),
}
# A section listed here is laid out exactly as written and never shuffled.
# Written once the author has moved tiles by hand: a shuffle that reseeds
# would undo the move, and pinning only a first row leaves the rest loose.
# Every pick in the folder must appear once; the build refuses otherwise.
ORDER = {
    "design": (
        "07.png",
        "axon.jpg",
        "dome.jpg",
        "housing.jpg",
        "robots.jpg",
        "27-2-2.jpg",
    ),
    "teaching": (
        "models01.jpg",
        "Jonathan Caruso & Jiawei Gong01.png",
        "Lucas Nagel_01.jpg",
        "Jiawei Gong_01.jpeg",
        "Lydia Efthymiopoulou_05.jpg",
        "Chase Scholze_02.png",
        "Miguel Pita-Ruiz_04.png",
        "Samuel Thurman_01.png",
        "Rishi Patel_00.png",
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


def titles_from_sidebar() -> dict[str, str]:
    """Every data-project link in the sidebar, slug -> text. Student pages are
    written by tools/build_teaching.py and would otherwise need listing here."""
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    return dict(re.findall(r'<a href="#project/([^"]+)" data-project="[^"]+"[^>]*>([^<]+)</a>', text))


def student_captions() -> dict[str, str]:
    """Student page slug -> 'ARCH 2017 · Lucas Nagel'. Student pages are not in
    the sidebar, so their tiles carry the caption themselves."""
    out = {}
    for md in (ROOT / "content" / "projects").glob("arch-*-*.md"):
        meta = {}
        block = md.read_text(encoding="utf-8").split("---", 2)[1]
        for line in block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        if meta.get("student"):
            out[md.stem] = f"{meta.get('title', '')} \u00b7 {meta['student']}"
            if meta.get("project"):
                out[md.stem] += f" \u00b7 {meta['project']}"
    return out


CAPTIONS = student_captions()


def category_of(slug: str) -> str | None:
    """Teaching category slug for a course or student page slug, else None."""
    from build_teaching import CATEGORIES  # noqa: PLC0415  (same folder)

    for cat_slug, _title, _span, _summary, courses in CATEGORIES:
        if any(slug == c or slug.startswith(f"{c}-") for c in courses):
            return cat_slug
    return None
TITLES = {**TITLES, **titles_from_sidebar(), **CAPTIONS}


def project_by_name(path: Path) -> str | None:
    # Compare with every separator stripped, so caadria_2026, caadria2026
    # and CAADRIA-2026 are one name.
    stem = re.sub(r"[^a-z0-9]", "", path.stem.lower())
    for needle, slug in BY_NAME:
        if re.sub(r"[^a-z0-9]", "", needle) in stem:
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
        # A tie between a course and one of its students goes to the student:
        # the same picture is published under both, and the page that names
        # the maker is the one to open.
        if differ < best_bits or (differ == best_bits and best and len(slug) > len(best)):
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


def resolve_extra(path: Path, library) -> tuple[str | None, str]:
    """An extra pick is filed under its category and named "Student_Project",
    which is enough to find its page without looking at the pixels: the
    category's courses are tried in turn for a page with that student and
    project. Content matching is the fallback, for a file named otherwise."""
    from build_teaching import CATEGORIES, slugify, split_folder  # noqa: PLC0415

    if path.name in BY_HAND:
        return BY_HAND[path.name], "by hand"
    courses = ()
    for _slug, title, _span, _summary, course_slugs in CATEGORIES:
        if path.parent.name.strip().lower() == title.lower():
            courses = course_slugs
    student, project = split_folder(path.stem)
    for course in courses:
        candidates = [f"{course}-{slugify(student)}-{slugify(project)}"] if project else []
        candidates.append(f"{course}-{slugify(student)}")
        for candidate in candidates:
            if candidate in TITLES:
                return candidate, "filename"
        # One project only: the name alone should find it.
        stem = f"{course}-{slugify(student)}-"
        matches = [slug for slug in TITLES if slug.startswith(stem)]
        if len(matches) == 1:
            return matches[0], "filename (only project)"
    return resolve("teaching", path, library)


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
    if slug.startswith("arch-") or slug.startswith("teaching-"):
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

    # The second track: category-only teaching tiles, after the homepage nine.
    extras = []
    if EXTRA_PICKS.is_dir():
        library = build_library()
        # Subfolders are the author's filing (one per category); the category a
        # tile lands in comes from its student's course, not from the folder.
        for path in sorted(p for p in EXTRA_PICKS.rglob("*") if p.is_file()):
            slug, how = resolve_extra(path, library)
            if slug is None or slug not in TITLES:
                print(f"  [!] extra {path.name}: {how} \u2014 add it to BY_HAND", file=sys.stderr)
                continue
            extras.append({"slug": slug, "path": path, "how": how})
        # An extra that is one of the homepage nine would show twice in a
        # category view. Match by content, not by name: the same picture was
        # filed under two names in two folders.
        homepage = [dhash(item["path"]) for item in ordered.get("teaching", [])]
        kept_extras = []
        for item in extras:
            print_ = dhash(item["path"])
            twin = any(
                print_ and mine and bin(print_[0] ^ mine[0]).count("1") <= 6
                for mine in homepage
            )
            if twin:
                print(f"  teaching: {item['path'].name} is already on the homepage, not repeated")
            else:
                kept_extras.append(item)
        extras = kept_extras
        if extras:
            extras, _clashes = mix(extras)
            print(f"  teaching: {len(extras)} extra tile(s) for the category views")

    cuts = {key: [(item["slug"], cut(item["path"]), False) for item in items] for key, items in ordered.items()}
    cuts["teaching"] += [(item["slug"], cut(item["path"]), True) for item in extras]

    if args.preview:
        cell = 200
        rows = max(len(v) for v in cuts.values())
        sheet = Image.new("RGB", (cell * rows, (cell + 26) * len(SECTIONS)), "white")
        draw = ImageDraw.Draw(sheet)
        for row, (key, _title, _folder) in enumerate(SECTIONS):
            draw.text((4, row * (cell + 26) + 6), key, fill="red")
            for column, (slug, image, _extra) in enumerate(cuts[key]):
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
        for index, (_slug, image, _extra) in enumerate(cuts[key], 1):
            target = folder / f"{index:02d}.jpg"
            image.save(target, "JPEG", quality=88, optimize=True, progressive=True)
        print(f"  {key}: {len(cuts[key])} tiles")

    write_markup(cuts)
    write_course_walls(cuts["teaching"])


def write_course_walls(teaching) -> None:
    """A course page shows its category's wall -- the same tiles, homepage and
    extra alike, each opening a student's page -- so the three ways in
    (category link, course page, homepage) agree on what there is to see."""
    from build_teaching import CATEGORIES, write_course_hub  # noqa: PLC0415

    by_category: dict[str, list[str]] = {}
    for index, (slug, _image, _extra) in enumerate(teaching, 1):
        category = category_of(slug)
        if not category:
            continue
        tile = f"assets/site_images/index/teaching/{index:02d}.jpg"
        caption = CAPTIONS.get(slug, TITLES.get(slug, slug))
        by_category.setdefault(category, []).append(f"{slug}::{caption}::{tile}")
    for cat_slug, _title, _span, _summary, courses in CATEGORIES:
        for course in courses:
            write_course_hub(course, by_category.get(cat_slug, []))
    print(f"  course pages: walls written for {sum(len(c) for *_r, c in CATEGORIES)} courses")


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
        for i, (slug, _image, extra) in enumerate(cuts[key], 1):
            eager = key == SECTIONS[0][0] and i <= 3
            caption = f' data-caption="{html.escape(CAPTIONS[slug], quote=True)}"' if slug in CAPTIONS else ""
            category = category_of(slug)
            cut = f' data-category="{category}"' if category else ""
            more = " data-extra" if extra else ""
            lines.append(f'          <a class="tile" href="#project/{slug}" data-project="{slug}"{caption}{cut}{more}>')
            lines.append("            <img")
            lines.append(f'              src="assets/site_images/index/{key}/{i:02d}.jpg?v={version}"')
            lines.append(f'              alt="{TITLES[slug]}"' + ("" if eager else '\n              loading="lazy"'))
            lines.append("            />")
            lines.append("          </a>")
        lines += ["        </div>", "      </section>", ""]
    lines.append("    </main>")

    updated = re.sub(r'    <main class="gallery"[\s\S]*?\n    </main>', "\n".join(lines), text, count=1)
    index.write_text(updated, encoding="utf-8")
    homepage = sum(1 for v in cuts.values() for _s, _i, extra in v if not extra)
    print(f"  index.html: {homepage} tiles on the homepage, {sum(len(v) for v in cuts.values()) - homepage} more in the category views")


if __name__ == "__main__":
    main()

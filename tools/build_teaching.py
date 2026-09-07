"""Build one page per student project from the teaching source folders.

The teaching section used to be one page per course, with every student's
work on it. It is now one page per student project, still filed under the
course: the page keeps the course number, term and description, and adds a
line naming the student and the assignment. A course can have a grid of
square tiles and a run of full-width figures, from two source subfolders.

    assets/teaching_work_samples/<course folder>/<Student Name>/
        grids/  01.jpg    -> square tiles, opening in the lightbox
        full/   01.jpg    -> shown whole, one per row

One folder per student, named as the name should appear on the page; a team
is one folder ("Hang Xu & Dingkun Hu"). Files are ordered by the number in
their name, whatever else the name says. Anything at the course level that is
not a student folder is ignored.

What this writes:

    assets/site_images/teaching/<course>/<student>/grid/NN.jpg  (+ thumbs/)
    assets/site_images/teaching/<course>/<student>/full/NN.jpg
    assets/site_images/teaching/<course>/<student>/hero.jpg
    content/projects/<course>-<student>.md
    index.html      the Teaching section of the sidebar, between its markers
    script.js       the projectSources entries, between their markers

Assignment names come from tools/assignments.csv (course, student,
assignment). The table is created with blanks the first time and never
overwritten; fill a blank in and rebuild. A student with no assignment named
gets the student line only.

The course pages (arch-2017.md and the rest) are left as they are.

Run tools/guard_images.py afterwards: it stamps each new picture with the
student's name, read from the page it belongs to.

    python tools/build_teaching.py
    python tools/build_teaching.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from export_web_images import (  # noqa: E402
    HERO_SIZE,
    MAIN_BOX,
    SOURCE_SUFFIXES,
    THUMB_SIZE,
    fit_within,
    load,
    save,
    square_crop,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "assets" / "teaching_work_samples"
OUT = ROOT / "assets" / "site_images" / "teaching"
PROJECTS = ROOT / "content" / "projects"
TABLE = ROOT / "tools" / "assignments.csv"

# Source folder -> course slug. The course page (content/projects/<slug>.md)
# supplies the title, term, description and the text of every student page.
COURSES = {
    "2026Spring_ARCH_2017": "arch-2017",
    "2023&2024Fall_Arch2020": "arch-2020",
    "2025Fall_Arch_6020": "arch-6020",
    "2025Spring_Arch_8833": "arch-8833",
}
QUALITY = 88

# The number that orders a file: "03.jpg", "Lucas Nagel_03.jpg", "img-3.png".
NUMBER = re.compile(r"(\d+)(?!.*\d)")
NOT_STUDENTS = {"grids", "full", "hero_image"}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def display_name(raw: str) -> str:
    """Kayla_Rinoski and Kayla Rinoski are one person."""
    return re.sub(r"\s+", " ", raw.replace("_", " ")).strip()


def front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    _, block, body = text.split("---", 2)
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, body.strip("\n")


def read_table() -> dict[tuple[str, str], str]:
    if not TABLE.exists():
        return {}
    with TABLE.open(encoding="utf-8", newline="") as handle:
        return {(r["course"], r["student"]): r["assignment"].strip() for r in csv.DictReader(handle)}


def write_table(rows: dict[tuple[str, str], str]) -> None:
    with TABLE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["course", "student", "assignment"])
        for (course, student), assignment in sorted(rows.items()):
            writer.writerow([course, student, assignment])


def collect(folder: Path) -> dict[str, dict[str, list[Path]]]:
    """Student display name -> {"grid": [...], "full": [...]}, each in number order."""
    students: dict[str, dict[str, list[Path]]] = {}
    for student_dir in sorted(folder.iterdir()):
        if not student_dir.is_dir() or student_dir.name in NOT_STUDENTS:
            continue
        name = display_name(student_dir.name)
        shots = {"grid": [], "full": []}
        for kind, sub in (("grid", "grids"), ("full", "full")):
            source = student_dir / sub
            if not source.is_dir():
                continue
            files = [p for p in source.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES]
            keyed = []
            for path in files:
                match = NUMBER.search(path.stem)
                keyed.append((int(match.group(1)) if match else 10**6, path.name, path))
            shots[kind] = [p for _n, _name, p in sorted(keyed)]
        if shots["grid"] or shots["full"]:
            students[name] = shots
        else:
            print(f"  [!] {student_dir.relative_to(SOURCES)}: no grids/ or full/ pictures", file=sys.stderr)
    return students


def export(student_dir: Path, shots: dict[str, list[Path]], dry: bool) -> dict[str, list[str]]:
    """Write the pictures; return the published paths per kind, site-relative."""
    published: dict[str, list[str]] = {"grid": [], "full": []}
    if not dry:
        shutil.rmtree(student_dir, ignore_errors=True)
    hero_source = (shots["grid"] or shots["full"])[0]
    for kind in ("grid", "full"):
        for index, path in enumerate(shots[kind], 1):
            target = student_dir / kind / f"{index:02d}"
            published[kind].append(f"{target.relative_to(ROOT).as_posix()}.jpg")
            if dry:
                continue
            image = load(path)
            main, resampled = fit_within(image, MAIN_BOX)
            save(main, target, "jpeg", QUALITY, resampled)
            if kind == "grid":
                thumb, thumb_resampled = square_crop(image, THUMB_SIZE)
                save(thumb, student_dir / kind / "thumbs" / f"{index:02d}", "jpeg", QUALITY, thumb_resampled)
    if not dry:
        hero, hero_resampled = square_crop(load(hero_source), HERO_SIZE)
        save(hero, student_dir / "hero", "jpeg", QUALITY, hero_resampled)
    return published


def page(course: dict[str, str], body: str, student: str, assignment: str, course_slug: str,
         cover: str, shots: dict[str, list[str]]) -> str:
    lines = [
        "---",
        f"title: {course['title']}",
        f"year: {course['year']}",
        f"type: {course['type']}",
        f"subtitle: {course['subtitle']}",
        f"cover: {cover}",
    ]
    if shots["grid"]:
        lines.append("gallery: " + " | ".join(shots["grid"]))
    if shots["full"]:
        lines.append("gallery_full: " + " | ".join(shots["full"]))
    lines.append(f"summary: {course['summary']}")
    credit = f"Student: {student}"
    if assignment:
        credit += f" | Assignment: {assignment}"
    lines += [
        f"authors: {credit}",
        f"student: {student}",
        f"course: {course_slug}",
        "---",
        "",
        body,
        "",
    ]
    return "\n".join(lines)


def replace_between(text: str, start: str, end: str, block: str, where: str) -> str:
    pattern = re.compile(re.escape(start) + r"[\s\S]*?" + re.escape(end))
    if not pattern.search(text):
        sys.exit(f"{where}: markers {start!r} … {end!r} not found")
    return pattern.sub(lambda _m: f"{start}\n{block}\n{end}", text, count=1)


def sidebar_course_links(index_text: str) -> dict[str, str]:
    """Course slug -> the link text the sidebar already uses for it."""
    # Sidebar anchors start with href; the wall's tiles start with class="tile"
    # and hold an <img>, not text, so they are not matched.
    return dict(re.findall(r'<a href="#project/(arch-\d+)" data-project="[^"]+">([^<\n]+)</a>', index_text))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Report, write nothing.")
    args = parser.parse_args()

    table = read_table()
    index_path = ROOT / "index.html"
    index_text = index_path.read_text(encoding="utf-8")
    course_links = sidebar_course_links(index_text)

    sidebar: list[str] = []
    sources: list[str] = []
    pages_written = 0
    pictures = 0

    # Sidebar order follows the course links as they stand.
    ordered = sorted(COURSES.items(), key=lambda kv: html.unescape(course_links.get(kv[1], kv[1])).lower())
    for folder_name, course_slug in ordered:
        folder = SOURCES / folder_name
        if not folder.is_dir():
            print(f"  [!] missing source folder {folder_name}", file=sys.stderr)
            continue
        course_meta, body = front_matter(PROJECTS / f"{course_slug}.md")
        students = collect(folder)
        print(f"  {course_slug}: {len(students)} students")

        sidebar.append(
            f'          <a href="#project/{course_slug}" data-project="{course_slug}">'
            f'{course_links.get(course_slug, course_meta.get("title", course_slug))}</a>'
        )
        sidebar.append('          <div class="students">')
        for student, shots in sorted(students.items()):
            slug = f"{course_slug}-{slugify(student)}"
            table.setdefault((course_slug, student), "")
            assignment = table[(course_slug, student)]
            student_dir = OUT / course_slug / slugify(student)
            published = export(student_dir, shots, args.dry_run)
            pictures += sum(len(v) for v in published.values())
            cover = f"{student_dir.relative_to(ROOT).as_posix()}/hero.jpg"
            text = page(course_meta, body, student, assignment, course_slug, cover, published)
            if not args.dry_run:
                (PROJECTS / f"{slug}.md").write_text(text, encoding="utf-8")
            pages_written += 1
            note = f"  assignment: {assignment}" if assignment else "  (no assignment named)"
            print(f"    {student:<40} grid {len(published['grid']):2d}  full {len(published['full']):2d}{note}")
            sidebar.append(
                f'            <a href="#project/{slug}" data-project="{slug}" '
                f'data-course="{course_meta.get("title", course_slug)}">{student}</a>'
            )
            sources.append(f'  "{slug}": "content/projects/{slug}.md",')
        sidebar.append("          </div>")

    if args.dry_run:
        print(f"\n  would write {pages_written} pages and {pictures} pictures")
        return

    write_table(table)
    index_path.write_text(
        replace_between(index_text, "          <!-- teaching:start -->", "          <!-- teaching:end -->",
                         "\n".join(sidebar), "index.html"),
        encoding="utf-8",
    )
    script_path = ROOT / "script.js"
    script_path.write_text(
        replace_between(script_path.read_text(encoding="utf-8"), "  // --- teaching:start ---",
                         "  // --- teaching:end ---", "\n".join(sources), "script.js"),
        encoding="utf-8",
    )
    blanks = sum(1 for v in table.values() if not v)
    print(f"\n  {pages_written} pages, {pictures} pictures; {blanks} assignment name(s) still blank in {TABLE.name}")
    print("  next: python tools/guard_images.py && python tools/build_wall.py")


if __name__ == "__main__":
    main()

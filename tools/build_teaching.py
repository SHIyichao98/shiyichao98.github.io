"""Build one page per student project from the teaching source folders.

The teaching section used to be one page per course, with every student's
work on it. It is now one page per student project, still filed under the
course: the page keeps the course number, term and description, and adds a
line naming the student and the assignment. A course can have a grid of
square tiles and a run of full-width figures, from two source subfolders.

    assets/teaching_work_samples/<course folder>/<Student Name>/
        project.md   -> what the page says: assignment, summary, text
        grids/ 01.jpg   -> square tiles, opening in the lightbox
        full/  01.jpg   -> shown whole, one per row

One folder per student, named as the name should appear on the page; a team
is one folder ("Hang Xu & Dingkun Hu"). Files are ordered by the number in
their name, whatever else the name says. Anything at the course level that is
not a student folder is ignored.

A student with more than one project has one folder per project at the
course level, named "Student Name_Project Name", each with its own grids/,
full/ and project.md:

    Lucas Nagel_Final Drawings/grids/01.jpg
    Lucas Nagel_Physical Models/grids/01.jpg

The part after the underscore names the project and is the assignment on
the page unless project.md says otherwise. Each project is its own page and
its own tile on the course page. (Project subfolders inside a student folder
are read too, for the same result.)

Pages and pictures for folders that no longer exist are removed on each
build, so renaming a folder moves the page rather than duplicating it.

project.md is the student's own account, written by hand:

    ---
    assignment: Form Study
    summary: One sentence under the title.
    ---

    ## Project

    A few paragraphs about the work.

A folder without one gets a blank template written into it on the next
build, so the place to write is never in doubt. Until it is filled in, the
page shows the course header, the student's name and the pictures, and
nothing it would have to make up. The course's own description stays on the
course page, linked from every student page.

What this writes:

    assets/site_images/teaching/<course>/<student>/grid/NN.jpg  (+ thumbs/)
    assets/site_images/teaching/<course>/<student>/full/NN.jpg
    assets/site_images/teaching/<course>/<student>/hero.jpg
    content/projects/<course>-<student>.md
    index.html      the Teaching section of the sidebar: three category links,
                    each a cut of the homepage teaching wall
    script.js       the projectSources entries, between their markers

The course pages (arch-2017.md and the rest) keep their own text; their
picture wall is written by tools/build_wall.py and is the same wall the
course's category shows, each tile a link to a student's page. Pictures open
in the lightbox only on the student's own page. A student with no folder has
no page, and so appears nowhere.

Run tools/guard_images.py afterwards: it stamps each new picture with the
student's name, read from the page it belongs to.

    python tools/build_teaching.py
    python tools/build_teaching.py --dry-run
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
import time
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
NOTE = "project.md"
NOTE_TEMPLATE = """---
assignment:
summary:
---

## Project

"""

# Source folder -> course slug. The course page (content/projects/<slug>.md)
# supplies the title, term, description and the text of every student page.
COURSES = {
    "2026Spring_ARCH_2017": "arch-2017",
    "2023&2024Fall_Arch2020": "arch-2020",
    "2025Fall_Arch_6020": "arch-6020",
    "2025Spring_Arch_8833": "arch-8833",
}

# The sidebar lists three categories, not four courses and not thirty
# students. A category link shows the teaching wall cut to that category's
# tiles; a tile opens the student's page. (slug, title, span, summary, course
# slugs -- span and summary are kept for the kicker and any future hub.)
CATEGORIES = (
    (
        "teaching-computational",
        "Computational Design & Digital Fabrication",
        "2023 Fall \u2013 2026 Fall",
        "Parametric modeling, visual scripting, rule-based design, simulation and fabrication, "
        "taught across the undergraduate and graduate Media + Modeling courses.",
        ("arch-2020", "arch-6020"),
    ),
    (
        "teaching-studio",
        "Architectural Design Studio",
        "2026 Spring",
        "Undergraduate design studio integrating precedent, typology, representation, physical "
        "making, and AI-assisted design workflows.",
        ("arch-2017",),
    ),
    (
        "teaching-ai",
        "AI Enhanced Architecture Design",
        "2025 Spring",
        "Generative image workflows, model training, and the integration of AI with parametric "
        "design tools in an advanced architecture course.",
        ("arch-8833",),
    ),
)
INSTRUCTOR = "Graduate Student Instructor, PhD student | School of Architecture, Georgia Institute of Technology"
QUALITY = 88

# The number that orders a file: "03.jpg", "Lucas Nagel_03.jpg", "img-3.png".
NUMBER = re.compile(r"(\d+)(?!.*\d)")
NOT_STUDENTS = {"grids", "full", "hero_image"}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def display_name(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip()


def split_folder(name: str) -> tuple[str, str]:
    """'Lucas Nagel_Final Drawings' -> ('Lucas Nagel', 'Final Drawings');
    'Lucas Nagel' -> ('Lucas Nagel', '')."""
    student, _, project = name.partition("_")
    # Underscores inside the project part stand for spaces: Building_System.
    return display_name(student), display_name(project.replace("_", " "))


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


def read_note(student_dir: Path, dry: bool) -> tuple[str, str, str]:
    """(assignment, summary, body) from the student's project.md.

    A missing note is written as a blank template. A body that is only the
    template's heading counts as empty, so an unfilled page is not published
    with a heading over nothing.
    """
    note = student_dir / NOTE
    if not note.exists():
        if not dry:
            note.write_text(NOTE_TEMPLATE, encoding="utf-8")
        return "", "", ""
    meta, body = front_matter(note)
    if body.strip() in {"", "## Project"}:
        body = ""
    return meta.get("assignment", "").strip(), meta.get("summary", "").strip(), body.strip()


def pictures_in(project_dir: Path) -> dict[str, list[Path]]:
    """{"grid": [...], "full": [...]} from a folder's grids/ and full/, in number order."""
    shots: dict[str, list[Path]] = {"grid": [], "full": []}
    for kind, sub in (("grid", "grids"), ("full", "full")):
        source = project_dir / sub
        if not source.is_dir():
            continue
        files = [p for p in source.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES]
        keyed = []
        for path in files:
            match = NUMBER.search(path.stem)
            keyed.append((int(match.group(1)) if match else 10**6, path.name, path))
        shots[kind] = [p for _n, _name, p in sorted(keyed)]
    return shots


def collect(folder: Path) -> list[tuple[str, str, Path, dict[str, list[Path]]]]:
    """(student, project, project folder, pictures) for every project in a course.

    A student folder is one project unless it holds project subfolders, in
    which case each of those is one, and any pictures at the student level
    are one more with no project name.
    """
    out = []
    for student_dir in sorted(folder.iterdir()):
        if not student_dir.is_dir() or student_dir.name in NOT_STUDENTS or student_dir.name.startswith("_"):
            continue
        name, project = split_folder(student_dir.name)
        found = False
        own = pictures_in(student_dir)
        if own["grid"] or own["full"]:
            out.append((name, project, student_dir, own)); found = True
        for project_dir in sorted(student_dir.iterdir()):
            if not project_dir.is_dir() or project_dir.name in NOT_STUDENTS:
                continue
            shots = pictures_in(project_dir)
            if shots["grid"] or shots["full"]:
                out.append((name, display_name(project_dir.name), project_dir, shots)); found = True
            else:
                print(f"  [!] {project_dir.relative_to(SOURCES)}: no grids/ or full/ pictures", file=sys.stderr)
        if not found:
            print(f"  [!] {student_dir.relative_to(SOURCES)}: no pictures", file=sys.stderr)
    return out


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


def page(course: dict[str, str], student: str, project: str, note: tuple[str, str, str], course_slug: str,
         cover: str, shots: dict[str, list[str]]) -> str:
    """A student page: the course as header, the student's own note as body."""
    assignment, summary, body = note
    # A named project folder names the assignment unless the note says otherwise.
    assignment = assignment or project
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
    if summary:
        lines.append(f"summary: {summary}")
    credit = f"Student: **{student}**"
    if assignment:
        credit += f" | Assignment: {assignment}"
    lines += [
        f"authors: {credit}",
        f"links: [About the course](#project/{course_slug})",
        f"student: {student}",
        f"project: {project}",
        f"course: {course_slug}",
        "---",
        "",
    ]
    # A short account of the course, and of my place in it, ahead of the
    # student's own note. Read from the course page's brief field, so the
    # wording lives with the course, not in this script.
    if course.get("brief"):
        lines += ["## Course", "", course["brief"], ""]
    if body:
        lines += [body, ""]
    return "\n".join(lines)


def category_page(slug: str, title: str, span: str, summary: str, courses: list[tuple[dict, str]],
                  hub: list[str]) -> str:
    """A hub: the category's courses described in turn, then the student tiles."""
    numbers = " \u00b7 ".join(meta.get("title", "") for meta, _body in courses)
    lines = [
        "---",
        f"title: {title}",
        f"year: {span}",
        "type: Teaching",
        f"subtitle: {numbers}",
        f"summary: {summary}",
        f"authors: {INSTRUCTOR}",
        "hub: " + " | ".join(hub),
        "---",
        "",
    ]
    for meta, body in courses:
        if len(courses) > 1:
            # Each course under its own heading, its sections a level down.
            lines.append(f"## {meta.get('title', '')} \u00b7 {meta.get('subtitle', '')} ({meta.get('year', '')})")
            lines.append("")
            lines.append(re.sub(r"^## ", "### ", body, flags=re.M))
        else:
            lines.append(body)
        lines.append("")
    return "\n".join(lines)


GALLERY_FIELDS = ("gallery", "gallery_credits", "gallery_full", "gallery_full_credits", "credit_label", "credit")


def write_course_hub(course_slug: str, hub: list[str]) -> None:
    """Swap the course page's own gallery for a hub of its student projects."""
    path = PROJECTS / f"{course_slug}.md"
    text = path.read_text(encoding="utf-8")
    head, block, body = text.split("---", 2)
    kept = [line for line in block.strip("\n").splitlines()
            if line.split(":", 1)[0].strip() not in GALLERY_FIELDS + ("hub",)]
    kept.append("hub: " + " | ".join(hub))
    path.write_text(f"---\n" + "\n".join(kept) + "\n---" + body, encoding="utf-8")


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
    parser.add_argument("--pages-only", action="store_true",
                        help="Rewrite pages, sidebar and router; leave pictures already exported alone.")
    args = parser.parse_args()

    index_path = ROOT / "index.html"
    index_text = index_path.read_text(encoding="utf-8")

    sidebar: list[str] = []
    sources: list[str] = []
    pages_written = 0
    pictures = 0
    notes_blank = 0
    produced_pages: set[Path] = set()
    produced_dirs: set[Path] = set()
    folder_of = {slug: name for name, slug in COURSES.items()}

    for cat_slug, cat_title, span, summary, course_slugs in CATEGORIES:
        # A category is a cut of the teaching wall, not a page: the link
        # filters the wall to the category's tiles, each of which opens a
        # student's project.
        sidebar.append(
            f'          <a href="#{cat_slug}" data-wall="teaching" data-category="{cat_slug}">'
            f'{html.escape(cat_title)}</a>'
        )
        for course_slug in course_slugs:
            folder = SOURCES / folder_of[course_slug]
            if not folder.is_dir():
                print(f"  [!] missing source folder {folder}", file=sys.stderr)
                continue
            course_meta, _course_body = front_matter(PROJECTS / f"{course_slug}.md")
            # The kicker on a student page names the category, as the sidebar does.
            course_meta = {**course_meta, "type": f"Teaching / {cat_title}"}
            hub: list[str] = []
            projects = collect(folder)
            print(f"  {course_slug}: {len(projects)} projects")
            for student, project, project_dir, shots in projects:
                slug = f"{course_slug}-{slugify(student)}" + (f"-{slugify(project)}" if project else "")
                note = read_note(project_dir, args.dry_run)
                notes_blank += not any(note)
                # Output folder is the slug less the course, so the wall's pick
                # matcher reads the project straight off the path.
                student_dir = OUT / course_slug / slug[len(course_slug) + 1:]
                if args.dry_run or (args.pages_only and student_dir.is_dir()):
                    published = export(student_dir, shots, dry=True)
                else:
                    published = export(student_dir, shots, dry=False)
                    pictures += sum(len(v) for v in published.values())
                cover = f"{student_dir.relative_to(ROOT).as_posix()}/hero.jpg"
                text = page(course_meta, student, project, note, course_slug, cover, published)
                if not args.dry_run:
                    (PROJECTS / f"{slug}.md").write_text(text, encoding="utf-8")
                produced_pages.add(PROJECTS / f"{slug}.md")
                produced_dirs.add(student_dir)
                pages_written += 1
                state = f"  assignment: {note[0]}" if note[0] else ("  (note filled, no assignment)" if any(note) else "  (project.md blank)")
                label = f"{student} \u00b7 {project}" if project else student
                print(f"    {label:<40} grid {len(published['grid']):2d}  full {len(published['full']):2d}{state}")
                sources.append(f'  "{slug}": "content/projects/{slug}.md",')
                hub.append(f"{slug}::{label}::{cover}")
            # The course page's hub is written by tools/build_wall.py from the
            # category's wall, so a course page shows the same pictures as
            # its category view. Nothing to do here.
        # The hub pages this once wrote are retired; clear a leftover.
        if not args.dry_run:
            (PROJECTS / f"{cat_slug}.md").unlink(missing_ok=True)

    if args.dry_run:
        print(f"\n  would write {pages_written} pages and {pictures} pictures")
        return

    # A folder renamed or removed since the last build leaves a page and a
    # picture folder behind; take them out, or the old address keeps working
    # beside the new one.
    stale = 0
    for md in PROJECTS.glob("arch-*-*.md"):
        if md not in produced_pages:
            md.unlink(); stale += 1
    for course_slug in COURSES.values():
        course_out = OUT / course_slug
        if not course_out.is_dir():
            continue
        for sub in course_out.iterdir():
            if sub.is_dir() and sub not in produced_dirs:
                # OneDrive holds a lock on a folder for a moment after touching
                # it; try a few times, then leave it and say so rather than
                # stop before the sidebar and router are written.
                for attempt in range(5):
                    try:
                        shutil.rmtree(sub); stale += 1
                        break
                    except PermissionError:
                        time.sleep(1)
                else:
                    print(f"  [!] could not remove {sub.relative_to(ROOT)}; delete it by hand", file=sys.stderr)
    if stale:
        print(f"  cleared {stale} stale page(s)/folder(s)")

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
    print(f"\n  {pages_written} pages, {pictures} pictures; {notes_blank} project.md still blank")
    print("  next: python tools/guard_images.py && python tools/build_wall.py")


if __name__ == "__main__":
    main()

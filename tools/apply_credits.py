"""Write the names collected in tools/credits.csv into the course pages.

Reads the `student` column and sets `gallery_credits` on each course page, in
the order the gallery lists its images. A blank cell means that image carries
no name, which is the only way to leave one uncredited while naming its
neighbours, so blanks are kept rather than dropped.

    python tools/apply_credits.py            # write
    python tools/apply_credits.py --dry-run  # report, change nothing
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "tools", "credits.csv")


def write_text(path: str, text: str) -> None:
    # The repo lives inside OneDrive, which intermittently holds a write lock.
    for _ in range(30):
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            return
        except PermissionError:
            time.sleep(1)
    sys.exit(f"could not write {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing.")
    args = parser.parse_args()

    if not os.path.exists(CSV):
        sys.exit(f"{CSV} not found — run tools/build_credit_sheet.py first")

    by_course: dict[str, dict[int, str]] = {}
    with open(CSV, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            by_course.setdefault(row["course"], {})[int(row["index"])] = (row["student"] or "").strip()

    for slug, entries in sorted(by_course.items()):
        path = os.path.join(ROOT, "content", "projects", f"{slug}.md")
        if not os.path.exists(path):
            print(f"  {slug}: no such page, skipped")
            continue
        text = open(path, encoding="utf-8").read()

        gallery = re.search(r"^gallery: (.+)$", text, re.M)
        if not gallery:
            print(f"  {slug}: no gallery, skipped")
            continue
        count = len([e for e in gallery.group(1).split("|") if e.strip()])

        names = [entries.get(i, "") for i in range(count)]
        named = sum(1 for n in names if n)
        if not named:
            print(f"  {slug}: no names given, left alone")
            continue

        # Trailing blanks say nothing that a shorter list does not.
        while names and not names[-1]:
            names.pop()
        line = "gallery_credits: " + " | ".join(names)

        if re.search(r"^gallery_credits: .*$", text, re.M):
            updated = re.sub(r"^gallery_credits: .*$", line, text, count=1, flags=re.M)
        else:
            updated = re.sub(r"^(gallery: .+)$", r"\1\n" + line.replace("\\", "\\\\"), text, count=1, flags=re.M)

        print(f"  {slug}: {named} of {count} images named")
        if not args.dry_run and updated != text:
            write_text(path, updated)

    if args.dry_run:
        print("\n  dry run — nothing written")
    else:
        print("\n  done — remember to bump the asset version")


if __name__ == "__main__":
    main()

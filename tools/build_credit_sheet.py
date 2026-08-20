"""Build the sheet used to name the student behind each teaching image.

The site has no per-image authorship anywhere, and the source filenames only
carry a name for some of the courses, so the mapping has to be typed once by
hand. This writes two ways to do that:

  tools/credits.html  a page of thumbnails, each with a box to type into. It
                      embeds the images, so it opens by double-clicking with
                      no server running, and it remembers what has been typed.
  tools/credits.csv   the same rows for anyone who would rather use Excel.

Names already readable from a source filename are filled in as a starting
point; every one of them still needs checking, since the match is made by
image content rather than by any recorded fact.

    python tools/build_credit_sheet.py

Then either type into the page and copy the block it produces, or fill the
`student` column of the CSV and run tools/apply_credits.py.
"""

from __future__ import annotations

import base64
import csv
import glob
import html
import io
import json
import os
import re
import sys
import time

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Course page -> the folder its images were exported from. The folder is only
# used to recover a name from a filename; a course with no folder still gets
# its rows, just with nothing filled in.
COURSES = [
    ("arch-6020", "Advanced Computational Design", "assets/teaching_work_samples/2025Fall_Arch_6020"),
    ("arch-2017", "Architectural Design Studio", "assets/teaching_work_samples/2026Spring_ARCH_2017"),
    ("arch-2020", "Computational Design Foundations", "assets/teaching_work_samples/2023&2024Fall_Arch2020"),
    ("arch-8833", "AI & Computational Design", "assets/teaching_work_samples/2025Spring_Arch_8833"),
]

THUMB = 190
# A source filename may name its student three ways. Only the first is written
# by a person who knew the answer; the other two are machine exports that
# mangle the name, so what they yield is a guess and is flagged as one.
PATTERNS = (
    re.compile(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)+)_\d"),  # Sydney Wetterhan_01.jpg — typed by hand
    re.compile(r"^([A-Za-z]+)_([A-Za-z]+)-"),           # Nguyen_Andy-ARCH2017-...
    re.compile(r"^([a-z]{4,})_\d+_\d+_", re.ASCII),     # wetterhansydneymarie_1051586_...
)


def open_for_write(path: str, **kwargs):
    """Open for writing, waiting out a lock.

    The repo lives inside OneDrive, and the sheet is meant to be edited in
    Excel, so either can be holding the file when this runs.
    """
    for attempt in range(20):
        try:
            return open(path, "w", **kwargs)
        except PermissionError:
            if attempt == 0:
                print(f"  {os.path.basename(path)} is locked — waiting (close it in Excel if it is open)")
            time.sleep(1)
    sys.exit(f"could not write {path}: still locked after 20s")


def dhash(path: str, size: int = 8) -> int:
    image = Image.open(path).convert("L").resize((size + 1, size))
    pixels = list(image.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            here = pixels[row * (size + 1) + col]
            right = pixels[row * (size + 1) + col + 1]
            bits = bits << 1 | (here > right)
    return bits


def guess_name(filename: str) -> tuple[str, bool]:
    """What to credit for a source file, and whether it had to be guessed.

    A name typed into the filename by hand is taken at its word and used in
    full: whoever wrote it knew the student and decided to name them. A name
    recovered from a machine export is reduced to initials instead, because
    the export mangles it and because coursework is an education record — a
    full name beside it identifies its author to every visitor. Either way the
    filename stays in this sheet's source column, which never leaves the
    machine, so a person can always see who a row belongs to.
    """
    stem = os.path.basename(filename)

    match = PATTERNS[0].match(stem)
    if match:
        return match.group(1), False

    match = PATTERNS[1].match(stem)
    if match:
        # Lastname_Firstname- : initials read first name, then last.
        return f"{match.group(2)[0]}{match.group(1)[0]}".upper(), True

    match = PATTERNS[2].match(stem)
    if match:
        # A run-together lastnamefirstname cannot be split reliably, so this
        # yields one letter and needs a person to finish it.
        return match.group(1)[0].upper(), True

    return "", False


def gallery_of(slug: str) -> list[str]:
    path = os.path.join(ROOT, "content", "projects", f"{slug}.md")
    text = open(path, encoding="utf-8").read()
    match = re.search(r"^gallery: (.+)$", text, re.M)
    if not match:
        return []
    return [entry.strip() for entry in match.group(1).split("|") if entry.strip()]


def existing_credits(slug: str) -> list[str]:
    path = os.path.join(ROOT, "content", "projects", f"{slug}.md")
    text = open(path, encoding="utf-8").read()
    match = re.search(r"^gallery_credits: (.*)$", text, re.M)
    if not match:
        return []
    return [entry.strip() for entry in match.group(1).split("|")]


def thumb_uri(path: str) -> str:
    image = Image.open(path)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail((THUMB, THUMB), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=72, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def collect() -> list[dict]:
    rows = []
    for slug, title, source_dir in COURSES:
        gallery = gallery_of(slug)
        if not gallery:
            print(f"  {slug}: no gallery, skipped")
            continue

        # Recover a filename per image by content, since export renumbers and
        # the counts do not always line up. Recursive: a course whose files
        # have been renamed by hand keeps them in a subfolder of its own.
        sources = sorted(
            path
            for path in glob.glob(os.path.join(ROOT, source_dir, "**", "*.*"), recursive=True)
            if os.path.isfile(path)
        )
        hashes = {}
        for path in sources:
            try:
                hashes[path] = dhash(path)
            except Exception:
                continue

        found = existing_credits(slug)
        for index, image in enumerate(gallery):
            full = os.path.join(ROOT, image)
            source, guess, distance, uncertain = "", "", None, False
            if os.path.exists(full) and hashes:
                here = dhash(full)
                source, distance = min(
                    ((k, bin(v ^ here).count("1")) for k, v in hashes.items()),
                    key=lambda pair: pair[1],
                )
                if distance <= 10:
                    guess, uncertain = guess_name(source)
                    source = os.path.basename(source)
                else:
                    source, guess, uncertain = "", "", False
            rows.append(
                {
                    "slug": slug,
                    "title": title,
                    "index": index,
                    "image": image,
                    "source": source,
                    "student": (found[index] if index < len(found) else "") or guess,
                    "guessed": uncertain and not (index < len(found) and found[index]),
                    "thumb": thumb_uri(full) if os.path.exists(full) else "",
                }
            )
        print(f"  {slug}: {len(gallery)} images, {sum(1 for r in rows if r['slug'] == slug and r['student'])} pre-filled")
    return rows


PAGE = """<!doctype html>
<meta charset="utf-8" />
<title>Student credits</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; padding: 32px clamp(16px, 4vw, 56px) 96px;
         font: 15px/1.5 "Helvetica Neue", Arial, sans-serif; color: #151515; background: #fff; }
  h1 { font-size: 1.5rem; margin: 0 0 6px; }
  .lede { color: #6b6b6b; max-width: 60ch; margin: 0 0 28px; }
  h2 { font-size: 1.1rem; margin: 40px 0 4px; }
  .count { color: #6b6b6b; font-size: 0.85rem; margin: 0 0 14px; }
  .rows { display: grid; gap: 10px; }
  .row { display: grid; grid-template-columns: 200px 1fr; gap: 16px; align-items: center;
         padding: 8px; border: 1px solid #e3e3e3; }
  .row img { display: block; width: 100%; height: auto; background: #f4f4f4; }
  .meta { font-size: 0.78rem; color: #6b6b6b; word-break: break-all; margin: 0 0 6px; }
  input { width: 100%; max-width: 460px; padding: 8px 10px; font: inherit;
          border: 1px solid #c9c9c9; background: #fff; }
  input.guessed { border-color: #d08a00; background: #fffaf0; }
  .flag { color: #d08a00; font-size: 0.78rem; margin: 4px 0 0; }
  footer { position: sticky; bottom: 0; background: #fff; border-top: 2px solid #151515;
           padding: 16px 0 0; margin-top: 40px; }
  textarea { width: 100%; height: 190px; font: 12px/1.5 ui-monospace, Consolas, monospace;
             padding: 10px; border: 1px solid #c9c9c9; }
  button { font: inherit; padding: 9px 16px; border: 1px solid #151515; background: #151515;
           color: #fff; cursor: pointer; }
  button.ghost { background: #fff; color: #151515; }
</style>
<h1>Student credits</h1>
<p class="lede">Type the student's name next to their image. What you type is kept in this
browser, so you can close the page and come back. When you are done, press
<strong>Build</strong> and send the block back &mdash; it goes straight into the project files.
Boxes with an amber edge were guessed from a source filename and need checking.
Leave a box empty to show no name on that image.</p>
__SECTIONS__
<footer>
  <p><button onclick="build()">Build</button>
     <button class="ghost" onclick="copyOut()">Copy</button>
     <button class="ghost" onclick="clearAll()">Clear all</button>
     <span id="status" style="color:#6b6b6b;font-size:0.85rem;margin-left:10px"></span></p>
  <textarea id="out" readonly placeholder="Press Build"></textarea>
</footer>
<script>
const ROWS = __ROWS__;
const KEY = "portfolio-credits";
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");

document.querySelectorAll("input[data-key]").forEach((box) => {
  if (saved[box.dataset.key] !== undefined) box.value = saved[box.dataset.key];
  box.addEventListener("input", () => {
    box.classList.remove("guessed");
    saved[box.dataset.key] = box.value;
    localStorage.setItem(KEY, JSON.stringify(saved));
    document.getElementById("status").textContent = "saved";
  });
});

function build() {
  const bySlug = {};
  ROWS.forEach((row) => {
    const box = document.querySelector(`input[data-key="${row.slug}:${row.index}"]`);
    (bySlug[row.slug] ||= [])[row.index] = (box.value || "").trim();
  });
  const lines = Object.entries(bySlug).map(([slug, names]) => {
    const filled = Array.from(names, (n) => n || "");
    return `${slug}.md\\ngallery_credits: ${filled.join(" | ")}`;
  });
  document.getElementById("out").value = lines.join("\\n\\n");
  const total = ROWS.length;
  const done = ROWS.filter((r) => {
    const b = document.querySelector(`input[data-key="${r.slug}:${r.index}"]`);
    return b && b.value.trim();
  }).length;
  document.getElementById("status").textContent = `${done} of ${total} named`;
}

function copyOut() {
  const out = document.getElementById("out");
  if (!out.value) build();
  navigator.clipboard.writeText(out.value).then(
    () => (document.getElementById("status").textContent = "copied"),
    () => {
      out.removeAttribute("readonly"); out.select();
      document.getElementById("status").textContent = "press Ctrl+C";
    },
  );
}

function clearAll() {
  if (!confirm("Clear every name typed on this page?")) return;
  localStorage.removeItem(KEY);
  document.querySelectorAll("input[data-key]").forEach((b) => (b.value = ""));
  document.getElementById("status").textContent = "cleared";
}
</script>
"""


def main() -> None:
    rows = collect()
    if not rows:
        sys.exit("nothing to write")

    sections = []
    for slug, title, _ in COURSES:
        mine = [r for r in rows if r["slug"] == slug]
        if not mine:
            continue
        cards = []
        for row in mine:
            flag = '<p class="flag">guessed from the filename &mdash; please check</p>' if row["guessed"] else ""
            source = html.escape(row["source"] or "source unknown")
            cards.append(
                f'''      <div class="row">
        <img src="{row['thumb']}" alt="" />
        <div>
          <p class="meta">{row['index'] + 1}. {html.escape(os.path.basename(row['image']))} &mdash; {source}</p>
          <input type="text" data-key="{slug}:{row['index']}" value="{html.escape(row['student'])}"
                 class="{'guessed' if row['guessed'] else ''}" placeholder="Student name" />
          {flag}
        </div>
      </div>'''
            )
        sections.append(
            f'''<section>
  <h2>{html.escape(title)} <span style="color:#6b6b6b;font-weight:400">({slug})</span></h2>
  <p class="count">{len(mine)} images</p>
  <div class="rows">
{chr(10).join(cards)}
  </div>
</section>'''
        )

    page = PAGE.replace("__SECTIONS__", "\n".join(sections)).replace(
        "__ROWS__",
        json.dumps([{k: r[k] for k in ("slug", "index")} for r in rows]),
    )
    out_html = os.path.join(ROOT, "tools", "credits.html")
    with open_for_write(out_html, encoding="utf-8") as handle:
        handle.write(page)

    out_csv = os.path.join(ROOT, "tools", "credits.csv")
    with open_for_write(out_csv, encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["course", "index", "image", "source_file", "student"])
        for row in rows:
            writer.writerow([row["slug"], row["index"], row["image"], row["source"], row["student"]])

    size = os.path.getsize(out_html) / 1024
    print(f"\n  tools/credits.html  {size:.0f} KB  ({len(rows)} rows, images embedded)")
    print(f"  tools/credits.csv   {len(rows)} rows")


if __name__ == "__main__":
    main()

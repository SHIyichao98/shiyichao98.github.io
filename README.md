# Yichao Shi — Academic Portfolio

**Live site: https://shiyichao98.github.io/**

Static site, no build step. `index.html` is the image index; every project page
is a Markdown file rendered in the browser by `script.js`.

## Where things live

| | |
|---|---|
| `index.html` | Image index (the curated wall) and the sidebar that lists every project |
| `script.js` | Markdown loader, routing, image grid, lightbox |
| `styles.css` | All styling |
| `content/projects/*.md` | One file per project: front matter plus body copy |
| `assets/site_images/` | **Published** web images. This is the only image folder that ships |
| `tools/` | Export and maintenance scripts |

Source material stays local and is gitignored: `assets/research_projects/`,
`assets/my_design_works/`, `assets/index_of_images/`,
`assets/teaching_work_samples/`. Only exports under `assets/site_images/` are
published.

## History, and how to trace it back

The site used to live at `https://shiyichao98.github.io/portfolio/`, from the
repository `SHIyichao98/portfolio`. That repository is now **private** and its
Pages site is switched off, so the old URL returns 404 and any link to it needs
updating.

It was retired for two reasons: the URL carried an extra `/portfolio/` path
segment, and the repository tracked 33 files of student coursework whose
filenames contained real student names, publicly downloadable and never
referenced by the site.

This repository starts from a fresh commit rather than carrying that history
over, so the student files are gone from the published record entirely, along
with 43 MB of large blobs left behind by images deleted during earlier work.

**The old repository still exists and is still yours.** It is private, but the
full commit history is intact, and those commit messages record why most of the
decisions here were made — the colour management work, the layout changes, the
LOOPS restructuring. To read it:

```
https://github.com/SHIyichao98/portfolio
```

## Local preview

```powershell
python -m http.server 5500
```

Then open `http://127.0.0.1:5500/`.

## Adding or updating images

Put full-resolution sources in the matching local folder, then export:

```powershell
python tools\export_web_images.py "assets\my_design_works\PROJECT" --out assets\site_images\design\PROJECT
```

The exporter reads through each file's ICC profile. That matters: several
sources are CMYK press files or tagged Apple RGB and Display P3, and converting
them without their profile shifts colour visibly. It never scales an image up;
if a source is too small it says so rather than inventing pixels.

Targets come from `styles.css`: 2240x1400 for the full image, 1200x1200 square
for a cover, 720x720 square for a grid tile.

A `hero_image/` subfolder inside a source folder designates the cover; otherwise
pass `--hero FILENAME` or let it pick the largest file.

### The homepage wall

The wall is curated by hand, not one tile per project. Put the images you want
on it in `assets/index_of_images/` under any filename, then:

```powershell
python tools\build_index_tiles.py assets\index_of_images
```

Each pick is matched back to its project by image content rather than filename,
cropped square, and interleaved so no two tiles from the same project sit next
to each other. Update the tiles and alt text in `index.html` afterwards.

### After changing any published file

```powershell
python tools\bump_version.py
```

Published filenames are stable and GitHub Pages sends `max-age=600`, so without
a version stamp a returning visitor keeps their cached copy and can end up
running new markup against old CSS. This raises the stamp in `index.html` and
`script.js`, which covers everything the page fetches at runtime.

## Adding a project

1. Export images to `assets/site_images/<section>/<slug>/`.
2. Create `content/projects/<slug>.md` with `title`, `year`, `type`, `cover`,
   `gallery`, `summary`.
3. Add the slug to `projectSources` in `script.js`.
4. Add a sidebar link in `index.html`.
5. Optionally add a tile to the wall.

Markdown supports `## Heading`, `### Subheading`, paragraphs, bullet lists,
`![Caption](path)`, `[Link](url)` and `**bold**`.

## Publishing

GitHub Pages serves `main` at the repository root. `.nojekyll` keeps Jekyll out
of the way. Pushing to `main` deploys; a build takes about a minute.

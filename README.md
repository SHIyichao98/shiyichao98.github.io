# Academic Portfolio

This is a static academic portfolio and research archive. It is intentionally
text-first: closer to a personal faculty / researcher homepage than a commercial
portfolio landing page.

## Files

- `index.html`: page content, research interests, projects, writing, CV, contact.
- `styles.css`: typography, layout, spacing, and responsive behavior.
- `script.js`: loads Markdown project pages and controls image galleries.
- `assets/site_images/`: compressed web images used by the public site.
- `assets/research_projects/`: local source archive, ignored by Git.

## Local Preview

Run a local server from this directory:

```powershell
python -m http.server 5500
```

Then open:

```text
http://127.0.0.1:5500/
```

Keep the PowerShell window open while previewing. Closing it stops the preview
server.

## What To Replace

1. Replace `Shiyi` with your preferred academic name.
2. Replace `your.email@example.com`, GitHub, and LinkedIn links.
3. Update the affiliation line under the name.
4. Replace the three research questions with your real interests.
5. Replace project descriptions with your actual research, design, or coding work.
6. Add real publications, working papers, studio projects, or course notes.
7. Update the CV section with your education, lab, advisor, tools, and service.

## Project Pages With Markdown

Project detail pages are managed with Markdown files in:

```text
content/projects/
```

The image wall in `index.html` uses `data-project` values to decide which
Markdown file to open. For example:

```html
<a href="#project/arch-6020" data-project="arch-6020">
```

loads:

```text
content/projects/arch-6020.md
```

Each Markdown file can include front matter:

```markdown
---
title: Project Title
year: 2026
type: Teaching / research
cover: assets/path/to/cover.jpg
gallery: assets/path/01.jpg | assets/path/02.jpg | assets/path/03.jpg
summary: One sentence summary.
---
```

Supported Markdown patterns:

- `## Heading`
- `### Subheading`
- Paragraphs
- Bullet lists
- `![Caption](assets/path/to/image.jpg)`
- `[Link text](https://example.com)`
- `**bold text**`

To add a new project:

1. Put source material in `assets/research_projects/` if it should stay local.
2. Export or copy lightweight web images into `assets/site_images/`.
3. Create a new Markdown file in `content/projects/`.
4. Add the new slug to `projectSources` in `script.js`.
5. Add a tile in `index.html` with `data-project="your-slug"`.
6. Add the carousel images to the Markdown frontmatter with `gallery:`.

Keep the public image set small. GitHub Pages is happiest when project images
are compressed JPG/PNG files, not full paper folders, PSD files, Illustrator
files, or animation frame exports.

## Publishing With GitHub Pages

This site has no build step. It can be published for free with GitHub Pages as a
public repository. The current structure is ready for Pages:

- `index.html` is at the repository root.
- `styles.css`, `script.js`, and `assets/` use relative paths.
- `.nojekyll` is included so GitHub serves the files as plain static files.

### Option A: Project Site

This is like `https://karadagi.github.io/researcher_profile/`.

1. Create a public GitHub repository, for example `portfolio`.
2. Push this folder to that repository.
3. Open the repository on GitHub.
4. Go to `Settings` -> `Pages`.
5. Under `Build and deployment`, choose `Deploy from a branch`.
6. Select branch `main` and folder `/root`.
7. Save.

Your URL will usually be:

```text
https://YOUR-GITHUB-USERNAME.github.io/portfolio/
```

### Option B: Personal Homepage

Use this if you want the shorter URL:

```text
https://YOUR-GITHUB-USERNAME.github.io/
```

Create the repository with this exact name:

```text
YOUR-GITHUB-USERNAME.github.io
```

Then push these files to that repository and enable Pages from `main` + `/root`.

For Netlify or Vercel, import the GitHub repository and leave the build command
empty. The publish directory is `.`.

## Maintenance

- Keep the newest or most relevant work near the top.
- Use project entries like citations: year, title, short description, links.
- Add dates to notes and publications so the archive has a clear timeline.
- Check external links every few months.
- Keep raw research folders local and ignored by Git. Only publish selected web
  images from `assets/site_images/`.
- After replacing site images, run:

```powershell
python tools\enhance_site_images.py
```

This does a conservative web cleanup pass: resize very small images, normalize
contrast on diagram-like figures, and lightly sharpen photos/renders.

For paper screenshots that still look blurry, re-render the original PDF at a
higher resolution and choose a cleaner crop:

```powershell
python tools\render_pdf_pages.py "assets\research_projects\PROJECT\paper.pdf" ".codex-preview\pdf-pages" --dpi 360
```

Then crop the best page/figure into `assets/site_images/`, update the matching
Markdown gallery if needed, and run `python tools\enhance_site_images.py` again.

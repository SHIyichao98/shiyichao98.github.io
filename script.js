const projectSources = {
  "arch-6020": "content/projects/arch-6020.md",
  "arch-2017": "content/projects/arch-2017.md",
  "arch-2020": "content/projects/arch-2020.md",
  "arch-8833": "content/projects/arch-8833.md",
  "acadia-2022": "content/projects/acadia-2022.md",
  loops: "content/projects/loops.md",
  "caadria-2025-1": "content/projects/caadria-2025-1.md",
  "caadria-2025-2": "content/projects/caadria-2025-2.md",
  "caadria-2026": "content/projects/caadria-2026.md",
  "dcc-2024": "content/projects/dcc-2024.md",
  "dcc-2026": "content/projects/dcc-2026.md",
  "hcii-2024": "content/projects/hcii-2024.md",
  "simaud-2023": "content/projects/simaud-2023.md",
  "simaud-2026": "content/projects/simaud-2026.md",
  stadium: "content/projects/stadium.md",
  street: "content/projects/street.md",
  craftman: "content/projects/craftman.md",
  mars: "content/projects/mars.md",
  robotics: "content/projects/robotics.md",
  about: "content/projects/about.md",
  publications: "content/projects/publications.md",
  cv: "content/projects/cv.md",
};

// Bumped whenever a published file changes. Filenames here are stable
// (01.jpg stays 01.jpg), so without this a browser that has seen the site
// keeps its old copy indefinitely, and a returning visitor can end up running
// new markup against old CSS. index.html carries the same stamp on script.js
// and styles.css, so one bump reaches everything.
const ASSET_VERSION = "17";
const versioned = (url) => `${url}${url.includes("?") ? "&" : "?"}v=${ASSET_VERSION}`;

const gallery = document.querySelector(".gallery");
const detail = document.querySelector("#project-detail");
const detailContent = document.querySelector("[data-project-content]");
const closeProject = document.querySelector("[data-close-project]");

// Route currently rendered. A hash navigation fires both popstate and
// hashchange, so syncRoute compares against this to avoid rendering twice.
let currentRoute = null;
// Incremented on every navigation so a slow fetch cannot overwrite newer content.
let requestToken = 0;
// Scroll offset of the image index, restored when a project is closed.
let indexScrollY = 0;

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const inlineMarkdown = (value) => {
  const escaped = escapeHtml(value);
  return escaped
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(?!\*)([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2">$1</a>');
};

const parseFrontMatter = (source) => {
  if (!source.startsWith("---")) {
    return { meta: {}, body: source };
  }

  const end = source.indexOf("\n---", 3);
  if (end === -1) {
    return { meta: {}, body: source };
  }

  const meta = {};
  const frontMatter = source.slice(3, end).trim();
  frontMatter.split(/\r?\n/).forEach((line) => {
    const separator = line.indexOf(":");
    if (separator === -1) return;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    meta[key] = value;
  });

  return { meta, body: source.slice(end + 4).trim() };
};

const splitGallery = (meta) => {
  const images = meta.gallery || meta.images || meta.cover || "";
  return images
    .split("|")
    .map((image) => image.trim())
    .filter(Boolean);
};

// Grid tiles live in a thumbs/ folder beside the full image. Projects exported
// before that convention have none, so hydrateGrids falls back to the full
// file on error rather than showing a broken tile.
const thumbSource = (image) => image.replace(/([^/]+)$/, "thumbs/$1");

// Two layouts. "grid" is the default three-column wall of square crops, right
// for a set of discrete photographs. "full" stacks each image at its own
// proportions across the page, for figures that carry sub-panels and labels and
// have to be read rather than browsed; a square crop of those loses most of the
// content. In full mode a tile loads the full image rather than a square thumb.
const renderGrid = (title, images, layout) => {
  if (!images.length) return "";
  const full = layout === "full";

  const tiles = images
    .map(
      (image, index) => `
        <button
          class="grid-tile"
          type="button"
          data-grid-tile
          data-index="${index}"
          data-src="${escapeHtml(versioned(image))}"
          aria-label="Open image ${index + 1} of ${images.length}"
        >
          <img
            data-thumb-src="${escapeHtml(versioned(full ? image : thumbSource(image)))}"
            data-full-src="${escapeHtml(versioned(image))}"
            alt=""
            loading="lazy"
          />
        </button>
      `,
    )
    .join("");

  return `
    <section class="project-grid${full ? " is-full" : ""}" data-grid aria-label="${escapeHtml(title)} images">
      ${tiles}
    </section>
  `;
};

const renderBlocks = (markdown) => {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let paragraph = [];
  let list = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!list.length) return;
    html.push(`<ul>${list.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
    list = [];
  };

  lines.forEach((line) => {
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      flushList();
      return;
    }

    const image = trimmed.match(/^!\[(.*?)\]\((.*?)\)$/);
    if (image) {
      flushParagraph();
      flushList();
      html.push(
        `<figure><img src="${escapeHtml(image[2])}" alt="${escapeHtml(image[1])}" loading="lazy" /><figcaption>${inlineMarkdown(image[1])}</figcaption></figure>`,
      );
      return;
    }

    if (trimmed.startsWith("## ")) {
      flushParagraph();
      flushList();
      html.push(`<h2>${inlineMarkdown(trimmed.slice(3))}</h2>`);
      return;
    }

    if (trimmed.startsWith("### ")) {
      flushParagraph();
      flushList();
      html.push(`<h3>${inlineMarkdown(trimmed.slice(4))}</h3>`);
      return;
    }

    if (trimmed.startsWith("- ")) {
      flushParagraph();
      list.push(trimmed.slice(2));
      return;
    }

    paragraph.push(trimmed);
  });

  flushParagraph();
  flushList();
  return html.join("");
};

const renderProject = (markdown) => {
  const { meta, body } = parseFrontMatter(markdown);
  const title = meta.title || "Untitled project";
  // Either half may be absent, and dropping the line when only the year is
  // missing would take the type down with it.
  const kickerParts = [meta.year, meta.type].filter(Boolean).map(inlineMarkdown);
  const kicker = kickerParts.length ? `<p class="kicker">${kickerParts.join(" / ")}</p>` : "";
  // A project can carry two lines under its title: a subtitle naming the work
  // itself, and a summary describing it. Either may be absent.
  const subtitle = meta.subtitle ? `<p class="subtitle">${inlineMarkdown(meta.subtitle)}</p>` : "";
  const summary = meta.summary ? `<p>${inlineMarkdown(meta.summary)}</p>` : "";
  const images = splitGallery(meta);

  // With no kicker, subtitle or summary there is nothing to fill a left column,
  // and the title ends up stranded beside the text. Lead with it instead.
  if (!kicker && !subtitle && !summary) {
    return `
      <header class="project-hero project-hero-lead">
        <h1 tabindex="-1" data-project-title>${inlineMarkdown(title)}</h1>
      </header>
      <div class="project-body">${renderBlocks(body)}</div>
      ${renderGrid(title, images, meta.layout)}
    `;
  }

  // Otherwise two columns above the wall: identity on the left, the written
  // account on the right, then the images run full width to the bottom.
  return `
    <div class="project-intro">
      <header class="project-hero">
        ${kicker}
        <h1 tabindex="-1" data-project-title>${inlineMarkdown(title)}</h1>
        ${subtitle}
        ${summary}
      </header>
      <div class="project-body">${renderBlocks(body)}</div>
    </div>
    ${renderGrid(title, images, meta.layout)}
  `;
};

const lightbox = document.querySelector("#lightbox");
const lightboxImage = lightbox.querySelector("[data-lightbox-image]");
const lightboxCount = lightbox.querySelector("[data-lightbox-count]");

// Grid tiles are square crops, so wide figures lose most of their content at
// that size. The lightbox shows the whole image, contained, uncropped.
let lightboxSources = [];
let lightboxIndex = 0;
let lightboxLabel = "";
let lightboxOpener = null;

const showLightbox = (nextIndex) => {
  if (!lightboxSources.length) return;
  lightboxIndex = (nextIndex + lightboxSources.length) % lightboxSources.length;
  lightboxImage.src = lightboxSources[lightboxIndex];
  lightboxImage.alt = `${lightboxLabel} image ${lightboxIndex + 1}`;
  lightboxCount.textContent = `${lightboxIndex + 1} / ${lightboxSources.length}`;
};

const closeLightbox = () => {
  lightbox.hidden = true;
  document.body.classList.remove("lightbox-open");
  lightboxImage.removeAttribute("src");
  if (lightboxOpener) {
    lightboxOpener.focus();
    lightboxOpener = null;
  }
};

const openLightbox = (sources, index, label, opener) => {
  lightboxSources = sources;
  lightboxLabel = label;
  lightboxOpener = opener || null;
  lightbox.hidden = false;
  document.body.classList.add("lightbox-open");
  showLightbox(index);
  lightbox.focus();
};

lightbox.querySelector("[data-lightbox-close]").addEventListener("click", closeLightbox);
lightbox.querySelector("[data-lightbox-prev]").addEventListener("click", () => showLightbox(lightboxIndex - 1));
lightbox.querySelector("[data-lightbox-next]").addEventListener("click", () => showLightbox(lightboxIndex + 1));

lightbox.addEventListener("click", (event) => {
  // Clicking the backdrop closes; clicking the image or a control does not.
  if (event.target === lightbox) closeLightbox();
});

document.addEventListener("keydown", (event) => {
  if (lightbox.hidden) return;
  if (event.key === "Escape") return closeLightbox();
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  event.preventDefault();
  showLightbox(event.key === "ArrowLeft" ? lightboxIndex - 1 : lightboxIndex + 1);
});

const hydrateGrids = (root) => {
  root.querySelectorAll("[data-grid]").forEach((grid) => {
    const tiles = Array.from(grid.querySelectorAll("[data-grid-tile]"));
    const sources = tiles.map((tile) => tile.dataset.src);
    const label = grid.getAttribute("aria-label").replace(" images", "");

    // Attach the fallback before assigning src, so a missing thumbs/ file is
    // always caught. Setting src in the markup would race the listener.
    tiles.forEach((tile) => {
      const image = tile.querySelector("img");
      if (image && image.dataset.thumbSrc) {
        image.addEventListener(
          "error",
          () => {
            image.src = image.dataset.fullSrc;
          },
          { once: true },
        );
        image.src = image.dataset.thumbSrc;
      }
      tile.addEventListener("click", () => {
        openLightbox(sources, Number(tile.dataset.index), label, tile);
      });
    });
  });
};

// Returning to the index should give a clean URL. Pushing "#" leaves a bare
// hash hanging off the address, and the page is the index by default anyway.
const indexUrl = () => window.location.pathname + window.location.search;

const showIndex = (updateHash = true) => {
  if (!lightbox.hidden) closeLightbox();
  currentRoute = "index";
  requestToken += 1;
  document.body.classList.remove("viewing-project");
  detail.hidden = true;
  gallery.hidden = false;
  detailContent.innerHTML = "";
  if (updateHash) {
    history.pushState(null, "", indexUrl());
  }
  window.scrollTo({ top: indexScrollY, behavior: "instant" });
};

const openProject = async (slug, updateHash = true) => {
  const source = projectSources[slug];
  if (!source) {
    // Unknown slug: fall back to the index rather than leaving a dead URL.
    showIndex(false);
    history.replaceState(null, "", indexUrl());
    return;
  }

  if (currentRoute === "index") {
    indexScrollY = window.scrollY;
  }
  if (!lightbox.hidden) closeLightbox();
  currentRoute = `project/${slug}`;
  const token = ++requestToken;

  document.body.classList.add("viewing-project");
  gallery.hidden = true;
  detail.hidden = false;
  detailContent.innerHTML = "<p>Loading project...</p>";
  if (updateHash) {
    history.pushState(null, "", `#project/${slug}`);
  }
  window.scrollTo({ top: 0, behavior: "instant" });

  try {
    const response = await fetch(versioned(source));
    if (!response.ok) {
      throw new Error(`Could not load ${source}`);
    }
    const markdown = await response.text();
    if (token !== requestToken) return;
    detailContent.innerHTML = renderProject(markdown);
    hydrateGrids(detailContent);
    detailContent.querySelector("[data-project-title]")?.focus({ preventScroll: true });
  } catch (error) {
    if (token !== requestToken) return;
    detailContent.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
};

document.querySelectorAll("[data-project]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const slug = link.dataset.project;
    if (currentRoute === `project/${slug}`) return;
    openProject(slug);
  });
});

closeProject.addEventListener("click", (event) => {
  event.preventDefault();
  showIndex();
});

const syncRoute = () => {
  const match = window.location.hash.match(/^#project\/(.+)$/);
  const route = match ? `project/${match[1]}` : "index";
  if (route === currentRoute) return;
  if (match) {
    openProject(match[1], false);
  } else {
    showIndex(false);
  }
};

window.addEventListener("popstate", syncRoute);
window.addEventListener("hashchange", syncRoute);
syncRoute();

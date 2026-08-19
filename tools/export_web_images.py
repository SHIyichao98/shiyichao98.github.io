"""Export web-ready images from a local source folder into assets/site_images.

Replaces the resize-and-sharpen pass in enhance_site_images.py, which upscaled
anything under 1200px on the short side and then sharpened the result. Upscaling
adds no detail, so that pass softened every undersized figure and left halos
around the edges. This script never scales an image up: if a source is smaller
than the target it is copied at its native size and reported as a shortfall.

Targets follow the layout in styles.css:

  carousel main image   .project-carousel is min(100%, 1120px), frame is 16/10
                        -> 1120x700 CSS px, doubled for high-DPI = 2240x1400
  gallery tile (hero)   .tile is aspect-ratio 1/1 with object-fit: cover
                        -> square crop, 1200x1200
  carousel thumbnail    .carousel-thumb is aspect-ratio 1/1, ~105-220 CSS px
                        -> square crop, 240x240

Sources stay local (assets/my_design_works and assets/research_projects are
gitignored). Only the exported files under assets/site_images are published.

Usage:
    python tools/export_web_images.py assets/my_design_works/stadium \
        --out assets/site_images/design/stadium --hero exterior_render_01.jpg
"""

from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path

from PIL import Image, ImageCms, ImageFilter, ImageOps

# The stadium renders are over 100 megapixels, past Pillow's decompression-bomb
# guard. These are the user's own files, so raise the ceiling rather than fail.
Image.MAX_IMAGE_PIXELS = None

MAIN_BOX = (2240, 1400)
HERO_SIZE = 1200
# Project pages show a square grid on the same three-column spec as the index,
# so a cell is roughly 340-362 CSS px. 720 covers that on a high-DPI screen.
THUMB_SIZE = 720
SOURCE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
cmyk_fallback_override: "Path | None" = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="Folder of full-resolution source images.")
    parser.add_argument("--out", type=Path, required=True, help="Destination folder under assets/site_images.")
    parser.add_argument("--hero", help="Filename to crop into hero.jpg. Defaults to the largest image.")
    parser.add_argument(
        "--hero-crop",
        choices=("center", "top", "bottom"),
        default="center",
        help="Which band of the image the square hero crop keeps.",
    )
    parser.add_argument(
        "--format",
        choices=("jpeg", "png"),
        default="jpeg",
        help="Use png for pure line art, diagrams, and figures with small type.",
    )
    parser.add_argument("--quality", type=int, default=88, help="JPEG quality. 88 is a good default.")
    parser.add_argument("--no-thumbs", action="store_true", help="Skip the thumbs/ folder.")
    parser.add_argument(
        "--aspect",
        help="Force output to this ratio, as W:H. Use when a source was exported at the "
             "wrong shape: slide decks sometimes arrive vertically squashed, and the "
             "geometry cannot be recovered by cropping.",
    )
    parser.add_argument(
        "--assume-cmyk",
        type=Path,
        help="ICC profile to assume for untagged CMYK sources. Defaults to US Web Coated (SWOP).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report what would be written, write nothing.")
    return parser.parse_args()


SRGB = ImageCms.createProfile("sRGB")
SRGB_NAME = "sRGB IEC61966-2.1"
# Relative colorimetric is the faithful choice here: sRGB is wider than a
# coated CMYK press gamut, so in-gamut colors map exactly. Black point
# compensation keeps shadows from clipping.
INTENT = ImageCms.Intent.RELATIVE_COLORIMETRIC
try:
    BPC_FLAGS = ImageCms.Flags.BLACKPOINTCOMPENSATION
except AttributeError:  # older Pillow
    BPC_FLAGS = ImageCms.FLAGS["BLACKPOINTCOMPENSATION"]


# Untagged CMYK has to be interpreted as something. US Web Coated (SWOP) is the
# North American print default and ships with Windows. Any reasonable coated
# profile lands far closer than raw channel math: coated CMYK profiles differ
# from each other by a few points, while the naive path is off by 20 or more.
FALLBACK_CMYK_PATHS = (
    Path(r"C:\Windows\System32\spool\drivers\color\RSWOP.icm"),
    Path(r"C:\Windows\System32\spool\drivers\color\CoatedGRACoL2006.icc"),
    Path(r"C:\Windows\System32\spool\drivers\color\CoatedFOGRA39.icc"),
)


def fallback_cmyk_profile(override: Path | None) -> tuple[bytes, str] | None:
    for candidate in ([override] if override else list(FALLBACK_CMYK_PATHS)):
        if candidate and candidate.is_file():
            return candidate.read_bytes(), candidate.name
    return None


def folder_cmyk_profile(folder: Path) -> bytes | None:
    """The CMYK profile used by other files in the same export batch.

    A CMYK file with no embedded profile is untagged, not profile-free: it came
    off the same press setup as its siblings. Borrowing their profile is far
    closer than falling back to raw channel math.
    """
    for sibling in sorted(folder.iterdir()):
        if sibling.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            with Image.open(sibling) as probe:
                icc = probe.info.get("icc_profile")
                if icc and probe.mode == "CMYK":
                    return icc
        except OSError:
            continue
    return None


def to_srgb(image: Image.Image, path: Path) -> Image.Image:
    """Convert through the embedded ICC profile into sRGB.

    Plain convert("RGB") ignores the profile. On the CMYK press files in this
    project that shifts colour cold by up to 49/255 per channel, because the
    naive formula underestimates the red channel. Anything already in sRGB is
    left alone.
    """
    icc = image.info.get("icc_profile")
    if not icc and image.mode == "CMYK":
        icc = folder_cmyk_profile(path.parent)
        if icc:
            print(f"  [i] {path.name}: untagged CMYK, using the folder's CMYK profile")
        else:
            fallback = fallback_cmyk_profile(cmyk_fallback_override)
            if fallback:
                icc, name = fallback
                print(f"  [i] {path.name}: untagged CMYK, assuming {name}")
            else:
                print(f"  [!] {path.name}: untagged CMYK and no profile to assume, colour may shift")
    if not icc:
        return image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        if ImageCms.getProfileDescription(source).strip() == SRGB_NAME:
            return image
        return ImageCms.profileToProfile(
            image, source, SRGB, outputMode="RGB", renderingIntent=INTENT, flags=BPC_FLAGS
        )
    except (ImageCms.PyCMSError, OSError) as error:
        print(f"  [!] {path.name}: ICC conversion failed ({error}), using raw channels")
        return image


def load(path: Path) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path))
    if image.mode in ("RGBA", "LA", "P"):
        # Flatten transparency onto white; the detail page background is light.
        image = image.convert("RGBA")
        base = Image.new("RGB", image.size, "white")
        base.paste(image, mask=image.getchannel("A"))
        return to_srgb(base, path)
    return to_srgb(image, path).convert("RGB")


def correct_aspect(image: Image.Image, ratio: float | None) -> Image.Image:
    """Restretch to the intended ratio. Only called when a source is known to be
    distorted, since it changes geometry rather than just size."""
    if not ratio:
        return image
    current = image.width / image.height
    if abs(current - ratio) < 0.01:
        return image
    # Keep the wider dimension and move the other, so the correction is a
    # resample rather than a crop.
    if current > ratio:
        return image.resize((image.width, round(image.width / ratio)), Image.Resampling.LANCZOS)
    return image.resize((round(image.height * ratio), image.height), Image.Resampling.LANCZOS)


def fit_within(image: Image.Image, box: tuple[int, int]) -> tuple[Image.Image, bool]:
    """Scale down to fit inside box. Never scales up."""
    scale = min(box[0] / image.width, box[1] / image.height)
    if scale >= 1:
        return image, False
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS), True


def square_crop(image: Image.Image, size: int, anchor: str = "center") -> tuple[Image.Image, bool]:
    """Center-crop to a square, then scale down to size. Never scales up."""
    side = min(image.width, image.height)
    left = (image.width - side) // 2
    if anchor == "top":
        top = 0
    elif anchor == "bottom":
        top = image.height - side
    else:
        top = (image.height - side) // 2
    cropped = image.crop((left, top, left + side, top + side))
    if side <= size:
        return cropped, False
    return cropped.resize((size, size), Image.Resampling.LANCZOS), True


def save(image: Image.Image, path: Path, fmt: str, quality: int, resampled: bool) -> None:
    if resampled:
        # Light pass to recover the micro-contrast that any downscale costs.
        # Far gentler than the 165% unsharp the old enhance script applied.
        image = image.filter(ImageFilter.UnsharpMask(radius=0.8, percent=60, threshold=3))
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "png":
        image.save(path.with_suffix(".png"), "PNG", optimize=True)
    else:
        image.save(path.with_suffix(".jpg"), "JPEG", quality=quality, optimize=True, progressive=True)


def main() -> None:
    global cmyk_fallback_override
    args = parse_args()
    cmyk_fallback_override = args.assume_cmyk
    source = args.source
    if not source.is_dir():
        raise SystemExit(f"Source folder not found: {source}")

    files = sorted(p for p in source.iterdir() if p.suffix.lower() in SOURCE_SUFFIXES)
    if not files:
        raise SystemExit(f"No images found in {source}")

    # Drop byte-identical duplicates, keeping the first name alphabetically.
    seen: dict[str, Path] = {}
    unique: list[Path] = []
    for path in files:
        digest = hashlib.md5()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        key = digest.hexdigest()
        if key in seen:
            print(f"  skip (duplicate of {seen[key].name}): {path.name}")
            continue
        seen[key] = path
        unique.append(path)

    hero_folder = source / "hero_image"
    if args.hero:
        matches = [p for p in unique if p.name == args.hero]
        if not matches:
            raise SystemExit(f"--hero {args.hero!r} is not in {source}")
        hero_source = matches[0]
    elif hero_folder.is_dir():
        # The research and teaching folders keep the chosen hero in a
        # hero_image/ subfolder rather than numbering it with the figures.
        candidates = sorted(p for p in hero_folder.iterdir() if p.suffix.lower() in SOURCE_SUFFIXES)
        if not candidates:
            raise SystemExit(f"{hero_folder} exists but holds no images")
        hero_source = candidates[0]
    else:
        with Image.open(unique[0]) as probe:
            hero_source = unique[0]
            best = probe.width * probe.height
        for path in unique[1:]:
            with Image.open(path) as probe:
                if probe.width * probe.height > best:
                    hero_source, best = path, probe.width * probe.height

    ext = "png" if args.format == "png" else "jpg"
    print(f"\n{source}  ->  {args.out}")
    print(f"  hero source: {hero_source.name}")
    shortfalls: list[str] = []

    target_ratio = None
    if args.aspect:
        w, h = (float(v) for v in args.aspect.split(":"))
        target_ratio = w / h

    for index, path in enumerate(unique, start=1):
        image = correct_aspect(load(path), target_ratio)
        main_image, resampled = fit_within(image, MAIN_BOX)
        target = args.out / f"{index:02d}"

        note = ""
        if not resampled:
            # How much of the target box this source actually fills.
            pct = round(100 / min(MAIN_BOX[0] / image.width, MAIN_BOX[1] / image.height))
            note = f"  [!] fills only {pct}% of {MAIN_BOX[0]}x{MAIN_BOX[1]}"
            shortfalls.append(f"{path.name} ({image.width}x{image.height}) fills {pct}% of target")

        print(f"  {index:02d}.{ext}  {image.width}x{image.height} -> {main_image.width}x{main_image.height}  {path.name}{note}")

        if not args.dry_run:
            save(main_image, target, args.format, args.quality, resampled)
            if not args.no_thumbs:
                thumb, thumb_resampled = square_crop(image, THUMB_SIZE)
                save(thumb, args.out / "thumbs" / f"{index:02d}", args.format, args.quality, thumb_resampled)

    hero_image = correct_aspect(load(hero_source), target_ratio)
    hero, hero_resampled = square_crop(hero_image, HERO_SIZE, args.hero_crop)
    print(f"  hero.{ext}  {hero.width}x{hero.height} ({args.hero_crop} crop)")
    if hero.width < HERO_SIZE:
        shortfalls.append(f"hero from {hero_source.name}: square crop is only {hero.width}px, want {HERO_SIZE}px")
    if not args.dry_run:
        save(hero, args.out / "hero", args.format, args.quality, hero_resampled)
        if not args.no_thumbs:
            # hero.jpg leads every gallery, so it needs a thumbnail too.
            hero_thumb, hero_thumb_resampled = square_crop(hero_image, THUMB_SIZE, args.hero_crop)
            save(hero_thumb, args.out / "thumbs" / "hero", args.format, args.quality, hero_thumb_resampled)

    if shortfalls:
        print(f"\n  {len(shortfalls)} image(s) below target — source resolution is the limit, not the export:")
        for line in shortfalls:
            print(f"    - {line}")


if __name__ == "__main__":
    main()

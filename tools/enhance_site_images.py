from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat


ROOT = Path("assets/site_images")
MAX_SIDE = 2400
MIN_SIDE_TARGET = 1200


def is_diagram_like(image: Image.Image) -> bool:
    small = image.copy()
    small.thumbnail((360, 360), Image.Resampling.BILINEAR)
    gray = small.convert("L")
    stat = ImageStat.Stat(gray)
    mean = stat.mean[0]
    contrast = stat.stddev[0]
    colors = small.convert("P", palette=Image.Palette.ADAPTIVE, colors=32).getcolors()
    color_count = len(colors or [])
    return mean > 165 and (contrast < 58 or color_count < 24)


def target_size(width: int, height: int) -> tuple[int, int]:
    max_side = max(width, height)
    min_side = min(width, height)

    if min_side < MIN_SIDE_TARGET:
        scale = MIN_SIDE_TARGET / min_side
    else:
        scale = 1

    if max_side * scale > MAX_SIDE:
        scale = MAX_SIDE / max_side

    return max(1, round(width * scale)), max(1, round(height * scale))


def enhance(path: Path) -> None:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)

    if image.mode in ("RGBA", "LA"):
        base = Image.new("RGB", image.size, "white")
        base.paste(image, mask=image.getchannel("A"))
        image = base
    else:
        image = image.convert("RGB")

    diagram = is_diagram_like(image)
    size = target_size(*image.size)
    if size != image.size:
        image = image.resize(size, Image.Resampling.LANCZOS)

    if diagram:
        image = ImageOps.autocontrast(image, cutoff=0.6)
        image = ImageEnhance.Contrast(image).enhance(1.08)
        image = image.filter(ImageFilter.UnsharpMask(radius=1.15, percent=165, threshold=2))
    else:
        image = ImageEnhance.Sharpness(image).enhance(1.15)
        image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=80, threshold=4))

    image.save(path, "JPEG", quality=90, optimize=True, progressive=True)


def main() -> None:
    paths = sorted(ROOT.glob("**/*.jpg"))
    for path in paths:
        before = path.stat().st_size
        enhance(path)
        after = path.stat().st_size
        print(f"{path.as_posix()} {before} -> {after}")


if __name__ == "__main__":
    main()

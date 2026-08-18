from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render high-resolution PDF pages for portfolio image cleanup."
    )
    parser.add_argument("pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Folder where rendered page images will be written.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=360,
        help="Render resolution. 300-450 is usually good for paper figures.",
    )
    parser.add_argument("--first", type=int, help="First page to render, 1-based.")
    parser.add_argument("--last", type=int, help="Last page to render, 1-based.")
    return parser.parse_args()


def find_pdftoppm() -> str:
    command = shutil.which("pdftoppm")
    candidates: list[Path] = []

    if command:
        path = Path(command)
        if path.suffix.lower() == ".exe":
            return str(path)

        parents = list(path.parents)
        if len(parents) >= 3:
            candidates.append(
                parents[2] / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe"
            )
        if len(parents) >= 2:
            candidates.append(parents[1] / "Library" / "bin" / "pdftoppm.exe")
        candidates.append(path)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise SystemExit("pdftoppm was not found on PATH.")


def main() -> None:
    args = parse_args()
    pdf = args.pdf.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")

    prefix = output_dir / pdf.stem
    command = [
        find_pdftoppm(),
        "-jpeg",
        "-r",
        str(args.dpi),
    ]
    if args.first:
        command.extend(["-f", str(args.first)])
    if args.last:
        command.extend(["-l", str(args.last)])
    command.extend([str(pdf), str(prefix)])

    subprocess.run(command, check=True)
    print(f"Rendered pages to {output_dir}")


if __name__ == "__main__":
    main()

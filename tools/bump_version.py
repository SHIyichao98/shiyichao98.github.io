"""Bump the asset version so browsers fetch changed files instead of cached ones.

Published filenames are stable: 01.jpg stays 01.jpg, script.js stays script.js.
Without a changing URL a browser that has already seen the site keeps its copy,
and GitHub Pages serves Cache-Control: max-age=600, so a returning visitor can
run new markup against old CSS. Stamping a version onto every asset URL gives
the browser a reason to refetch.

index.html carries the stamp on styles.css, script.js, and the index tiles.
script.js carries ASSET_VERSION and applies it to everything it fetches at
runtime: markdown pages, grid tiles, and lightbox images. index.html itself is
the one file that cannot be stamped, but it expires in ten minutes, so the
staleness is bounded and self-healing.

Run after changing any published asset, then commit:
    python tools/bump_version.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INDEX = Path("index.html")
SCRIPT = Path("script.js")


def current() -> int:
    match = re.search(r'const ASSET_VERSION = "(\d+)"', SCRIPT.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("ASSET_VERSION not found in script.js")
    return int(match.group(1))


def main() -> None:
    old = current()
    new = old + 1

    script = SCRIPT.read_text(encoding="utf-8")
    script = script.replace(f'const ASSET_VERSION = "{old}"', f'const ASSET_VERSION = "{new}"')
    SCRIPT.write_text(script, encoding="utf-8")

    index = INDEX.read_text(encoding="utf-8")
    index, count = re.subn(rf"\?v={old}\b", f"?v={new}", index)
    INDEX.write_text(index, encoding="utf-8")

    print(f"  asset version {old} -> {new}")
    print(f"  script.js: ASSET_VERSION")
    print(f"  index.html: {count} references")
    if count == 0:
        print("  [!] no ?v= references in index.html — check it was stamped in the first place", file=sys.stderr)


if __name__ == "__main__":
    main()

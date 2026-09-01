"""Write the portfolio as IDML, InDesign's open interchange format.

InDesign's own .indd is closed and undocumented, so nothing outside Adobe can
write one. IDML is the way in: a zip of XML that InDesign opens and converts to
a full editable document, with real text frames, real paragraph styles, and
real image links. What comes out is editable the way a designer expects, unlike
the generated PDF, where moving a caption means editing a stylesheet.

The format is exacting — one wrong element and InDesign refuses the file rather
than complaining about a detail — so this writes the smallest structure that is
still valid: one page per spread, one story per text frame, a rectangle with a
linked image for each picture, and only the styles the pages actually use.

Two things are easy to get wrong and are worth naming:

  Coordinates are points, and page items are placed by their centre, not their
  corner. A frame's geometry runs from -w/2 to w/2 about its own origin, and its
  ItemTransform moves that origin into spread space, where the page centre is 0,0.

  mimetype must be the first entry in the zip and must be stored uncompressed.
  A deflated mimetype produces a file InDesign will not open.

Images are linked, not embedded, at absolute paths into portfolio_package. Move
that folder and InDesign will ask to relink; it finds them again if they sit
beside the document or in a Links folder.

    python tools/build_idml.py --sample    # first three pages, to test opening
    python tools/build_idml.py             # all twenty
"""

from __future__ import annotations

import argparse
import html
import zipfile
from pathlib import Path

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).parent))

from build_portfolio import (  # noqa: E402
    EMAIL,
    NAME,
    PAGES,
    ROLE,
    SITE,
    bullets,
    kicker,
    paragraphs,
    pick,
    read,
)

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "portfolio_package" / "images"
OUT_FULL = ROOT / "Yichao_Shi_Portfolio.idml"
OUT_SAMPLE = ROOT / "Yichao_Shi_Portfolio_sample.idml"

PT = 72.0
PAGE_W, PAGE_H = 11 * PT, 8.5 * PT
PAD_T, PAD_S, PAD_B = 0.62 * PT, 0.7 * PT, 0.55 * PT
PROSE_W, SPLIT_GAP, FIG_GAP = 3.05 * PT, 0.36 * PT, 0.13 * PT
HEAD_H = 78.0

LIVE_X = PAD_S
LIVE_W = PAGE_W - 2 * PAD_S
BODY_Y = PAD_T + HEAD_H + 10
BODY_H = PAGE_H - PAD_B - BODY_Y
FIGS_X = PAD_S + PROSE_W + SPLIT_GAP
FIGS_W = PAGE_W - PAD_S - FIGS_X

# name -> (point size, leading, colour, bold, caps, space after)
STYLES = {
    "Kicker": (9.5, 12, "Grey", False, True, 5),
    "Title": (20, 22, "Ink", True, False, 4),
    "Subtitle": (13, 16, "Grey", False, False, 4),
    "Authors": (9.5, 12.5, "Grey", False, False, 8),
    "Standfirst": (11.5, 16, "Ink", False, False, 8),
    "Body": (10, 14.5, "Ink", False, False, 8),
    "SectionHead": (9.5, 12, "Ink", True, True, 4),
    "ListItem": (9.5, 12.5, "Soft", False, False, 3),
    "Caption": (7.5, 9.5, "Grey", False, False, 3),
    "Reference": (7.4, 9.5, "Ink", False, False, 4),
    "CoverName": (42, 44, "Ink", True, False, 14),
    "CoverRole": (12, 16, "Soft", False, False, 6),
}
COLOURS = {"Ink": (0, 0, 0, 92), "Grey": (0, 0, 0, 58), "Soft": (0, 0, 0, 74)}


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def geometry(w: float, h: float) -> str:
    """A rectangular path about the item's own centre, which is how InDesign
    writes one: the frame's transform then places that centre in the spread."""
    left, top, right, bottom = -w / 2, -h / 2, w / 2, h / 2
    points = ((left, top), (left, bottom), (right, bottom), (right, top))
    anchors = "".join(
        f'<PathPointType Anchor="{x:.4f} {y:.4f}" LeftDirection="{x:.4f} {y:.4f}" '
        f'RightDirection="{x:.4f} {y:.4f}"/>'
        for x, y in points
    )
    return (
        "<Properties><PathGeometry><GeometryPathType PathOpen=\"false\">"
        f"<PathPointArray>{anchors}</PathPointArray>"
        "</GeometryPathType></PathGeometry></Properties>"
    )


def transform(x: float, y: float, w: float, h: float) -> str:
    """Place a frame whose page-space rectangle is (x, y, w, h).

    Spread space has the page centre at the origin, so the frame's centre in
    page space is shifted by half a page in each direction."""
    cx = x + w / 2 - PAGE_W / 2
    cy = y + h / 2 - PAGE_H / 2
    return f'1 0 0 1 {cx:.4f} {cy:.4f}'


def text_frame(uid: str, story: str, x: float, y: float, w: float, h: float) -> str:
    return (
        f'<TextFrame Self="{uid}" ParentStory="{story}" '
        f'ItemTransform="{transform(x, y, w, h)}" '
        f'AppliedObjectStyle="ObjectStyle/$ID/[Normal Text Frame]">'
        f"{geometry(w, h)}"
        '<TextFramePreference TextColumnCount="1" TextColumnGutter="12" '
        'VerticalJustification="TopAlign" AutoSizingType="Off"/>'
        "</TextFrame>"
    )


def image_frame(uid: str, path: Path, x: float, y: float, w: float, h: float, whole: bool) -> str:
    try:
        px, py = Image.open(path).size
    except Exception:
        px, py = 1000, 1000
    scale = (min if whole else max)(w / px, h / py)
    # The image's own space starts at its top-left; the frame's starts at its
    # centre, so the placement offset is half the scaled image back and up.
    tx, ty = -scale * px / 2, -scale * py / 2
    uri = "file:/" + str(path).replace("\\", "/")
    return (
        f'<Rectangle Self="{uid}" ContentType="GraphicType" '
        f'ItemTransform="{transform(x, y, w, h)}" '
        f'AppliedObjectStyle="ObjectStyle/$ID/[Normal Graphics Frame]" '
        f'StrokeWeight="0" StrokeColor="Swatch/None" FillColor="Swatch/None">'
        f"{geometry(w, h)}"
        f'<Image Self="{uid}i" ItemTransform="{scale:.6f} 0 0 {scale:.6f} {tx:.4f} {ty:.4f}" '
        f'ImageTypeName="$ID/JPEG" ActualPpi="72 72" EffectivePpi="72 72">'
        "<Properties>"
        "<Profile type=\"string\">$ID/Embedded</Profile>"
        f'<GraphicBounds Left="0" Top="0" Right="{px}" Bottom="{py}"/>'
        "</Properties>"
        f'<Link Self="{uid}l" LinkResourceURI="{esc(uri)}" LinkResourceFormat="$ID/JPEG" '
        'StoredState="Normal" LinkClassID="35906" LinkClientID="257" '
        'AssetURL="$ID/" AssetID="$ID/" LinkImportStamp="" '
        'LinkImportModificationTime="" LinkImportTime="" LinkObjectModified="false"/>'
        "</Image>"
        "</Rectangle>"
    )


def story_xml(uid: str, blocks: list[tuple[str, str]]) -> str:
    runs = []
    for style, text in blocks:
        if not text:
            continue
        body = esc(text).replace("\n", "<Br/>")
        runs.append(
            f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/{style}">'
            '<CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">'
            f"<Content>{body}</Content><Br/>"
            "</CharacterStyleRange>"
            "</ParagraphStyleRange>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        f'<Story Self="{uid}" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="" AppliedNamedGrid="n">'
        '<StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" '
        'FrameType="TextFrameType" StoryOrientation="Horizontal" StoryDirection="LeftToRightDirection"/>'
        f"{''.join(runs)}"
        "</Story></idPkg:Story>"
    )


# ------------------------------------------------------------- page content --

def blocks_for(spec: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (header blocks, body blocks) for a page."""
    kind = spec["kind"]
    if kind == "cover":
        return (
            [("CoverName", NAME), ("CoverRole", ROLE), ("Kicker", "Portfolio / research, teaching, design")],
            [("Caption", f"{EMAIL}   {SITE}")],
        )
    if kind == "map":
        return ([("Title", "Research")], [("Body", "The map is placed as research-map.svg; it carries its own type.")])
    if kind == "closing":
        about = read("about")
        return ([("Title", NAME)], [("Standfirst", about.get("summary", "")), ("Caption", f"{EMAIL}\n{SITE}")])
    if kind == "cv":
        meta = read("cv")
        body: list[tuple[str, str]] = []
        for name in ("Education", "Experience", "Academic Service", "Awards", "Methods and Tools"):
            rows = bullets(meta, name)
            if rows:
                body.append(("SectionHead", name))
                body += [("ListItem", r) for r in rows]
        return ([("Title", "Curriculum vitae"), ("Subtitle", "Abridged; the full CV is a separate document.")], body)
    if kind == "teaching-overview":
        body = []
        for slug in ("arch-2017", "arch-6020", "arch-8833", "arch-2020"):
            meta = read(slug)
            role = paragraphs(meta, "Role")
            body += [
                ("SectionHead", f"{meta.get('title','')} — {meta.get('subtitle','')}"),
                ("ListItem", meta.get("year", "")),
                ("ListItem", meta.get("summary", "")),
                ("Caption", role[0] if role else ""),
            ]
        return ([("Title", "Teaching")], body)
    if kind == "papers-three":
        body = []
        for slug in spec["slugs"]:
            meta = read(slug)
            body += [
                ("Kicker", meta.get("year", "")),
                ("SectionHead", meta.get("title", "")),
                ("Caption", meta.get("authors", "")),
                ("ListItem", meta.get("summary", "")),
            ]
        text = (ROOT / "content" / "projects" / "publications.md").read_text(encoding="utf-8")
        raw = text.split("---", 2)[2] if text.startswith("---") else text
        body.append(("SectionHead", "Peer-reviewed publications"))
        body += [("Reference", r.strip()) for r in raw.splitlines() if r.strip()]
        return ([("Title", "Further research")], body)

    if kind == "design":
        # One or two projects share the page, so the heading belongs to the
        # first and the rest runs on below it.
        first = read(spec["slugs"][0])
        head = [("Kicker", kicker(first)), ("Title", first.get("title", ""))]
        body = []
        for index, slug in enumerate(spec["slugs"]):
            meta = read(slug)
            if index:
                body += [("Kicker", kicker(meta)), ("SectionHead", meta.get("title", ""))]
            body.append(("Standfirst" if not index else "ListItem", meta.get("summary", "")))
            role = paragraphs(meta, "Role")
            if role:
                body.append(("Caption", role[0]))
        return (head, body)

    meta = read(spec["slug"])
    if spec.get("part") == 2:
        head = [("Kicker", f"{kicker(meta)} / student work"), ("Title", meta.get("title", ""))]
        return (head, [])
    head = [("Kicker", kicker(meta)), ("Title", meta.get("title", ""))]
    if meta.get("subtitle"):
        head.append(("Subtitle", meta["subtitle"]))
    body = []
    if meta.get("authors"):
        body.append(("Authors", meta["authors"].replace(" | ", "   ")))
    body.append(("Standfirst", meta.get("summary", "")))
    overview = paragraphs(meta, "Overview")
    if overview:
        body.append(("Body", overview[0]))
    focus = bullets(meta, "Focus")
    if focus:
        body.append(("SectionHead", "Focus"))
        body += [("ListItem", f) for f in focus[:6]]
    role = paragraphs(meta, "Role")
    if role:
        body += [("SectionHead", "Role"), ("Caption", role[0])]
    return (head, body)


def images_for(spec: dict) -> tuple[list[tuple[Path, str]], int, bool]:
    """Return (paths with captions, columns, place whole)."""
    kind = spec["kind"]
    number = PAGES.index(spec) + 1
    found = sorted(LINKS.glob(f"p{number:02d}_*"))
    if kind == "cover":
        return [(p, "") for p in found], 5, False
    if kind == "map":
        return [], 1, True
    if kind in {"cv", "closing", "teaching-overview"}:
        return [], 1, False

    pairs: list[tuple[str, str]] = []
    if kind == "paper":
        pairs = pick(read(spec["slug"]), spec["shots"], by_figure=True)
    elif kind == "course":
        meta = read(spec["slug"])
        pairs = pick(meta, spec["shots"], skip=spec["shots"] if spec.get("part") == 2 else 0)
    elif kind == "design":
        for slug in spec["slugs"]:
            pairs += pick(read(slug), spec["shots"])
    elif kind == "papers-three":
        pairs = [pick(read(slug), 1, by_figure=True)[0] for slug in spec["slugs"]]

    captions = [c for _s, c in pairs]
    wide = 0
    for source, _c in pairs:
        try:
            w, h = Image.open(ROOT / source).size
            wide += w / h > 1.25
        except Exception:
            pass
    whole = bool(pairs) and wide > len(pairs) / 2
    columns = 3 if (kind == "papers-three" or (kind == "course" and spec.get("part") == 2)) else 2
    if kind == "design" and spec["shots"] >= 3:
        columns = 3
    return list(zip(found, captions + [""] * len(found))), columns, whole


# ------------------------------------------------------------------ package --

def styles_xml() -> str:
    paragraphs_xml = []
    for name, (size, leading, colour, bold, caps, after) in STYLES.items():
        # AppliedFont, Leading and BasedOn are child elements, not attributes.
        # Written as attributes InDesign rejects the package outright rather
        # than falling back to a default.
        paragraphs_xml.append(
            f'<ParagraphStyle Self="ParagraphStyle/{name}" Name="{name}" '
            f'PointSize="{size}" SpaceAfter="{after}" FillColor="Color/{colour}" '
            f'Capitalization="{"AllCaps" if caps else "Normal"}" '
            f'FontStyle="{"Bold" if bold else "Regular"}" '
            'Justification="LeftAlign" AppliedLanguage="$ID/English: USA">'
            "<Properties>"
            '<BasedOn type="object">$ID/[No paragraph style]</BasedOn>'
            '<PreviewColor type="enumeration">Nothing</PreviewColor>'
            '<AppliedFont type="string">Helvetica Neue</AppliedFont>'
            f'<Leading type="unit">{leading}</Leading>'
            "</Properties></ParagraphStyle>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:Styles xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        "<RootCharacterStyleGroup Self=\"u0\">"
        '<CharacterStyle Self="CharacterStyle/$ID/[No character style]" Name="$ID/[No character style]"/>'
        "</RootCharacterStyleGroup>"
        "<RootParagraphStyleGroup Self=\"u1\">"
        '<ParagraphStyle Self="ParagraphStyle/$ID/[No paragraph style]" Name="$ID/[No paragraph style]"/>'
        '<ParagraphStyle Self="ParagraphStyle/$ID/NormalParagraphStyle" Name="$ID/NormalParagraphStyle" '
        'AppliedFont="Helvetica Neue" PointSize="10" Leading="14"/>'
        f"{''.join(paragraphs_xml)}"
        "</RootParagraphStyleGroup>"
        '<RootObjectStyleGroup Self="u2">'
        '<ObjectStyle Self="ObjectStyle/$ID/[None]" Name="$ID/[None]"/>'
        '<ObjectStyle Self="ObjectStyle/$ID/[Normal Graphics Frame]" Name="$ID/[Normal Graphics Frame]"/>'
        '<ObjectStyle Self="ObjectStyle/$ID/[Normal Text Frame]" Name="$ID/[Normal Text Frame]"/>'
        "</RootObjectStyleGroup>"
        '<RootCellStyleGroup Self="u3"><CellStyle Self="CellStyle/$ID/[None]" Name="$ID/[None]"/></RootCellStyleGroup>'
        '<RootTableStyleGroup Self="u4"><TableStyle Self="TableStyle/$ID/[No table style]" Name="$ID/[No table style]"/></RootTableStyleGroup>'
        "</idPkg:Styles>"
    )


def graphic_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:Graphic xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        '<Color Self="Color/Black" Model="Process" Space="CMYK" ColorValue="0 0 0 100" Name="Black" '
        'ColorEditable="false" ColorRemovable="false"/>'
        '<Color Self="Color/Paper" Model="Process" Space="CMYK" ColorValue="0 0 0 0" Name="Paper" '
        'ColorEditable="false" ColorRemovable="false"/>'
        '<Swatch Self="Swatch/None" Name="None" ColorEditable="false" ColorRemovable="false"/>'
        # The document's own greys live here rather than in Styles.xml: a
        # paragraph style referencing a colour defined outside Graphic.xml
        # resolves to nothing.
        + "".join(
            f'<Color Self="Color/{name}" Model="Process" Space="CMYK" '
            f'ColorValue="{c} {m} {y} {k}" Name="{name}" '
            'ColorEditable="true" ColorRemovable="true"/>'
            for name, (c, m, y, k) in COLOURS.items()
        )
        + '<StrokeStyle Self="StrokeStyle/$ID/Solid" Name="$ID/Solid"/>'
        '<Ink Self="Ink/$ID/Process Cyan" Name="$ID/Process Cyan"/>'
        '<Ink Self="Ink/$ID/Process Magenta" Name="$ID/Process Magenta"/>'
        '<Ink Self="Ink/$ID/Process Yellow" Name="$ID/Process Yellow"/>'
        '<Ink Self="Ink/$ID/Process Black" Name="$ID/Process Black"/>'
        "</idPkg:Graphic>"
    )


def fonts_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:Fonts xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        '<FontFamily Self="fam1" Name="Helvetica Neue">'
        '<Font Self="fam1f1" FontFamily="Helvetica Neue" Name="Helvetica Neue Regular" '
        'PostScriptName="HelveticaNeue" Status="Substituted" FontStyleName="Regular" FontType="OpenTypeCFF"/>'
        '<Font Self="fam1f2" FontFamily="Helvetica Neue" Name="Helvetica Neue Bold" '
        'PostScriptName="HelveticaNeue-Bold" Status="Substituted" FontStyleName="Bold" FontType="OpenTypeCFF"/>'
        "</FontFamily></idPkg:Fonts>"
    )


def preferences_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:Preferences xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        f'<DocumentPreference PageHeight="{PAGE_H}" PageWidth="{PAGE_W}" PagesPerDocument="1" '
        'FacingPages="false" PageOrientation="Landscape" DocumentBleedTopOffset="0" '
        'DocumentBleedBottomOffset="0" DocumentBleedInsideOrLeftOffset="0" DocumentBleedOutsideOrRightOffset="0"/>'
        '<ViewPreference HorizontalMeasurementUnits="Points" VerticalMeasurementUnits="Points" '
        'RulerOrigin="PageOrigin"/>'
        f'<MarginPreference Top="{PAD_T}" Bottom="{PAD_B}" Left="{PAD_S}" Right="{PAD_S}" '
        'ColumnCount="1" ColumnGutter="12"/>'
        '<TextDefault AppliedFont="Helvetica Neue" PointSize="10" Leading="14" '
        'AppliedLanguage="$ID/English: USA"/>'
        "</idPkg:Preferences>"
    )


def master_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:MasterSpread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        '<MasterSpread Self="mA" Name="A-Master" NamePrefix="A" BaseName="Master" PageCount="1" '
        'ItemTransform="1 0 0 1 0 0" ShowMasterItems="true">'
        f'<Page Self="mApage" Name="A" AppliedMaster="n" '
        f'GeometricBounds="0 0 {PAGE_H} {PAGE_W}" ItemTransform="1 0 0 1 {-PAGE_W/2} {-PAGE_H/2}">'
        f'<MarginPreference Top="{PAD_T}" Bottom="{PAD_B}" Left="{PAD_S}" Right="{PAD_S}" '
        'ColumnCount="1" ColumnGutter="12"/>'
        "</Page></MasterSpread></idPkg:MasterSpread>"
    )


def spread_xml(number: int, items: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        f'<Spread Self="s{number}" PageCount="1" BindingLocation="0" AllowPageShuffle="true" '
        'ItemTransform="1 0 0 1 0 0" ShowMasterItems="true" PageTransitionType="None">'
        '<FlattenerPreference LineArtAndTextResolution="300" GradientAndMeshResolution="150" '
        'ClipComplexRegions="false" ConvertAllStrokesToOutlines="false" ConvertAllTextToOutlines="false"/>'
        f'<Page Self="page{number}" Name="{number}" AppliedMaster="mA" '
        f'GeometricBounds="0 0 {PAGE_H} {PAGE_W}" ItemTransform="1 0 0 1 {-PAGE_W/2} {-PAGE_H/2}" '
        'AppliedTrapPreset="TrapPreset/$ID/kDefaultTrapStyleName" OverrideList="">'
        f'<MarginPreference Top="{PAD_T}" Bottom="{PAD_B}" Left="{PAD_S}" Right="{PAD_S}" '
        'ColumnCount="1" ColumnGutter="12"/>'
        "</Page>"
        f"{items}"
        "</Spread></idPkg:Spread>"
    )


def designmap(spreads: int, stories: list[str]) -> str:
    parts = [
        '<idPkg:Graphic src="Resources/Graphic.xml"/>',
        '<idPkg:Fonts src="Resources/Fonts.xml"/>',
        '<idPkg:Styles src="Resources/Styles.xml"/>',
        '<idPkg:Preferences src="Resources/Preferences.xml"/>',
        '<idPkg:MasterSpread src="MasterSpreads/MasterSpread_mA.xml"/>',
    ]
    parts += [f'<idPkg:Spread src="Spreads/Spread_s{i}.xml"/>' for i in range(1, spreads + 1)]
    parts += [f'<idPkg:Story src="Stories/Story_{s}.xml"/>' for s in stories]
    parts.append('<idPkg:BackingStory src="XML/BackingStory.xml"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<?aid style="50" type="document" readerVersion="6.0" featureSet="257" product="8.0(370)" ?>'
        '<Document xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0" '
        f'Self="portfolio" StoryList="{" ".join(stories)}" Name="Yichao Shi Portfolio">'
        f"{''.join(parts)}"
        "</Document>"
    )


def build(limit: int | None) -> tuple[dict[str, str], int]:
    specs = PAGES[:limit] if limit else PAGES
    files: dict[str, str] = {}
    stories: list[str] = []

    for number, spec in enumerate(specs, 1):
        head, body = blocks_for(spec)
        shots, columns, whole = images_for(spec)
        items = []

        if head:
            uid = f"st{number}h"
            stories.append(uid)
            files[f"Stories/Story_{uid}.xml"] = story_xml(uid, head)
            items.append(text_frame(f"tf{number}h", uid, LIVE_X, PAD_T, LIVE_W, HEAD_H))

        text_w = PROSE_W if shots else LIVE_W
        if body:
            uid = f"st{number}b"
            stories.append(uid)
            files[f"Stories/Story_{uid}.xml"] = story_xml(uid, body)
            items.append(text_frame(f"tf{number}b", uid, LIVE_X, BODY_Y, text_w, BODY_H))

        if shots:
            grid_x = FIGS_X if body else LIVE_X
            grid_w = FIGS_W if body else LIVE_W
            rows = max(1, -(-len(shots) // columns))
            cell_w = (grid_w - FIG_GAP * (columns - 1)) / columns
            cell_h = (BODY_H - FIG_GAP * (rows - 1)) / rows
            for index, (path, _caption) in enumerate(shots):
                col, row = index % columns, index // columns
                items.append(
                    image_frame(
                        f"rc{number}_{index}",
                        path,
                        grid_x + col * (cell_w + FIG_GAP),
                        BODY_Y + row * (cell_h + FIG_GAP),
                        cell_w,
                        cell_h,
                        whole,
                    )
                )

        files[f"Spreads/Spread_s{number}.xml"] = spread_xml(number, "".join(items))

    files["designmap.xml"] = designmap(len(specs), stories)
    files["Resources/Graphic.xml"] = graphic_xml()
    files["Resources/Fonts.xml"] = fonts_xml()
    files["Resources/Styles.xml"] = styles_xml()
    files["Resources/Preferences.xml"] = preferences_xml()
    files["MasterSpreads/MasterSpread_mA.xml"] = master_xml()
    files["XML/BackingStory.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="8.0">'
        '<XmlStory Self="backing" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="" AppliedNamedGrid="n">'
        '<StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" FrameType="TextFrameType" '
        'StoryOrientation="Horizontal" StoryDirection="LeftToRightDirection"/>'
        "</XmlStory></idPkg:Story>"
    )
    files["META-INF/container.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles><rootfile full-path="designmap.xml" '
        'media-type="text/xml"/></rootfiles></container>'
    )
    files["META-INF/metadata.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:format>application/vnd.adobe.indesign-idml-package'
        "</dc:format></rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    return files, len(specs)


def write(path: Path, files: dict[str, str]) -> None:
    if path.exists():
        path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Stored, and first in the archive. A deflated mimetype makes a file
        # InDesign will not open.
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.adobe.indesign-idml-package",
            compress_type=zipfile.ZIP_STORED,
        )
        for name, body in files.items():
            zf.writestr(name, body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="First three pages only, to test that it opens.")
    args = parser.parse_args()

    if not LINKS.is_dir():
        sys.exit("run tools/export_indesign_package.py first — the images come from there")

    files, count = build(3 if args.sample else None)
    target = OUT_SAMPLE if args.sample else OUT_FULL
    write(target, files)
    print(f"  {target.name}  {count} pages  {target.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()

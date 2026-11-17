"""MkDocs hook: give local images their intrinsic size and load all but the first lazily.

An <img> without width and height takes no room until it loads, so the text under it
jumps (Cumulative Layout Shift). Markdown has no way to state the size of a screenshot
short of typing it, so it is read from the file when the page is built. The theme styles
images with `height: auto; max-width: 100%`, so the attributes only reserve the aspect
ratio and never change the size an image is shown at.

The first image of the content may be the largest paint of the page, so it stays eager;
every later one waits until it nears the viewport (advanced.md alone holds 34 screenshots).
"""

from functools import cache
from logging import getLogger
from pathlib import Path
from re import IGNORECASE, compile as re_compile
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError

log = getLogger("mkdocs.hooks.imgsize")

_IMG_RE = re_compile(r"<img\b[^>]*>", IGNORECASE)
_ATTR_RE = re_compile(r"""\s([a-zA-Z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_SVG_ROOT_RE = re_compile(r"<svg\b[^>]*>", IGNORECASE)
_NUMBER_RE = re_compile(r"^\s*([0-9]*\.?[0-9]+)\s*(?:px)?\s*$")


@cache
def _size(path: str):
    """Return (width, height) of an image file, or None when it cannot be read."""
    file = Path(path)
    try:
        if file.suffix.lower() == ".svg":
            return _svg_size(file.read_text(encoding="utf-8", errors="replace"))
        with Image.open(file) as image:
            return image.size
    except (OSError, UnidentifiedImageError):
        return None


def _svg_size(text: str):
    root = _SVG_ROOT_RE.search(text)
    if not root:
        return None
    attrs = {name.lower(): double or single for name, double, single in _ATTR_RE.findall(root.group(0))}
    box = attrs.get("viewbox", "").replace(",", " ").split()
    if len(box) == 4:
        try:
            width, height = float(box[2]), float(box[3])
        except ValueError:
            return None
        return (width, height) if width > 0 and height > 0 else None
    width, height = _NUMBER_RE.match(attrs.get("width", "")), _NUMBER_RE.match(attrs.get("height", ""))
    return (float(width.group(1)), float(height.group(1))) if width and height else None


def _number(value):
    match = _NUMBER_RE.match(value) if value is not None else None
    return float(match.group(1)) if match else None


def _fmt(value: float) -> str:
    # the width and height attributes take whole pixels
    return str(round(value))


def on_post_page(output, page, config):
    page_dir = Path(page.file.abs_src_path).parent

    def sized(tag, attrs):
        src = attrs.get("src")
        if not src or "width" in attrs and "height" in attrs:
            return tag
        parts = urlsplit(src)
        if parts.scheme or parts.netloc or not parts.path:
            return tag
        # a built page links its images relative to its own URL, which for a page
        # under a language folder is not the folder of its source file, so the file
        # is found from the docs directory instead
        built = Path(config["docs_dir"], *[p for p in unquote(parts.path).split("/") if p not in ("", ".", "..")])
        found = built if built.is_file() else (page_dir / unquote(parts.path)).resolve()
        size = _size(str(found)) if found.is_file() else None
        if not size:
            return tag
        width, height = _number(attrs.get("width")), _number(attrs.get("height"))
        if "width" in attrs and width is None or "height" in attrs and height is None:
            return tag  # a percentage or other unit: leave the author's sizing alone
        if width is height is None:
            width, height = size
        elif height is None:
            height = width * size[1] / size[0]
        else:
            width = height * size[0] / size[1]
        extra = ""
        if "width" not in attrs:
            extra += f' width="{_fmt(width)}"'
        if "height" not in attrs:
            extra += f' height="{_fmt(height)}"'
        return _append(tag, extra)

    def _append(tag, extra):
        if not extra:
            return tag
        return tag[:-2].rstrip() + extra + " />" if tag.endswith("/>") else tag[:-1] + extra + ">"

    def process(chunk, lazy):
        first = [True]

        def rewrite(match):
            tag = match.group(0)
            attrs = {name.lower(): double or single for name, double, single in _ATTR_RE.findall(tag)}
            tag = sized(tag, attrs)
            if lazy and "twemoji" not in attrs.get("class", ""):
                if first[0]:
                    first[0] = False
                elif "loading" not in attrs:
                    tag = _append(tag, ' loading="lazy" decoding="async"')
            return tag

        return _IMG_RE.sub(rewrite, chunk)

    # the header logo and the like come before <article>: sized, never lazy
    start = output.find("<article")
    if start < 0:
        return process(output, False)
    return process(output[:start], False) + process(output[start:], True)

"""MkDocs hook to generate llms.txt and llms-full.txt for AI agent consumption."""

from json import dumps
from logging import getLogger
import os
from pathlib import Path
from re import DOTALL, MULTILINE, compile as re_compile, split
from urllib.parse import quote, urlsplit

from markdown.extensions.toc import slugify

log = getLogger("mkdocs.hooks.llmstxt")

SITE_NAME = "BunkerWeb documentation"

DESCRIPTION = (
    "BunkerWeb is a next-generation, open-source Web Application Firewall (WAF). "
    "Based on NGINX under the hood, it protects web services to make them secure "
    "by default. It integrates seamlessly into existing environments (Linux, Docker, "
    "Swarm, Kubernetes) as a reverse proxy and is fully configurable via environment "
    "variables or an awesome web UI. "
    "Source: https://github.com/bunkerity/bunkerweb"
)

SECTIONS = {
    "Getting Started": {
        "index.md": "Introduction and overview of BunkerWeb",
        "concepts.md": "Core concepts — multisite, settings contexts, security modes",
        "quickstart-guide.md": "Quick start guide for first-time setup",
    },
    "Integration Guides": {
        "integrations.md": "Docker, Kubernetes, Swarm, Linux, and Ansible setup",
    },
    "Configuration Reference": {
        "features.md": "Complete settings reference — all plugins, all options",
    },
    "Advanced Usage": {
        "advanced.md": "Custom configs, headers, ModSecurity, PHP, streaming, and more",
    },
    "Web UI & API": {
        "web-ui.md": "Web UI usage guide",
        "api.md": "REST API documentation",
    },
    "Plugin System": {
        "plugins.md": "Writing and using external plugins",
    },
    "Operations": {
        "upgrading.md": "Version migration and upgrade guides",
        "troubleshooting.md": "Common issues and solutions",
    },
}

# Patterns to strip from markdown content for LLM consumption.
# These operate OUTSIDE fenced code blocks only (see _clean_markdown).
_STRIP_PATTERNS = [
    re_compile(r"<figure[^>]*>.*?</figure>", DOTALL),
    re_compile(r"<iframe[^>]*>.*?</iframe>", DOTALL),
    re_compile(r"<img[^>]*>"),
]
# Image markdown: preserve alt text as [Image: description]
_IMAGE_RE = re_compile(r"!\[([^\]]*)\]\([^)]*\)(\{[^}]*\})?")
_COLLAPSE_BLANK_LINES = re_compile(r"\n{3,}")
# Convert relative .md links to absolute URLs
_RELATIVE_LINK_RE = re_compile(r"\]\((?!http)([a-zA-Z][^)]*?)\.md(#[^)]*?)?\)")
_FENCE_RE = re_compile(r"^(`{3,}|~{3,})(.*)$")
_HEADING_RE = re_compile(r"^(#{1,6})\s+(.+)$")
_TAB_RE = re_compile(r'^=== "(.+)"')


def _clean_markdown(content, base_url):
    """Remove images, iframes, and HTML blocks from markdown content.

    Processes only text outside fenced code blocks to avoid corrupting code examples.
    """
    # Split on fenced code block boundaries (``` or ~~~)
    parts = split(r"(^```.*?^```|^~~~.*?^~~~)", content, flags=MULTILINE | DOTALL)

    cleaned_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inside a fenced code block — keep as-is
            cleaned_parts.append(part)
        else:
            # Outside code blocks — apply stripping
            for pattern in _STRIP_PATTERNS:
                part = pattern.sub("", part)
            # Preserve image alt text
            part = _IMAGE_RE.sub(lambda m: f"[Image: {m.group(1)}]" if m.group(1) else "", part)
            # Convert relative .md links to absolute
            if base_url:
                part = _RELATIVE_LINK_RE.sub(
                    lambda m: f"]({base_url}/{m.group(1).replace('.md', '')}/{m.group(2) or ''})",
                    part,
                )
            cleaned_parts.append(part)

    return _COLLAPSE_BLANK_LINES.sub("\n\n", "".join(cleaned_parts)).strip()


def _get_page_title(content):
    """Extract the first H1 title from markdown content."""
    for line in content.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _doc_base_url(site_url: str, version: str | None) -> str:
    """Return the docs base URL without a trailing slash, pinned to the mike version when one is set."""
    if version is None:
        return site_url.rstrip("/")
    url = urlsplit(site_url)
    return f"{url.scheme}://{url.netloc}/{quote(version, safe='~.-_')}"


def _split_row(line: str) -> list[str]:
    """Split a markdown table row into cells, keeping escaped pipes inside a cell."""
    cells = []
    start = backslashes = 0
    line = line.strip().strip("|")
    for i, char in enumerate(line):
        if char == "|" and backslashes % 2 == 0:
            cells.append(line[start:i].replace(r"\|", "|").strip())
            start = i + 1
        backslashes = backslashes + 1 if char == "\\" else 0
    cells.append(line[start:].replace(r"\|", "|").strip())
    return cells


def parse_settings(markdown: str) -> list[dict]:
    """Parse the five-column settings tables of features.md, merging repeated names into variants."""
    rows = {}
    heading = section = tab = fence = None
    in_table = False
    for line in markdown.splitlines():
        line = line.strip()
        marker = _FENCE_RE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            in_table = False
            continue
        title = _HEADING_RE.match(line)
        if title:
            tab = None
            in_table = False
            if len(title[1]) == 2:
                heading = _STRIP_PATTERNS[2].sub("", title[2]).strip()
                section = None
            elif len(title[1]) in (3, 4):
                section = title[2]
            continue
        label = _TAB_RE.match(line)
        if label:
            tab = label[1]
        if not line.startswith("|"):
            in_table = False
            continue
        cells = _split_row(line)
        if cells == ["Setting", "Default", "Context", "Multiple", "Description"]:
            in_table = True
            continue
        if not in_table or not heading or len(cells) != 5 or cells[2] not in ("global", "multisite"):
            continue
        name, default, context, multiple, description = cells
        name = name.strip("`")
        variant = {"section": section, "tab": tab, "description": description}
        if name in rows:
            first = rows[name]
            if "variants" not in first:
                first["variants"] = [{key: first[key] for key in variant}]
            first["variants"].append(variant)
            continue
        rows[name] = {
            "name": name,
            "default": default.strip("`"),
            "context": context,
            "multiple": multiple.lower() == "yes",
            "description": description,
            "section": section,
            "tab": tab,
            "plugin": heading.removesuffix(" (PRO)").strip(),
            "pro": heading.endswith("(PRO)"),
            "slug": slugify(heading, "-"),
        }
    return list(rows.values())


def _write_settings(site_dir: Path, rows: list[dict], base_url: str, version: str | None) -> int:
    """Write settings/index.json and one settings/<plugin>.json per plugin; return the plugin count."""
    target = site_dir / "settings"
    target.mkdir(parents=True, exist_ok=True)
    index = {"version": version, "source": f"{base_url}/features/", "settings": {row["name"]: row["slug"] for row in rows}}
    (target / "index.json").write_text(dumps(index, ensure_ascii=False, indent=None), encoding="utf-8")
    plugins = {}
    for row in rows:
        plugin = plugins.setdefault(
            row["slug"],
            {"version": version, "plugin": row["plugin"], "pro": row["pro"], "url": f"{base_url}/features/#{row['slug']}", "settings": []},
        )
        plugin["settings"].append({key: row[key] for key in ("name", "default", "context", "multiple", "description", "variants") if key in row})
    for slug, plugin in plugins.items():
        (target / f"{slug}.json").write_text(dumps(plugin, ensure_ascii=False, indent=None), encoding="utf-8")
    return len(plugins)


def _write_page_sitemaps(site_dir):
    """Copy the root sitemap beside each page for Material's language selector."""
    sitemap = site_dir / "sitemap.xml"
    if not sitemap.is_file():
        log.warning("llmstxt: Root sitemap not found; page-local copies were not generated")
        return 0

    content = sitemap.read_bytes()
    count = 0
    for index_path in site_dir.rglob("index.html"):
        target = index_path.parent / "sitemap.xml"
        if target == sitemap:
            continue
        target.write_bytes(content)
        count += 1
    return count


def on_post_build(config, **kwargs):
    """Generate llms.txt and llms-full.txt after the build completes."""
    site_dir = Path(config["site_dir"])
    # mike rewrites site_url to canonical latest/ during deploy; MIKE_DOCS_VERSION holds the real version.
    base_url = _doc_base_url(config.get("site_url") or "", os.environ.get("MIKE_DOCS_VERSION"))

    # Always read from the project-root docs/ directory (English source),
    # not config["docs_dir"] which the i18n plugin changes per locale.
    config_file = config.get("config_file_path")
    if config_file:
        docs_dir = Path(config_file).parent / "docs"
    else:
        docs_dir = Path(config["docs_dir"])

    settings_rows = []
    features = docs_dir / "features.md"
    if features.is_file():
        settings_rows = parse_settings(features.read_text(encoding="utf-8"))
        plugin_count = _write_settings(site_dir, settings_rows, base_url, os.environ.get("MIKE_DOCS_VERSION"))
        log.info("llmstxt: Generated %d settings in %d plugin files", len(settings_rows), plugin_count)
    else:
        log.warning("llmstxt: Source file 'features.md' not found. Skipping settings files.")

    # Build llms.txt index
    lines = [f"# {SITE_NAME}\n"]
    lines.append(f"> {DESCRIPTION}\n")

    # Build llms-full.txt content
    full_parts = [f"# {SITE_NAME}\n"]
    full_parts.append(f"> {DESCRIPTION}\n")

    for section_name, pages in SECTIONS.items():
        lines.append(f"## {section_name}\n")
        full_section_parts = []

        for filename, description in pages.items():
            src_path = docs_dir / filename
            if not src_path.exists():
                log.warning("llmstxt: Source file '%s' not found. Skipping.", filename)
                continue

            content = src_path.read_text(encoding="utf-8")
            title = _get_page_title(content) or filename.replace(".md", "").replace("-", " ").title()

            # Page URL: filename without .md extension becomes directory/
            page_slug = filename.replace(".md", "")
            if page_slug == "index":
                md_url = f"{base_url}/index.md"
            else:
                md_url = f"{base_url}/{page_slug}/index.md"

            lines.append(f"- [{title}]({md_url}): {description}")

            # Clean content for full output
            cleaned = _clean_markdown(content, base_url)
            full_section_parts.append(cleaned)

            # Write per-page .md companion file next to the HTML output
            if page_slug == "index":
                companion_path = site_dir / "index.md"
            else:
                companion_dir = site_dir / page_slug
                companion_dir.mkdir(parents=True, exist_ok=True)
                companion_path = companion_dir / "index.md"
            companion_path.write_text(cleaned, encoding="utf-8")

        lines.append("")
        full_parts.append(f"# {section_name}\n")
        full_parts.append("\n\n".join(full_section_parts))
        full_parts.append("")

        if section_name == "Configuration Reference" and settings_rows:
            lines.append("## Settings lookup\n")
            lines.append(
                f"- [Settings index]({base_url}/settings/index.json): exact setting name → plugin file; "
                "then fetch settings/<plugin>.json for default, context, multiple and description"
            )
            plugins = {row["slug"]: row["plugin"] for row in settings_rows}
            lines.extend(f"- [{plugin}]({base_url}/settings/{slug}.json)" for slug, plugin in plugins.items())
            lines.append("")

    # Write llms.txt
    llms_txt = site_dir / "llms.txt"
    llms_txt.write_text("\n".join(lines), encoding="utf-8")
    log.info("llmstxt: Generated %s", llms_txt)

    # Write llms-full.txt
    llms_full = site_dir / "llms-full.txt"
    llms_full.write_text("\n".join(full_parts), encoding="utf-8")
    log.info("llmstxt: Generated %s (%dKB)", llms_full, llms_full.stat().st_size // 1024)

    sitemap_count = _write_page_sitemaps(site_dir)
    log.info("llmstxt: Generated %d page-local sitemap copies", sitemap_count)

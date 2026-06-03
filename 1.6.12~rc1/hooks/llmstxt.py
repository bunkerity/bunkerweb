"""MkDocs hook to generate llms.txt and llms-full.txt for AI agent consumption."""

from logging import getLogger
from pathlib import Path
from re import DOTALL, MULTILINE, compile as re_compile, split

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


def on_post_build(config, **kwargs):
    """Generate llms.txt and llms-full.txt after the build completes."""
    site_dir = Path(config["site_dir"])
    base_url = (config.get("site_url") or "").rstrip("/")

    # Always read from the project-root docs/ directory (English source),
    # not config["docs_dir"] which the i18n plugin changes per locale.
    config_file = config.get("config_file_path")
    if config_file:
        docs_dir = Path(config_file).parent / "docs"
    else:
        docs_dir = Path(config["docs_dir"])

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

    # Write llms.txt
    llms_txt = site_dir / "llms.txt"
    llms_txt.write_text("\n".join(lines), encoding="utf-8")
    log.info("llmstxt: Generated %s", llms_txt)

    # Write llms-full.txt
    llms_full = site_dir / "llms-full.txt"
    llms_full.write_text("\n".join(full_parts), encoding="utf-8")
    log.info("llmstxt: Generated %s (%dKB)", llms_full, llms_full.stat().st_size // 1024)

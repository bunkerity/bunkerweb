"""MkDocs hook: make the hreflang alternates absolute and add x-default.

Google ignores an alternate link whose href is relative, and Material writes each one
relative to the page. Each href is resolved against the page's canonical URL, which
follows the version prefix mike sets in site_url at deploy time.
"""

from re import compile as re_compile
from urllib.parse import urljoin

DEFAULT_LANGUAGE = "en"  # the `default: true` locale in mkdocs.yml
_ALTERNATE_RE = re_compile(r'<link rel="alternate" href="([^"]*)" hreflang="([^"]*)">')


def on_post_page(output, page, config):
    base = page.canonical_url
    if not base:
        return output

    def absolute(match):
        link = f'<link rel="alternate" href="{urljoin(base, match.group(1))}" hreflang="{match.group(2)}">'
        # the default language is the fallback for visitors none of the others fit
        if match.group(2) == DEFAULT_LANGUAGE:
            link += link.replace(f'hreflang="{match.group(2)}"', 'hreflang="x-default"')
        return link

    return _ALTERNATE_RE.sub(absolute, output)

# AGENTS.md

Agent guide for the user-facing documentation in `docs/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../AGENTS.md](../AGENTS.md) (short) and [../CLAUDE.md](../CLAUDE.md) (architecture)
- Plugin contract: [../src/common/core/AGENTS.md](../src/common/core/AGENTS.md)

## What This Is

The published documentation at <https://docs.bunkerweb.io>, built with MkDocs Material. `mkdocs.yml` and `mkdocs_print.yml` live at the **repo root**, not here. `docs/Dockerfile` pins the mkdocs-material image by digest.

Content is one Markdown file per topic at the top level (`quickstart-guide.md`, `concepts.md`, `features.md`, `advanced.md`, `integrations.md`, `plugins.md`, `web-ui.md`, `api.md`, `upgrading.md`, `troubleshooting.md`, …), with a folder per locale mirroring the same filenames — the nav in `mkdocs.yml` is language-agnostic and the `i18n` plugin resolves each locale by folder. `i18n` runs first so search, social and print-site see localized pages.

`docs/hooks/llmstxt.py` is a build hook. `docs/assets/`, `docs/diagrams/`, `docs/overrides/` and `docs/misc/` hold the supporting files.

## The Trap Worth Knowing

`json2md.py` generates the settings documentation from plugin metadata, and **a plugin's `README.md` wins over its `plugin.json` settings table**. Concretely:

- A setting added without touching that plugin's `README.md` never appears in the docs — the generator prints the README instead of the generated table.
- A plugin whose `settings` object is empty is **skipped entirely** and can only be documented by hand in `advanced.md` or `web-ui.md`.
- `json2md.py` runs in **no CI job and no pre-commit hook**. Nothing will tell you the docs went stale.
- It reads `DOCS_LANG` and emits one locale at a time.
- Do **not** unescape `\|` in generated output: `pytablewriter` escapes pipes in cell values so a default like `GET|POST|HEAD` renders inside a Markdown table cell instead of splitting it into columns. Included READMEs rely on the same escaping.

So: **changing a setting is a two-file change** — `plugin.json` and the plugin's `README.md`.

## Conventions

- Locale folders mirror the English filenames exactly; a new page means a file in each locale that ships it.
- Prettier (via pre-commit) formats Markdown here; codespell runs over it too, with `docs/json2md.py` on the skip list.
- Everything under `docs/superpowers/` is local working material, not published content.

## Scope Note

The content pass over the user documentation — the missing feature pages, the CHANGELOG, the README, the translation sweep — belongs to the 1.7 closing documentation chantier, not to routine work. This guide covers **how the docs are produced**, so a change to a setting or a plugin does not silently skip them.

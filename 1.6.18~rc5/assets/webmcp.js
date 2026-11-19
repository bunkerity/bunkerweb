(async function () {
  function createTools(env) {
    const pages = [
      "index",
      "concepts",
      "quickstart-guide",
      "integrations",
      "features",
      "advanced",
      "web-ui",
      "api",
      "plugins",
      "upgrading",
      "troubleshooting",
    ];
    const searchIndexes = new Map();
    const versionProperty = { type: "string" };
    const versionName = (root) =>
      decodeURIComponent(root.pathname.split("/").filter(Boolean).pop() || "");

    async function response(url) {
      const result = await env.fetch(url.href);
      if (!result.ok)
        throw new Error(`Cannot read ${url.href}: HTTP ${result.status}`);
      return result;
    }

    async function versions() {
      return (await response(new URL("/versions.json", env.origin))).json();
    }

    async function resolveRoot(version) {
      if (version === undefined) return env.root;
      const entries = await versions();
      const entry = entries.find(
        (item) =>
          item.version === version || (item.aliases || []).includes(version),
      );
      if (!entry)
        throw new Error(`Unknown version "${version}"; call list_versions`);
      return new URL("/" + encodeURIComponent(entry.version) + "/", env.origin);
    }

    function shorten(text, length) {
      return text.length <= length
        ? text
        : text.slice(0, Math.max(0, length - 1)) + (length ? "…" : "");
    }

    function sectionText(markdown, section) {
      let fence = null;
      let start = null;
      let level = 0;
      let offset = 0;
      for (const line of markdown.split("\n")) {
        const marker = line.match(/^\s*(`{3,}|~{3,})(.*)$/);
        if (fence) {
          if (
            marker &&
            marker[1][0] === fence[0] &&
            marker[1].length >= fence.length &&
            !marker[2].trim()
          )
            fence = null;
        } else if (marker) {
          fence = marker[1];
        } else {
          const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
          if (heading) {
            if (start !== null && heading[1].length <= level)
              return markdown.slice(start, offset);
            if (
              start === null &&
              heading[2].toLowerCase() === section.toLowerCase()
            ) {
              start = offset;
              level = heading[1].length;
            }
          }
        }
        offset += line.length + 1;
      }
      if (start === null) throw new Error(`Section "${section}" not found`);
      return markdown.slice(start);
    }

    return [
      {
        name: "get_setting",
        description:
          "Look up an English BunkerWeb setting, its default, scope and documentation for a docs version.",
        inputSchema: {
          type: "object",
          properties: {
            name: { type: "string", pattern: "^[A-Za-z0-9._-]{1,200}$" },
            version: versionProperty,
          },
          required: ["name"],
        },
        async execute({ name, version }) {
          if (typeof name !== "string" || !/^[A-Za-z0-9._-]{1,200}$/.test(name))
            throw new Error("Invalid setting name");
          const root = await resolveRoot(version);
          const indexResponse = await env.fetch(
            new URL("settings/index.json", root).href,
          );
          if (indexResponse.status === 404) {
            throw new Error(
              `Settings files are not published for ${versionName(root)}; use read_doc with page "features"`,
            );
          }
          if (!indexResponse.ok)
            throw new Error(
              `Cannot read settings index: HTTP ${indexResponse.status}`,
            );
          const index = await indexResponse.json();
          const requested = name;
          if (!Object.prototype.hasOwnProperty.call(index.settings, name)) {
            const prefixed = name.match(/^[a-z0-9.-]+_([A-Z][A-Z0-9_]*)$/);
            if (prefixed) name = prefixed[1];
          }
          let numbered = false;
          if (!Object.prototype.hasOwnProperty.call(index.settings, name)) {
            const multiple = name.match(/^(.+)_\d+$/);
            if (multiple) {
              name = multiple[1];
              numbered = true;
            }
          }
          let plugin;
          let row;
          if (Object.prototype.hasOwnProperty.call(index.settings, name)) {
            plugin = await (
              await response(
                new URL(`settings/${index.settings[name]}.json`, root),
              )
            ).json();
            row = plugin.settings.find((setting) => setting.name === name);
          }
          if (!row || (numbered && !row.multiple)) {
            return {
              found: false,
              requested,
              suggestions: Object.keys(index.settings)
                .filter((key) => key.split("_")[0] === name.split("_")[0])
                .slice(0, 5),
              hint: "Use search_docs",
            };
          }
          const result = {
            found: true,
            name: row.name,
            requested,
            plugin: plugin.plugin,
            pro: plugin.pro,
            default: row.default,
            context: row.context,
            multiple: row.multiple,
            description: shorten(row.description, 900),
            url: plugin.url,
            version: plugin.version || versionName(root),
          };
          if (row.variants) {
            result.variants = row.variants.map(
              (variant) => variant.tab || variant.section,
            );
            result.variants_section = row.variants[0].section;
            result.hint = `Use read_doc with page "features" and section ${result.variants_section}, following next_offset`;
          }
          const excess = JSON.stringify(result).length - 1500;
          if (excess > 0)
            result.description = shorten(
              result.description,
              Math.max(0, result.description.length - excess),
            );
          return result;
        },
      },
      {
        name: "search_docs",
        description:
          "Search English BunkerWeb documentation for a docs version; return short excerpts and links.",
        inputSchema: {
          type: "object",
          properties: {
            query: { type: "string", minLength: 1, maxLength: 200 },
            limit: { type: "integer", minimum: 1, maximum: 10, default: 5 },
            version: versionProperty,
          },
          required: ["query"],
        },
        async execute({ query, limit = 5, version }) {
          if (
            typeof query !== "string" ||
            query.length < 1 ||
            query.length > 200
          )
            throw new Error("Invalid search query");
          if (!Number.isInteger(limit) || limit < 1 || limit > 10)
            throw new Error("Invalid search limit");
          const root = await resolveRoot(version);
          if (!searchIndexes.has(root.href)) {
            const index = await (
              await response(new URL("search/search_index.json", root))
            ).json();
            searchIndexes.set(root.href, index);
          }
          const terms = query
            .toLowerCase()
            .split(/\W+/)
            .filter((term) => term.length >= 2);
          const results = searchIndexes
            .get(root.href)
            .docs.filter((doc) => !/^(fr|de|es|zh)\//.test(doc.location))
            .map((doc) => {
              const text = doc.text.replace(/<[^>]*>/g, "");
              const score = terms.reduce(
                (sum, term) =>
                  sum +
                  (doc.title.toLowerCase().includes(term) ? 5 : 0) +
                  Math.min(5, text.toLowerCase().split(term).length - 1),
                0,
              );
              return { doc, text, score };
            })
            .filter((hit) => hit.score > 0)
            .sort((left, right) => right.score - left.score)
            .slice(0, limit)
            .map((hit) => ({
              title: hit.doc.title,
              url: new URL(hit.doc.location, root).href,
              snippet: shorten(hit.text, 160),
            }));
          return { version: versionName(root), results };
        },
      },
      {
        name: "read_doc",
        description:
          "Read an English BunkerWeb documentation page or heading section in chunks; follow next_offset.",
        inputSchema: {
          type: "object",
          properties: {
            page: { type: "string", enum: pages },
            section: { type: "string" },
            offset: { type: "integer", minimum: 0 },
            version: versionProperty,
          },
          required: ["page"],
        },
        async execute({ page, section, offset = 0, version }) {
          if (!pages.includes(page))
            throw new Error("Invalid documentation page");
          if (!Number.isInteger(offset) || offset < 0)
            throw new Error("Invalid documentation offset");
          if (section !== undefined && typeof section !== "string")
            throw new Error("Invalid documentation section");
          const root = await resolveRoot(version);
          const path = page === "index" ? "" : `${page}/`;
          let markdown = await (
            await response(new URL(`${path}index.md`, root))
          ).text();
          if (section !== undefined) markdown = sectionText(markdown, section);
          return {
            page,
            section: section === undefined ? null : section,
            url: new URL(path, root).href,
            text: markdown.slice(offset, offset + 4000),
            offset,
            next_offset: offset + 4000 < markdown.length ? offset + 4000 : null,
            total: markdown.length,
          };
        },
      },
      {
        name: "list_versions",
        description:
          "List published BunkerWeb docs versions and aliases, including the current version when hidden.",
        inputSchema: { type: "object", properties: {} },
        async execute() {
          const current = versionName(env.root);
          return {
            current,
            versions: (await versions())
              .filter(
                (entry) =>
                  !entry.properties?.hidden ||
                  entry.version === current ||
                  (entry.aliases || []).includes(current),
              )
              .map((entry) => ({
                version: entry.version,
                aliases: entry.aliases || [],
              })),
          };
        },
      },
    ].map((tool) => ({ ...tool, annotations: { readOnlyHint: true } }));
  }

  if (
    typeof document?.modelContext?.registerTool !== "function" ||
    !(window.__md_scope instanceof URL)
  )
    return;
  try {
    for (const tool of createTools({
      fetch: fetch.bind(window),
      root: window.__md_scope,
      origin: window.__md_scope.origin,
    })) {
      await document.modelContext.registerTool(tool);
    }
  } catch (err) {
    console.warn("BunkerWeb docs WebMCP tools not registered:", err);
  }
})().catch(() => {});

# Copilot Instructions for BunkerWeb

## Project Overview

- **BunkerWeb** is a next-generation, open-source Web Application Firewall (WAF) built on top of NGINX, with a modular, plugin-based architecture.
- Major components: core (security logic), scheduler (configuration and job orchestration), web UI (management), plugin system (feature extension), and integrations (Docker, Kubernetes, Swarm, Linux, Azure).
- Configuration is driven by environment variables (settings), custom NGINX/ModSecurity configs, and a backend database (SQLite, MariaDB, MySQL, PostgreSQL).

## Key Directories

- `src/`: Main source code (core, scheduler, plugins, UI, integrations)
- `docs/`: Documentation, guides, and assets
- `examples/`: Real-world configuration and deployment examples
- `tests/`: Test scripts and scenarios
- `misc/`: Utilities, scripts, and ASCII art

## Developer Workflows

- **Build/Run**: See `docs/quickstart-guide.md` and `README.md` for integration-specific instructions (Linux, Docker, Kubernetes, etc.).
- **Testing**: Use scripts in `tests/` (e.g., `main.py`, `AutoconfTest.py`, `SwarmTest.py`).
- **Debugging**: Logs and job execution are managed by the scheduler; use the web UI for live monitoring and troubleshooting.
- **Plugins**: Add new features by placing plugins in the appropriate directory and updating settings. See `docs/plugins.md` and the [bunkerweb-plugins repo](https://github.com/bunkerity/bunkerweb-plugins).

## Project-Specific Conventions

- **Settings**: All configuration is via environment variables (e.g., `USE_ANTIBOT=captcha`). In multisite mode, prefix with the server name (e.g., `www.example.com_USE_ANTIBOT=captcha`).
- **Multiple values**: Use numbered suffixes for repeated settings (e.g., `REVERSE_PROXY_URL_1`, `REVERSE_PROXY_URL_2`).
- **Custom configs**: Place NGINX/ModSecurity customizations in designated config files or via the web UI.
- **Localization**: UI translations in `src/ui/app/static/locales/`.

## Integration Patterns

- **Scheduler** is the central orchestrator for config, jobs, and service communication.
- **Autoconf** listens for environment events (Docker, Swarm, Kubernetes) and updates config in real time.
- **Web UI** interacts with the scheduler/database for live management.
- **Plugins** extend core via settings and hooks; see plugin README files for details.

## Examples

- See `examples/` for integration and configuration samples.
- See `src/common/core/` for core security modules (each with its own README).

## External Resources

- [Documentation](https://docs.bunkerweb.io)
- [Web UI Demo](https://demo-ui.bunkerweb.io)
- [Plugins](https://github.com/bunkerity/bunkerweb-plugins)

## Contributing

- Follow the [CONTRIBUTING.md](../CONTRIBUTING.md) and [SECURITY.md](../SECURITY.md) guidelines.
- Use the [web UI](https://docs.bunkerweb.io/web-ui/) for most configuration and debugging tasks.

---

**Tip:** For new features, follow the patterns in `src/common/core/` and `src/ui/`. For integrations, reference the relevant subdirectory in `examples/` and `docs/`.

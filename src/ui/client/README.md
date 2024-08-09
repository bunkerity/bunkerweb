# General

Vite.js will be use to build needed pages and resources (CSS, JS...) for the BunkerWeb UI.

# Structure

We have two main folders :
- `dashboard` with a multi page approach, this part is used to dev main pages on the dashboard. Use `vite.config.dashboard.js`.
- `setup` that is special because we need a all-in-one HTML file for the setup page. Use `vite.config.setup.js`.

# Dev mode client only

In case you want to check pages without build, you can run available scripts in `package.json`.
For example, you need to execute `npm run dev-dashboard` to run a vite dev server.

# Dev mode BunkerWeb UI

In case you want to run the BunkerWeb UI, try to update front-end and get the modifications on your app, you need to do the following :
- go to `misc/dev` path and run `docker compose -f docker-compose.ui.yml up --build` in order to create BunkerWeb with UI looking for local static and templates folder
- update front-end in dev mode and run inside `cd/src/ui/client` : `python build.py` to rebuild setup and dashboard pages.

# Prod mode

You only have to run a basic `docker-compose` and `src/ui/Dockerfile` will build the front automatically.

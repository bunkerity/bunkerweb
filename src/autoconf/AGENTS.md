# AGENTS.md

Agent guide for BunkerWeb Autoconf in `src/autoconf/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- API guide: [../api/AGENTS.md](../api/AGENTS.md) — Autoconf's only write path

## What This Is

Autoconf watches container/orchestrator events (Docker, Swarm, Kubernetes) and reconfigures BunkerWeb by translating labels and annotations into settings, persisted through the FastAPI API. The Scheduler picks the changes up from there. Autoconf has **no database dependency**.

## Critical Rules

- Configuration is written **only** through the API. Never add a direct DB path.
- Controllers translate labels/annotations into settings, services, instances and custom configs — nothing else.
- Preserve the shared debounce and the `update_needed()`-before-`apply()` pattern.
- `apply()` must signal the Scheduler through the API metadata and checked-changes calls.
- API degraded mode keeps watching events and skips writes until the API recovers. Do not turn it into a hard failure.
- Swarm is supported, not deprecated — see the Swarm rules below.

## Architecture

### Class hierarchy

```
Config (Config.py)
  └── Controller (controllers/Controller.py)              # abstract base
        ├── DockerController                              # standalone Docker
        ├── SwarmController                               # Docker Swarm
        └── KubernetesController                          # concrete K8s base
              ├── IngressController                       # K8s Ingress API
              └── GatewayController                       # K8s Gateway API
```

`Config` owns settings validation, change detection (`update_needed`), API writes (`apply`) and waiting for the Scheduler (`wait_applying`). `Controller` adds instance/service discovery abstractions and the event-loop skeleton. Concrete controllers implement platform discovery and event handling.

`AutoconfApiClient` (`api_client.py`) subclasses `BaseApiClient` (`src/common/utils/base_api_client.py`) — the same base the UI's client extends.

### Startup

1. Detect the mode from `SWARM_MODE`, `KUBERNETES_MODE`, `KUBERNETES_GATEWAY_MODE`.
2. Build `AutoconfApiClient` from `API_URL` and `API_TOKEN`.
3. Instantiate the controller (passing `api_client`).
4. `controller.wait()` — poll until the API is ready and at least one healthy instance exists.
5. `controller.initial_apply()` — first gather and apply.
6. `controller.process_events()` — the infinite event loop.

### Event processing

All controllers share a debounced loop (2-second window):

1. Receive the platform event (Docker event stream, K8s watch).
2. Filter on relevant labels/annotations, and on `NAMESPACES` when set.
3. Set `pending_apply = True` and record the timestamp.
4. Sleep until the window passes with no new event.
5. Re-discover instances, services and configs from the platform.
6. If `update_needed()` reports changes, `apply()`.
7. `apply()` calls `save_config()`, `save_custom_configs()`, `update_instances()`, then `checked_changes()` to signal the Scheduler.

Docker and Swarm share one debounce/batch/apply loop, `Controller._run_event_loop`. They used to carry near-identical copies, so a fix to one bypassed the other — **do not re-inline it**.

### Labels and annotations

- **Docker/Swarm**: labels prefixed `bunkerweb.` (`bunkerweb.SERVER_NAME`, `bunkerweb.INSTANCE`).
- **Kubernetes**: annotations prefixed `bunkerweb.io/`.
- Custom configs: `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` labels on Docker, ConfigMaps annotated `bunkerweb.io/CONFIG_TYPE` on K8s.
- Ignore filtering: `DOCKER_IGNORE_LABELS`, `SWARM_IGNORE_LABELS`, `KUBERNETES_IGNORE_ANNOTATIONS`.

### Kubernetes

- **KubernetesController** (base): watches Pods, ConfigMaps, Services and Secrets; `get_configs()` returns both extra settings (from `settings`-type ConfigMaps) and custom configs; detects the LoadBalancer IP for status patching; threaded watchers retry on `410 Gone` (expired resource version).
- **IngressController**: translates Ingress rules into `REVERSE_PROXY_HOST_N`/`REVERSE_PROXY_URL_N`, handles TLS secrets, supports `KUBERNETES_INGRESS_CLASS` filtering.
- **GatewayController**: Gateway API with HTTPRoute, GRPCRoute, TLSRoute, TCPRoute and UDPRoute. Auto-detects the available CRD versions, resolves listeners for hostname/port/protocol/TLS, caches gateways per cycle, patches Gateway status with LoadBalancer addresses.

### API interaction

- **Hybrid availability**: `_check_api_available()` checks `_api.readonly` before writes. An unreachable API drops into degraded mode (`_api_available = False`) — events keep being watched, `apply()` is skipped, recovery happens automatically on the next `ping()`.
- **Change signaling**: `checked_changes()` sets the metadata flags the Scheduler watches.
- **Settings validation**: each setting extracted from a label goes through `validate_setting()` (`POST /global_settings/validate`).

The endpoints used are plugins/services/instances reads, the bulk instance and config writes, the global-settings config write, metadata read and patch, and `POST /system/checked-changes`. Check `api_client.py` for the current exact set.

### Threading

- **Docker**: single-threaded loop on `client.events()`, with an internal lock for the debounce.
- **Swarm**: two threads, one for `service` events and one for `config` events, sharing a lock.
- **Kubernetes**: one thread per watcher type (pod, configmap, service, secret, ingress/gateway routes), all sharing `_internal_lock`.

## Build and Run

```bash
docker build -f src/autoconf/Dockerfile -t bunkerweb-autoconf:dev .
docker compose -f misc/dev/docker-compose.autoconf.yml up -d
docker compose -f misc/dev/docker-compose.autoconf.yml up -d --force-recreate bw-autoconf
pip install --require-hashes -r src/autoconf/requirements.txt
```

Multi-stage Dockerfile; the final image runs as the `autoconf` user (UID 101). The dev compose does **not** volume-mount the source — rebuild and recreate for code changes.

## Runtime Gotchas

- **Swarm: an instance service must be `mode: global`.** The controller refuses a replicated one. The registered hostname is `<service>.<NodeID>.<TaskID>`, which only resolves for a global service; a replicated service's tasks are `<service>.<slot>.<TaskID>` and unreachable from the control plane.
- **Swarm: `bunkerweb.CUSTOM_CONF_*` labels are Docker-only and inert here.** The controller warns once per service; the Swarm route is a `docker config` object labelled `bunkerweb.CONFIG_TYPE`.
- **Swarm: a task's `Status.State == "running"` is already gated on the container HEALTHCHECK** by swarmkit, in both directions. Do not add a container-inspect tier — it cannot work off-node anyway.
- `API_ERROR_TIMEOUT` controls when repeated API failures escalate warnings to errors in `wait_applying()`.
- All controllers use a `_first_start` flag to apply unconditionally on the first cycle, and `_set_autoconf_loaded()` sets the `autoconf_loaded` metadata **once**, after the first successful apply.
- Health: `/var/tmp/bunkerweb/autoconf.healthy` is written when the event loop starts and removed on exit.

## Environment

| Variable                                | Default                       | Purpose                                               |
| --------------------------------------- | ----------------------------- | ----------------------------------------------------- |
| `SWARM_MODE`                            | `no`                          | Enable the Swarm controller                           |
| `KUBERNETES_MODE`                       | `no`                          | Enable the Kubernetes Ingress controller              |
| `KUBERNETES_GATEWAY_MODE`               | `no`                          | Enable the Kubernetes Gateway API controller          |
| `DOCKER_HOST`                           | `unix:///var/run/docker.sock` | Docker socket                                         |
| `WAIT_RETRY_INTERVAL`                   | `5`                           | Seconds between readiness retries                     |
| `NAMESPACES`                            | (all)                         | Space-separated namespace filter                      |
| `USE_KUBERNETES_FQDN`                   | `yes`                         | Pod FQDN instead of IP as hostname                    |
| `KUBERNETES_DOMAIN_NAME`                | `cluster.local`               | Cluster domain                                        |
| `KUBERNETES_SERVICE_PROTOCOL`           | `http`                        | Protocol for backend service URLs                     |
| `KUBERNETES_REVERSE_PROXY_SUFFIX_START` | `1`                           | Starting index for numbered reverse-proxy settings    |
| `API_URL`                               | `http://bw-api:5000`          | API base URL                                          |
| `API_TOKEN`                             | (empty)                       | Bearer token                                          |
| `API_ERROR_TIMEOUT`                     | `60`                          | Seconds of consecutive API failures before escalation |

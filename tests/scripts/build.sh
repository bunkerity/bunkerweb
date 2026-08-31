#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"
release="${3:-}"
category="${4:-}"

if [ -z "$release" ] ; then
    log "RUN" "❌" "Please provide a release as 3rd argument"
    exit 1
elif [ -z "$category" ] ; then
    log "RUN" "❌" "Please provide a category as 4th argument"
    exit 1
fi

if ! groups "$(whoami)" | grep -q '\bdocker\b' ; then
  log "BUILD" "ℹ️ " "🐳 Adding user to docker group ..."
  sudo usermod -aG docker "$(whoami)"
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "🐳 Failed to add user to docker group"
    exit 1
  fi
  newgrp docker
fi

if [ "$integration" == "Swarm" ] ; then
  log "BUILD" "ℹ️ " "🐝 Prepping Swarm integration ..."
  # FIRST, before anything starts. Every helper compose pins static addresses in bw-universe /
  # bw-services / bw-db, and on this arm those have to be attachable OVERLAYS: a Swarm service
  # cannot join a bridge, while a standalone container joins an attachable overlay exactly the
  # way it joins a bridge, static address included. So the networks must exist as overlays
  # BEFORE the first container attaches to them.
  #
  # That ordering is load-bearing and was got wrong once: `tests/misc/docker/redis.yml` puts the
  # harness's own redis on bw-universe at 10.20.30.50 and starts immediately below, so with this
  # block any further down the bridge already existed AND was held by a running container --
  # `docker network rm` a no-op, `docker network create` refused, every Swarm run dead on arrival.
  #
  # The two `down -v` calls release what a previous run left behind. Nothing of this run's state
  # is lost: redis has no volume and the first `redis_cli` write happens after it restarts, below.
  # Bringing dnsmasq down is also what makes it re-read tests/misc/conf/dnsmasq.hosts -- it parses
  # that file once, at start, so a surviving container would keep answering 192.168.0.254 for
  # app1.bw-services whatever the sed below writes.
  docker compose -f tests/misc/docker/redis.yml down -v > /dev/null 2>&1
  docker compose -f tests/misc/docker/dnsmasq.yml down -v > /dev/null 2>&1

  # And the database volume, because on THIS arm a stale one is not merely stale, it is poison.
  # The controller registers each instance as `<service>.<NodeID>.<TaskID>`, and the NodeID comes
  # from the swarm -- which this arm creates and leaves on every run, so it is different every
  # time. A `bw-storage` carried over from a previous run therefore holds an instance hostname
  # that can never resolve again: the scheduler pings it through the API, gets 502, reports "one
  # or more BunkerWeb instances are unreachable", and never clears instances_changed. bw-autoconf
  # then waits on that flag forever, fails its healthcheck, and Swarm kills and restarts it in a
  # loop until the stack wait times out -- 300 s of a symptom five layers from the cause.
  # Diagnosed from exactly that: a scheduler pinging node c3u2qmzruri7a5... while `docker stack
  # ps` showed the live task on node 5o11knc01x2xt...
  docker volume rm -f bw-storage > /dev/null 2>&1

  # Once per run, and before the first swarm_ensure_host: it is what makes "this arm created the
  # swarm / the node label" a fact about THIS run rather than a leftover from an earlier one.
  swarm_forget_markers

  swarm_ensure_host || exit 1
  swarm_ensure_networks || exit 1

  # `192.168.0.254 app1.bw-services` and its cacheable-app sibling are static answers for
  # containers that no longer have static addresses: the application layer is a Swarm SERVICE
  # here (it has to be, for the controller to see its labels) and Swarm allocates its VIP from
  # the overlay pool. Commenting the rows out makes dnsmasq forward those names to Docker's own
  # resolver (`server=127.0.0.11` in dnsmasq.conf), which answers with the alias
  # swarm-services.py puts on every converted service. `cleanup_stack` strips the prefix back off.
  sed_in_place 's/^192\.168\.0\.\([0-9]*\) \(.*\.bw-services\)$/#swarm-arm 192.168.0.\1 \2/' tests/misc/conf/dnsmasq.hosts
fi

log "BUILD" "ℹ️ " "💽 Starting redis server ..."
robust_docker_pull "tests/misc/docker/redis.yml" "redis"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  log "BUILD" "❌" "💽 Failed to pull redis server after multiple attempts"
  exit 1
fi

docker compose -f tests/misc/docker/redis.yml up -d
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  log "BUILD" "❌" "💽 Failed to start redis server"
  exit 1
fi

log "BUILD" "ℹ️ " "💽 Waiting for redis server to be healthy ..."
i=0
while [ $i -lt 30 ] ; do
  if redis_cli ping | grep -q "PONG" ; then
    log "BUILD" "ℹ️ " "💽 Redis server is healthy ✅"
    break
  fi
  sleep 1
  i=$((i+1))
done
if [ $i -ge 30 ] ; then
  log "BUILD" "❌" "💽 Redis server is not healthy after 30 seconds"
  exit 1
fi

redis_cli set end 0 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  log "BUILD" "❌" "💽 Failed to set end flag in redis server"
  exit 1
fi

# In CI the images are pulled and retagged by the workflow. Locally nothing has
# produced them, so build the ones this run needs straight from the checkout — that is
# what makes "clone, then run a test" work without a pipeline.
if [ -z "${IN_CICD:-}" ] ; then
  declare -A local_images=(
    ["bunkerity/bunkerweb"]="src/bw/Dockerfile"
    ["bunkerity/bunkerweb-scheduler"]="src/scheduler/Dockerfile"
    ["bunkerity/bunkerweb-api"]="src/api/Dockerfile"
    ["bunkerity/bunkerweb-worker"]="src/worker/Dockerfile"
  )
  # Swarm too: the arm runs a controller, and it is the same image — SWARM_MODE picks
  # SwarmController over DockerController inside it.
  if [ "$integration" == "Autoconf" ] || [ "$integration" == "Swarm" ] || [ "$integration" == "Kubernetes" ] ; then
    local_images["bunkerity/bunkerweb-autoconf"]="src/autoconf/Dockerfile"
  fi
  if [ "$integration" == "All-in-one" ] ; then
    local_images=(["bunkerity/bunkerweb-all-in-one"]="src/all-in-one/Dockerfile")
  fi
  if [ "$type" == "ui" ] ; then
    local_images["bunkerity/bunkerweb-ui"]="src/ui/Dockerfile"
  fi

  # The :tests tag is global to the daemon, so another checkout's build answers to it. A
  # bunkerweb-ui:tests left by a 1.6 tree ran under a 1.7 stack here and every ui spec failed
  # somewhere far away from the cause. Reuse only what carries this checkout's version label.
  checkout_version="$(cat src/VERSION)"
  build_ref="$(mktemp)"
  for image in "${!local_images[@]}" ; do
    if [ -n "$(docker images -q "${image}:tests" 2> /dev/null)" ] ; then
      image_version="$(docker inspect --format '{{index .Config.Labels "version"}}' "${image}:tests" 2> /dev/null)"
      if [ "$image_version" != "$checkout_version" ] ; then
        log "BUILD" "⚠️" "🐳 ${image}:tests is version '${image_version:-unknown}', this checkout is ${checkout_version} — rebuilding"
      else
        # Same version is not the same content. Every image copies part of src/, so an edit
        # made after the last build is invisible to the tag: a fix to src/common/confs sat in
        # bunkerweb:tests and bunkerweb-scheduler:tests while bunkerweb-worker:tests -- which
        # ships the same confs and is what pushes them to the instances -- kept the broken
        # copy, and the spec failed as if nothing had been fixed.
        image_created="$(docker inspect --format '{{.Created}}' "${image}:tests" 2> /dev/null)"
        if [ -n "$image_created" ] && touch -d "$image_created" "$build_ref" 2> /dev/null ; then
          newer="$(find src -type f -newer "$build_ref" -print -quit 2> /dev/null)"
          if [ -z "$newer" ] ; then
            log "BUILD" "ℹ️ " "🐳 Reusing local image ${image}:tests (delete it to force a rebuild)"
            continue
          fi
          log "BUILD" "⚠️" "🐳 ${image}:tests predates $newer — rebuilding"
        else
          log "BUILD" "ℹ️ " "🐳 Reusing local image ${image}:tests (delete it to force a rebuild)"
          continue
        fi
      fi
    fi

    log "BUILD" "ℹ️ " "🐳 Building ${image}:tests from ${local_images[$image]} ..."
    if ! docker build -t "${image}:tests" -f "${local_images[$image]}" . ; then
      log "BUILD" "❌" "🐳 Failed to build ${image}:tests"
      rm -f "$build_ref"
      exit 1
    fi
  done
  rm -f "$build_ref"
fi

if [[ "$category" =~ ";" ]] ; then
  redis_cli lpush tests "$category" > /dev/null
  category=$(echo "$category" | cut -d ";" -f 1)
else
  if [ "$release" == "dev" ] ; then
    python3 tests/parse.py "$type" --integration "$integration" --category "$category" --dev
  else
    python3 tests/parse.py "$type" --integration "$integration" --category "$category"
  fi

  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "✂ Failed to parse tests"
    exit 1
  fi
fi

if [ "$integration" == "Linux" ] ; then
  log "BUILD" "ℹ️ " "🐧 Prepping Linux integration ..."
  # Commented out, not deleted, and `cleanup_stack` strips the prefix back off -- the same shape
  # the Swarm arm uses on dnsmasq.hosts above, for the same reason. Deleting the line loses WHERE
  # it was, and dnsmasq.conf sets `strict-order`: its own comment says Docker's resolver has to be
  # FIRST or a public one answers NXDOMAIN for a container name and ends the query. The teardown
  # used to put it back with `18i`, a hard-coded line number that lands it fourth, below Cloudflare
  # and Google -- so a Linux run left the file semantically changed and the next Autoconf or Docker
  # example could not resolve its own upstream (502, and nothing naming DNS).
  sed_in_place 's/^server=127\.0\.0\.11$/#linux-arm server=127.0.0.11/' tests/misc/conf/dnsmasq.conf
  if ! $IS_FREEBSD ; then
    docker exec -u 0 bunkerweb-linux systemctl disable --now systemd-resolved
    docker exec -u 0 bunkerweb-linux sh -c 'echo "nameserver 127.0.0.1" | tee /etc/resolv.conf'
  fi

  sed_in_place 's/10.20.30.[0-9][0-9]*/127.0.0.1/g' tests/misc/conf/dnsmasq.hosts
  sed_in_place 's/10.10.10.[0-9][0-9]*/127.0.0.1/g' tests/misc/conf/dnsmasq.hosts
  sed_in_place 's@9000@/run/php/php-fpm.sock@g' tests/misc/conf/php-fpm.conf
  if ! $IS_FREEBSD ; then
    nginx_gid="$(docker exec -u 0 bunkerweb-linux id -g nginx)"
    sed_in_place "s/^listen.group =.*$/listen.group = $nginx_gid/g" tests/misc/conf/php-fpm.conf

    # On Linux the helper stands in for a php-fpm installed on the machine, so it has to run as
    # the same user the packaged BunkerWeb serves files as. Its own image numbers www-data
    # differently (82 on Alpine, 33 on Debian), and an example hardens its web root to 0640/0750
    # -- so a mismatch here means php-fpm cannot read a file that is plainly there, and answers
    # "Primary script unknown", which nginx returns as a 404.
    www_uid="$(docker exec -u 0 bunkerweb-linux id -u www-data)"
    sed_in_place "s/^user =.*$/user = $www_uid/g" tests/misc/conf/php-fpm.conf
    sed_in_place "s/^group =.*$/group = $nginx_gid/g" tests/misc/conf/php-fpm.conf
    sed_in_place "s/^listen.owner =.*$/listen.owner = $www_uid/g" tests/misc/conf/php-fpm.conf
  fi
fi

mkdir -p /tmp/output

# Every integration serves /var/www/html off this machine: the containers bind-mount it (in the
# images /var/www/html is a symlink to /data/www, which the entrypoint refuses to start without
# read and execute for nginx), Kubernetes copies it into the node, and the php-fpm helper reads it.
# CI provisions it in the workflow itself, unconditionally ("Setup configuration files" in
# .github/workflows/integration-tests.yml) — a workstation has nothing that does, and it is where
# integrations collide: a Linux example hardens the web root to 0750 for the nginx group as ITS
# container numbers it, which locks out the Docker stack's nginx on the next run. Normalising
# here, before anything starts, is what keeps runs of different integrations independent.
provision_www_root || exit 1

if [ "$integration" != "Kubernetes" ] ; then
  if [ "$integration" != "Linux" ] && [ "$integration" != "Swarm" ] ; then
    log "BUILD" "ℹ️ " "🚀 Prepping $integration integration ..."
  fi

  robust_docker_pull "tests/misc/docker/dnsmasq.yml" "dnsmasq"
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "🤿 Failed to pull dnsmasq after multiple attempts"
    exit 1
  fi

  docker compose -f tests/misc/docker/dnsmasq.yml up -d
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "🤿 Failed to start dnsmasq"
    exit 1
  fi

  if [ "$integration" != "Linux" ] && [ "$integration" != "All-in-one" ] && grep -q "crowdsec" tests/"$type"/"$category".yml ; then
    robust_docker_pull "tests/misc/docker/syslog.yml" "syslog"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
      log "BUILD" "❌" "💬 Failed to pull syslog after multiple attempts"
      exit 1
    fi

    docker compose -f tests/misc/docker/syslog.yml up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
      log "BUILD" "❌" "💬 Failed to start syslog"
      exit 1
    fi
  fi

  if [ "$type" == "core" ] ; then
    # An example-backed spec carries no settings of its own: the example directory holds them,
    # so the helper services a spec needs have to be looked for there too. Without this the
    # php-fpm helper never starts for `example-php-multisite` and every request 502s on a socket
    # nothing is listening on.
    php_sources=("tests/core/$category.yml")
    example_name="$(awk '/^example:[[:space:]]/ {print $2; exit}' "tests/core/$category.yml")"
    if [ -n "$example_name" ] && [ -d "examples/$example_name" ] ; then
      php_sources+=("examples/$example_name")
    fi

    if grep -qr "php-fpm" "${php_sources[@]}" ; then
      robust_docker_pull "tests/misc/docker/php.yml" "php-fpm"
      # shellcheck disable=SC2181
      if [ $? -ne 0 ] ; then
        log "BUILD" "❌" "🐘 Failed to pull php after multiple attempts"
        exit 1
      fi

      docker compose -f tests/misc/docker/php.yml up -d
      # shellcheck disable=SC2181
      if [ $? -ne 0 ] ; then
        log "BUILD" "❌" "🐘 Failed to start php"
        exit 1
      fi
    fi

    if grep -q "custom-api" tests/core/"$category".yml ; then
      docker compose -f tests/misc/docker/custom-api.yml up --build -d
      # shellcheck disable=SC2181
      if [ $? -ne 0 ] ; then
        log "BUILD" "❌" "🔧 Failed to start custom-api"
        exit 1
      fi
    fi

    if [ "$integration" != "All-in-one" ] && grep -q "CROWDSEC_API" tests/core/"$category".yml ; then
        touch /tmp/crowdsec.env
        robust_docker_pull "tests/misc/docker/crowdsec.yml" "CrowdSec"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "BUILD" "❌" "🦙 Failed to pull CrowdSec after multiple attempts"
            exit 1
        fi
    fi
  fi
else
  log "BUILD" "ℹ️ " "🚀 Prepping Kubernetes integration ..."
  if ! minikube status >/dev/null 2>&1; then
    # No sudo gate here any more. It existed only to `kill -9` leftover `minikube mount` processes
    # before starting the cluster, and there are no mounts to leak now -- the fixtures are copied
    # into the node instead. The docker driver itself needs no root, so a cold workstation no longer
    # blocks on a password prompt in the middle of an automated run.
    log "BUILD" "ℹ️ " "☸️ Starting Minikube ..."
    total_memory=$(free -m | awk '/^Mem:/{print $2}')
    memory_limit=$((total_memory * 80 / 100))

    # The shared helper keeps the local pre-flight/start arguments and CI on one list.
    # shellcheck disable=SC1091
    source tests/scripts/minikube-ports.sh

    # Pre-flight, because docker reports only the FIRST conflict and minikube then leaves a
    # half-created node behind: "failed to bind host port 127.0.0.1:7000/tcp: address already in
    # use" after 45 seconds, with no hint about what holds it. A desktop can easily be sitting on
    # one of these (an AirPlay receiver owns :7000, a local MySQL owns :3306). Name every conflict
    # up front, with the process where the kernel will tell us. `UI_HOST_PORT` moves the one that
    # collides most often, the same variable the Docker `ui` stack already honours.
    port_conflicts=()
    for mapping in "${minikube_ports[@]}" ; do
      host_port="${mapping%%:*}"
      if ss -ltn "sport = :${host_port}" 2>/dev/null | tail -n +2 | grep -q . ; then
        owner="$(ss -ltnp "sport = :${host_port}" 2>/dev/null | tail -n +2 | grep -o 'users:(("[^"]*"' | head -1 | cut -d'"' -f2)"
        port_conflicts+=("${host_port}${owner:+ (held by ${owner})}")
      fi
    done
    if [ "${#port_conflicts[@]}" -ne 0 ] ; then
      log "BUILD" "❌" "☸️ Minikube publishes these host ports and they are already taken: ${port_conflicts[*]}"
      log "BUILD" "ℹ️ " "   Free them and start this arm again -- the cluster cannot be created without them, and a partial start leaves a node that has to be deleted by hand."
      exit 1
    fi

    minikube start \
              --driver docker \
              --cpus max \
              --memory "${memory_limit}m" \
              --wait all \
              --addons "registry,storage-provisioner,default-storageclass" \
              --listen-address "127.0.0.1" \
              --insecure-registry "10.0.0.0/24" \
              --embed-certs \
              --disable-metrics \
              --disable-optimizations \
              "${minikube_port_args[@]}"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
      log "BUILD" "❌" "☸️ Failed to start Minikube"
      exit 1
    fi
    log "BUILD" "ℹ️ " "☸️ Minikube started successfully ✅"
  fi

  # A cluster that was already up is NOT necessarily one this harness can use. `minikube start`
  # above is skipped entirely when `minikube status` succeeds, so a cluster someone started by hand
  # has none of the flags below it -- no `--addons registry`, and none of the `--ports` publishes
  # that put the registry, the ingress and every database on 127.0.0.1. The symptom is
  # "Registry is not healthy after 60 tries" a minute later, which points nowhere near the cause.
  # Enabling the addon here would only half-repair it (the port publishes cannot be added to a
  # running cluster at all), so this refuses instead of pretending.
  if ! docker port minikube 2>/dev/null | grep -q "5000/tcp -> 127.0.0.1:5000" ; then
    log "BUILD" "❌" "☸️ This Minikube cluster was not started by the harness: 127.0.0.1:5000 is not published, so no image can reach the in-cluster registry."
    log "BUILD" "ℹ️ " "   Run 'minikube delete' and start this arm again -- build.sh starts the cluster with the addons and port publishes the tests need."
    exit 1
  fi

  log "BUILD" "ℹ️ " "🗺️ Editing coredns configmap ..."
  kubectl get configmap coredns -n kube-system -o yaml > /tmp/coredns-configmap.yaml
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "🗺️ Failed to get coredns configmap"
    exit 1
  fi

  python3 tests/k8s/edit_coredns.py
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "🗺️ Failed to edit coredns configmap"
    exit 1
  fi

  kubectl replace -f /tmp/coredns-configmap.yaml
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "🗺️ Failed to replace coredns configmap"
    exit 1
  fi

  kubectl rollout restart deployment coredns -n kube-system
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    log "BUILD" "❌" "🗺️ Failed to restart coredns"
    exit 1
  fi
  log "BUILD" "ℹ️ " "🗺️ Coredns configmap edited successfully ✅"


  if [ "$type" == "core" ] ; then
    if grep -q "type: redis" tests/core/"$category".yml ; then
      mkdir -p /tmp/redis-acl /tmp/redis-tls /tmp/redis-scripts
      cp tests/misc/scripts/redis-entrypoint.sh tests/misc/scripts/redis-sentinel-entrypoint.sh /tmp/redis-scripts/
      chmod 0755 /tmp/redis-scripts/redis-entrypoint.sh /tmp/redis-scripts/redis-sentinel-entrypoint.sh
    fi

    if grep -q "valkey: true" tests/core/"$category".yml ; then
      mkdir -p /tmp/valkey-acl /tmp/valkey-tls /tmp/valkey-sentinel
      # Into redis-scripts on purpose: that directory is already created just above (a valkey spec
      # is a redis spec -- `valkey: true` is an attribute of a `type: redis` action) and is already
      # in the sync_minikube_fixtures list, so tests/misc/k8s/valkey.yml can mount it as /scripts
      # without a new fixture directory. The stock image ignores VALKEY_* env, so without this
      # entrypoint the ACL file is never loaded and every authenticated action fails on AUTH.
      cp tests/misc/scripts/valkey-entrypoint.sh /tmp/redis-scripts/
      chmod 0755 /tmp/redis-scripts/valkey-entrypoint.sh
    fi
  fi

  # The fixtures are copied INTO the node instead of 9p-mounted from the host -- see
  # sync_to_minikube in utils.sh for why (host firewalls, and 9p's ~600-file reliability ceiling).
  # start.sh syncs again before each apply: a before-script runs after this point and writes
  # certificates into /tmp/output that a build-time-only sync would never deliver.
  sync_minikube_fixtures || exit 1

  log "BUILD" "ℹ️ " "🧊 Waiting for registry to be healthy ..."
  i=0
  while [ $i -lt 60 ] ; do
    if curl -m 2 -s 127.0.0.1:5000/v2/_catalog | grep -q "repositories" ; then
      log "BUILD" "ℹ️ " "🧊 Registry is healthy ✅"
      break
    fi
    sleep 1
    i=$((i+1))
  done
  if [ $i -ge 60 ] ; then
    log "BUILD" "❌" "🧊 Registry is not healthy after 60 tries"
    exit 1
  fi

  log "BUILD" "ℹ️ " "🚢 Prepping custom local images ..."
  # API and worker are in every 1.7 cluster, whatever the test type.
  images=("bunkerity/bunkerweb" "bunkerity/bunkerweb-scheduler" "bunkerity/bunkerweb-autoconf" "bunkerity/bunkerweb-api" "bunkerity/bunkerweb-worker")
  if [ "$type" == "ui" ] ; then
    images+=("bunkerity/bunkerweb-ui")
  fi

  for image in "${images[@]}" ; do
    docker tag "$image":tests 127.0.0.1:5000/"$image":tests
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
      log "BUILD" "❌" "🏷 Failed to tag $image:tests"
      exit 1
    fi

    docker push 127.0.0.1:5000/"$image":tests
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
      log "BUILD" "❌" "🚀 Failed to push $image:tests"
      exit 1
    fi
  done
  log "BUILD" "ℹ️ " "🚢 Custom local images are ready ✅"

  if [ "$type" == "core" ] ; then
    if grep -q "svc-custom-api.misc.svc.cluster.local" tests/core/"$category".yml ; then
      log "BUILD" "ℹ️ " "🔧 Prepping custom-api ..."
      docker build -t 127.0.0.1:5000/custom-api:tests -f tests/misc/api/Dockerfile tests/misc/api
      # shellcheck disable=SC2181
      if [ $? -ne 0 ] ; then
        log "BUILD" "❌" "🏗 Failed to build custom-api"
        exit 1
      fi

      docker push 127.0.0.1:5000/custom-api:tests
      # shellcheck disable=SC2181
      if [ $? -ne 0 ] ; then
        log "BUILD" "❌" "🚀 Failed to push custom-api:tests"
        exit 1
      fi

      kubectl apply -f tests/misc/k8s/custom-api.yml
      # shellcheck disable=SC2181
      if [ $? -ne 0 ] ; then
        log "BUILD" "❌" "🔧 Apply failed for custom-api"
        exit 1
      fi

      kubectl wait --for=condition=available -n misc deployment/custom-api --timeout=60s
      # shellcheck disable=SC2181
      if [ $? -ne 0 ] ; then
        log "BUILD" "❌" "🔧 Failed to wait for custom-api deployment"
        exit 1
      fi
      log "BUILD" "ℹ️ " "🔧 Custom-api is ready ✅"
    fi
  fi
fi

log "BUILD" "ℹ️ " "🧑‍🔧 Build done ✅"
redis_cli set end 1 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  log "BUILD" "❌" "💽 Failed to set end flag in redis server"
  exit 1
fi

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
  if redis-cli ping | grep -q "PONG" ; then
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

redis-cli set end 0 > /dev/null
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
  if [ "$integration" == "Autoconf" ] || [ "$integration" == "Kubernetes" ] ; then
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
  redis-cli lpush tests "$category" > /dev/null
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
  sed_in_place '/^server=127.0.0.11/d' tests/misc/conf/dnsmasq.conf
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
  fi
fi

mkdir -p /tmp/output

if [ "$integration" != "Kubernetes" ] ; then
  if [ "$integration" != "Linux" ] ; then
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
    if grep -q "php-fpm" tests/core/"$category".yml ; then
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
    sudo echo "🔑 Sudo privileges granted ✅"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
      log "BUILD" "❌" "🔑 Sudo privileges not granted"
      exit 1
    fi

    mount_pids=$(pgrep -f "minikube mount")
    if [ -n "$mount_pids" ]; then
      for pid in $mount_pids ; do
      sudo kill -9 "$pid"
      done
    fi

    log "BUILD" "ℹ️ " "☸️ Starting Minikube ..."
    total_memory=$(free -m | awk '/^Mem:/{print $2}')
    memory_limit=$((total_memory * 80 / 100))
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
              --ports 127.0.0.1:80:80 \
              --ports 127.0.0.1:443:443 \
              --ports 127.0.0.1:5000:5000 \
              --ports 127.0.0.1:5001:5001 \
              --ports 127.0.0.1:5443:5443 \
              --ports 127.0.0.1:7000:30070 \
              --ports 127.0.0.1:8000:30080 \
              --ports 127.0.0.1:8888:30088 \
              --ports 127.0.0.1:3306:30306 \
              --ports 127.0.0.1:5432:30432 \
              --ports 127.0.0.1:6380:30379 \
              --ports 127.0.0.1:6381:30380 \
              --ports 127.0.0.1:6382:30381 \
              --ports 127.0.0.1:6479:30479 \
              --ports 127.0.0.1:26379:32379 \
              --ports 127.0.0.1:26380:32380 \
              --ports 127.0.0.1:26381:32381 \
              --ports 127.0.0.1:26479:32479 \
              --ports 127.0.0.1:26480:32480 \
              --ports 127.0.0.1:26481:32481
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
      log "BUILD" "❌" "☸️ Failed to start Minikube"
      exit 1
    fi
    log "BUILD" "ℹ️ " "☸️ Minikube started successfully ✅"

    minikube_mount_logs=$(ls /tmp/minikube_mount_*.log)
    if [ -n "$minikube_mount_logs" ] ; then
      for log_file in $minikube_mount_logs ; do
        rm -f "$log_file"
      done
    fi
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

  function mount_and_log() {
    local host_dir="${1:-}"
    local minikube_dir="${2:-}"
    local log_file="/tmp/minikube_mount_${minikube_dir//\//_}.log"

    # Kill any stale minikube mount for the same target left over from a previous run.
    # A leaked mount holds the 9p bind and prevents a fresh mount from ever reaching "Successfully mounted".
    pkill -f "minikube mount ${host_dir}:${minikube_dir}" 2>/dev/null || true
    rm -f "$log_file"

    log "BUILD" "ℹ️ " "📂 Mounting $host_dir to Minikube ..."
    minikube mount "$host_dir:$minikube_dir" --log_file="$log_file" &
    local mount_pid="$!"
    local ret="$?"

    if [ "$ret" -ne 0 ]; then
      log "BUILD" "❌" "📂 Failed to launch minikube mount for $host_dir"
      exit 1
    fi

    # Poll up to ~30s for "Successfully mounted", and fail fast if the background mount dies.
    local waited=0
    local max_wait=30
    while [ "$waited" -lt "$max_wait" ]; do
      if grep -q "Successfully mounted" "$log_file" 2>/dev/null ; then
        break
      fi
      if ! kill -0 "$mount_pid" 2>/dev/null ; then
        log "BUILD" "❌" "📂 minikube mount for $host_dir exited before completing"
        exit 1
      fi
      sleep 1
      waited=$((waited + 1))
    done

    if ! grep -q "Successfully mounted" "$log_file" 2>/dev/null ; then
      log "BUILD" "❌" "📂 Failed to mount $host_dir to Minikube (timeout after ${max_wait}s)"
      kill "$mount_pid" 2>/dev/null || true
      exit 1
    fi

    redis-cli lpush minikube_cmd_pids "$mount_pid"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ]; then
      log "BUILD" "❌" "💽 Failed to push mount pid to redis server"
      exit 1
    fi

    log "BUILD" "ℹ️ " "📂 $host_dir mounted to Minikube successfully ✅"
  }

  mount_and_log "/var/www/html" "/mnt/www"
  mount_and_log "/tmp/output" "/mnt/output"

  if [ "$type" == "core" ] ; then
    if grep -q "type: redis" tests/core/"$category".yml ; then
      mkdir -p /tmp/redis-acl /tmp/redis-tls /tmp/redis-scripts
      cp tests/misc/scripts/redis-entrypoint.sh tests/misc/scripts/redis-sentinel-entrypoint.sh /tmp/redis-scripts/
      chmod 0755 /tmp/redis-scripts/redis-entrypoint.sh /tmp/redis-scripts/redis-sentinel-entrypoint.sh
      mount_and_log "/tmp/redis-acl" "/mnt/redis-acl"
      mount_and_log "/tmp/redis-tls" "/mnt/redis-tls"
      mount_and_log "/tmp/redis-scripts" "/mnt/redis-scripts"
    fi

    if grep -q "valkey: true" tests/core/"$category".yml ; then
      mkdir -p /tmp/valkey-acl /tmp/valkey-tls /tmp/valkey-sentinel
      mount_and_log "/tmp/valkey-acl" "/mnt/valkey-acl"
      mount_and_log "/tmp/valkey-tls" "/mnt/valkey-tls"
      mount_and_log "/tmp/valkey-sentinel" "/mnt/valkey-sentinel"
    fi
  fi

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
redis-cli set end 1 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  log "BUILD" "❌" "💽 Failed to set end flag in redis server"
  exit 1
fi

.PHONY: test tests test-dynamic-debian12 build clean shell base-image lint tests-asan

BASE_IMAGE ?= ngx-zstd-tests-base
NGINX_VERSION ?= release-1.30.4
DOCKER ?= docker
# Use PULL=--pull when an explicit base-image refresh is wanted.
PULL ?=

MODULE_SRCS = filter/ngx_http_zstd_filter_module.c \
	filter/ngx_http_zstd_filter.c \
	static/ngx_http_zstd_static_module.c

base-image:
	$(DOCKER) build $(PULL) \
		--build-arg NGINX_VERSION=$(NGINX_VERSION) \
		-f Dockerfile.tests-base \
		-t $(BASE_IMAGE):$(NGINX_VERSION) .

build: base-image

tests: build
	@if [ "$(HUP)" != "0" ]; then echo "Fast mode: HUP enabled (use HUP=0 to disable)"; fi
	$(DOCKER) compose -f docker-compose.test.yml run --rm \
		$(if $(filter 0,$(HUP)),-e TEST_NGINX_USE_HUP=0,) \
		tests $(T)

test: tests

test-dynamic-debian12:
	$(DOCKER) build --pull \
		--build-arg NGINX_VERSION=$(NGINX_VERSION) \
		-f Dockerfile.dynamic-debian12 \
		-t ngx-zstd-dynamic-debian12:$(NGINX_VERSION) .

shell: build
	$(DOCKER) compose -f docker-compose.test.yml run --rm tests /bin/bash

# Static analysis with cppcheck. Runs inside the base image so cppcheck can
# resolve nginx headers (under /opt/nginx-src) and report on our code only.
lint: build
	$(DOCKER) run --rm \
		-v $(PWD):/work \
		-w /work \
		$(BASE_IMAGE):$(NGINX_VERSION) \
		cppcheck --enable=warning,portability,performance \
		  --check-level=exhaustive \
		  --error-exitcode=1 \
		  --suppressions-list=.cppcheck-suppressions \
		  --suppress=missingIncludeSystem \
		  --std=c11 \
		  -DZSTD_STATIC_LINKING_ONLY \
		  -I /opt/nginx-src/src/core -I /opt/nginx-src/src/event \
		  -I /opt/nginx-src/src/http -I /opt/nginx-src/src/http/modules \
		  -I /opt/nginx-src/src/os/unix -I /opt/nginx-src/objs \
		  $(MODULE_SRCS)

# Run the test suite under AddressSanitizer. Rebuilds nginx from source with
# the module compiled in statically and -fsanitize=address. HUP mode is left
# off for clean per-test process attribution.
tests-asan: build
	$(DOCKER) run --rm \
		-e ASAN=1 \
		-e TEST_NGINX_FAST_SHUTDOWN=1 \
		-e TEST_NGINX_NO_CLEAN=1 \
		-e TEST_NGINX_LOG_LEVEL=debug \
		-e TEST_NGINX_ERROR_LOG=/work/test-error-asan.log \
		-v $(PWD):/work \
		-w /work \
		$(BASE_IMAGE):$(NGINX_VERSION) /work/docker-run-tests.sh $(T)

clean:
	-$(DOCKER) image rm $(BASE_IMAGE):$(NGINX_VERSION)

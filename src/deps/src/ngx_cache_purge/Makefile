# Makefile for ngx_cache_purge testing and development
.PHONY: test test-all test-memory test-performance test-load test-coverage clean dev-test dev-watch test-compat help

# Default nginx version for testing
NGINX_VERSION ?= 1.24.0

# Colors for output
GREEN=\033[0;32m
YELLOW=\033[1;33m
RED=\033[0;31m
NC=\033[0m # No Color

# Default target
help:
	@echo "$(GREEN)ngx_cache_purge Development Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Testing Commands:$(NC)"
	@echo "  test                 - Run basic functionality tests"
	@echo "  test-all            - Run comprehensive test suite (all services)"
	@echo "  test-memory         - Run memory leak analysis with Valgrind"
	@echo "  test-performance    - Run performance benchmarks"
	@echo "  test-load           - Run load testing with Artillery"
	@echo "  test-coverage       - Generate code coverage report"
	@echo "  test-compat         - Test compatibility across nginx versions"
	@echo ""
	@echo "$(YELLOW)Development Commands:$(NC)"
	@echo "  dev-test            - Quick test for development (basic tests only)"
	@echo "  dev-watch           - Watch mode for development (requires inotify-tools)"
	@echo "  clean               - Clean up test artifacts and containers"
	@echo ""
	@echo "$(YELLOW)Environment Variables:$(NC)"
	@echo "  NGINX_VERSION       - nginx version to test (default: $(NGINX_VERSION))"
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make test                          # Quick basic tests"
	@echo "  make test-all                      # Full test suite"
	@echo "  NGINX_VERSION=1.22.1 make test    # Test specific nginx version"

# Run basic functionality tests
test:
	@echo "$(GREEN)Running basic ngx_cache_purge tests...$(NC)"
	docker-compose -f docker-compose.test.yml run --rm nginx-test prove -v t/basic.t t/config.t
	@echo "$(GREEN)Basic tests completed!$(NC)"

# Run comprehensive test suite
test-all:
	@echo "$(GREEN)Running comprehensive test suite...$(NC)"
	@echo "This will test: basic functionality, background queue, memory, performance, and compatibility"
	docker-compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from nginx-test
	@echo "$(GREEN)All tests completed!$(NC)"

# Memory leak testing with Valgrind
test-memory:
	@echo "$(GREEN)Running memory leak analysis...$(NC)"
	@mkdir -p valgrind-results
	docker-compose -f docker-compose.test.yml run --rm valgrind-test
	@echo "$(GREEN)Memory test results available in valgrind-results/$(NC)"
	@if [ -f valgrind-results/memcheck.log ]; then \
		echo "$(YELLOW)Memory leak summary:$(NC)"; \
		grep -E "(ERROR SUMMARY|definitely lost|indirectly lost|possibly lost)" valgrind-results/memcheck.log || true; \
	fi

# Performance testing
test-performance:
	@echo "$(GREEN)Running performance benchmarks...$(NC)"
	@mkdir -p performance-results
	docker-compose -f docker-compose.test.yml run --rm performance-test
	@echo "$(GREEN)Performance results available in performance-results/$(NC)"

# Load testing with Artillery
test-load:
	@echo "$(GREEN)Running load tests...$(NC)"
	@mkdir -p load-results
	docker-compose -f docker-compose.test.yml run --rm load-test
	@echo "$(GREEN)Load test results available in load-results/$(NC)"

# Code coverage analysis
test-coverage:
	@echo "$(GREEN)Generating code coverage report...$(NC)"
	@mkdir -p coverage-results
	docker-compose -f docker-compose.test.yml run --rm coverage-test
	@echo "$(GREEN)Coverage report available at coverage-results/html/index.html$(NC)"

# Multi-version compatibility testing
test-compat:
	@echo "$(GREEN)Testing compatibility across nginx versions...$(NC)"
	@echo "Testing nginx 1.20.2..."
	@NGINX_VERSION=1.20.2 docker-compose -f docker-compose.test.yml run --rm nginx-test prove -v t/basic.t t/config.t
	@echo "Testing nginx 1.22.1..."
	@NGINX_VERSION=1.22.1 docker-compose -f docker-compose.test.yml run --rm nginx-test prove -v t/basic.t t/config.t
	@echo "Testing nginx 1.24.0..."
	@NGINX_VERSION=1.24.0 docker-compose -f docker-compose.test.yml run --rm nginx-test prove -v t/basic.t t/config.t
	@echo "$(GREEN)Compatibility tests completed!$(NC)"

# Quick development test (single test file)
dev-test:
	@echo "$(GREEN)Running quick development test...$(NC)"
	docker-compose -f docker-compose.test.yml run --rm -v $(PWD):/src nginx-test prove -v t/basic.t

# Watch mode for development (requires inotify-tools on host)
dev-watch:
	@echo "$(GREEN)Starting watch mode... (Press Ctrl+C to stop)$(NC)"
	@echo "Watching: *.c *.h t/*.t files"
	@while true; do \
		make dev-test; \
		echo "$(YELLOW)Waiting for changes...$(NC)"; \
		inotifywait -qq -e modify,create,delete *.c *.h t/*.t 2>/dev/null || true; \
		sleep 1; \
	done

# Test legacy compatibility (run original tests)
test-legacy:
	@echo "$(GREEN)Running legacy test compatibility...$(NC)"
	@if [ -d t/legacy ]; then \
		docker-compose -f docker-compose.test.yml run --rm nginx-test prove -v t/legacy/; \
	else \
		echo "$(RED)No legacy tests found in t/legacy/$(NC)"; \
		exit 1; \
	fi

# Build test environment without running tests
build:
	@echo "$(GREEN)Building test environment...$(NC)"
	docker-compose -f docker-compose.test.yml build nginx-test
	@echo "$(GREEN)Build completed!$(NC)"

# Interactive test environment (for debugging)
shell:
	@echo "$(GREEN)Starting interactive test shell...$(NC)"
	docker-compose -f docker-compose.test.yml run --rm nginx-test bash

# Check if docker and docker-compose are available
check-deps:
	@echo "$(GREEN)Checking dependencies...$(NC)"
	@command -v docker >/dev/null 2>&1 || { echo "$(RED)Error: Docker not found$(NC)"; exit 1; }
	@command -v docker-compose >/dev/null 2>&1 || { echo "$(RED)Error: docker-compose not found$(NC)"; exit 1; }
	@echo "$(GREEN)Dependencies OK$(NC)"

# Clean up all test artifacts
clean:
	@echo "$(GREEN)Cleaning up test artifacts...$(NC)"
	docker-compose -f docker-compose.test.yml down -v --remove-orphans || true
	docker system prune -f || true
	rm -rf test-results valgrind-results performance-results load-results coverage-results
	rm -rf cache cache2 perfcache bgcache concurrent throttle
	rm -rf t/servroot tmp
	@echo "$(GREEN)Cleanup completed!$(NC)"

# Force rebuild (clean build)
rebuild: clean build
	@echo "$(GREEN)Force rebuild completed!$(NC)"

# Show test results summary
results:
	@echo "$(GREEN)Test Results Summary:$(NC)"
	@echo ""
	@if [ -d test-results ]; then \
		echo "$(YELLOW)Test Results:$(NC)"; \
		find test-results -name "*.xml" -exec basename {} \; 2>/dev/null || echo "No test results found"; \
	fi
	@if [ -d valgrind-results ]; then \
		echo "$(YELLOW)Memory Analysis:$(NC)"; \
		ls -la valgrind-results/ 2>/dev/null || echo "No memory analysis results found"; \
	fi
	@if [ -d performance-results ]; then \
		echo "$(YELLOW)Performance Results:$(NC)"; \
		ls -la performance-results/ 2>/dev/null || echo "No performance results found"; \
	fi
	@if [ -d coverage-results ]; then \
		echo "$(YELLOW)Coverage Report:$(NC)"; \
		echo "Open coverage-results/html/index.html in browser"; \
	fi

# Install dependencies for watch mode
install-watch-deps:
	@echo "$(GREEN)Installing watch mode dependencies...$(NC)"
	@if command -v apt-get >/dev/null 2>&1; then \
		sudo apt-get update && sudo apt-get install -y inotify-tools; \
	elif command -v yum >/dev/null 2>&1; then \
		sudo yum install -y inotify-tools; \
	elif command -v brew >/dev/null 2>&1; then \
		brew install fswatch; \
		echo "$(YELLOW)Note: Use 'fswatch' instead of 'inotifywait' on macOS$(NC)"; \
	else \
		echo "$(RED)Cannot install inotify-tools automatically. Please install manually.$(NC)"; \
	fi

# Run tests with specific nginx version
test-nginx-version:
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: Please specify VERSION=x.y.z$(NC)"; \
		echo "Example: make test-nginx-version VERSION=1.22.1"; \
		exit 1; \
	fi
	@echo "$(GREEN)Testing with nginx $(VERSION)...$(NC)"
	@NGINX_VERSION=$(VERSION) docker-compose -f docker-compose.test.yml run --rm nginx-test prove -v t/basic.t

# Quick syntax check (lint)
lint:
	@echo "$(GREEN)Running syntax checks...$(NC)"
	@if command -v cppcheck >/dev/null 2>&1; then \
		cppcheck --enable=all --inconclusive --std=c99 \
			--suppress=missingIncludeSystem \
			--error-exitcode=1 \
			ngx_cache_purge_module.c; \
	else \
		echo "$(YELLOW)cppcheck not found, skipping static analysis$(NC)"; \
	fi
	@echo "$(GREEN)Syntax check completed!$(NC)"

# Show system info for debugging
info:
	@echo "$(GREEN)System Information:$(NC)"
	@echo "Docker version: $$(docker --version 2>/dev/null || echo 'Not installed')"
	@echo "Docker Compose version: $$(docker-compose --version 2>/dev/null || echo 'Not installed')"
	@echo "Current directory: $(PWD)"
	@echo "Available files: $$(ls -la *.c *.md config 2>/dev/null || echo 'Module files not found')"
	@echo "Test files: $$(find t/ -name '*.t' 2>/dev/null | wc -l) files"
	@echo "Default nginx version: $(NGINX_VERSION)"
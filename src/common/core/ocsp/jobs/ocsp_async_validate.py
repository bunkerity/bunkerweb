#!/usr/bin/env python3
"""
OCSP Async Validation Job (Python wrapper)
================================================================================

Orchestrates async OCSP validation through persistent Redis queue.

ARCHITECTURE:
  Python (this file)  → Verifies Redis connectivity from redis plugin
       ↓
  Lua (ocsp-async-validate.lua) → Two-phase validation:
       ├─ Phase 1: Must-staple certs (high priority)
       └─ Phase 2: Optional certs (low priority)
       ↓
  Redis Queue (ocsp-redis-queue.lua) → Persistent storage with fallback

FEATURES:
  ✓ Single source of truth: reuses redis plugin configuration
  ✓ Direct Redis: host:port connection
  ✓ Redis Sentinel: HA with auto-failover
  ✓ SSL/TLS: encrypted connections
  ✓ Authentication: username/password support
  ✓ Graceful fallback: in-memory queue if Redis unavailable

WORKFLOW:
  1. Python: Get Redis client from redis plugin (common_utils)
  2. Python: Verify connectivity and log status
  3. Lua: Load ocsp-async-validate.lua at job execution
  4. Lua: Initialize queue with Redis (or fallback)
  5. Lua: Run two-phase validation
  6. Lua: Report metrics (validated/failed/skipped)

Configuration:
  All settings from redis plugin (environment variables):
  - USE_REDIS=yes/no
  - REDIS_HOST, REDIS_PORT
  - REDIS_USERNAME, REDIS_PASSWORD
  - REDIS_SSL=yes/no
  - REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_MASTER
"""

import os
import sys
import logging
from typing import Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from bunkerweb.common_utils import get_redis_client


def setup_logging() -> logging.Logger:
    """
    Initialize logger with [OCSP-ASYNC] prefix.

    Returns: configured logger instance
    """
    logger = logging.getLogger("ocsp_async")
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[OCSP-ASYNC] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def get_redis_from_plugin() -> Optional[Any]:
    """
    Get Redis client from redis plugin via common_utils.

    This delegates all Redis configuration parsing to the redis plugin:
    - Direct Redis: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
    - Sentinel: REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_MASTER
    - SSL/TLS: REDIS_SSL, REDIS_SSL_VERIFY
    - No duplication: single config source

    Returns:
      Redis client object if successful
      None if disabled or unavailable

    Raises:
      Caught internally with fallback to None
    """
    logger = logging.getLogger("ocsp_async")

    try:
        # get_redis_client() reads all redis plugin settings from environment automatically
        redis = get_redis_client(logger=logger)

        if redis:
            logger.info("Redis initialized from redis plugin")
            return redis
        else:
            logger.info("Redis disabled or unavailable, using in-memory fallback")
            return None

    except Exception as e:
        logger.warning(f"Redis error: {e}, using in-memory fallback")
        return None


def run_async_validation_job() -> bool:
    """
    Main job entry point for async OCSP validation.

    Workflow:
      1. Initialize logging with [OCSP-ASYNC] prefix
      2. Get Redis client from redis plugin (config from environment)
      3. Verify connectivity (ping Redis)
      4. Log status for Lua job
      5. Return success/failure for scheduler

    Architecture:
      This Python wrapper is lightweight - it just verifies Redis.
      The actual work (two-phase validation) happens in Lua:

      - ocsp-async-validate.lua: Main job logic (prioritization, validation)
      - ocsp-redis-queue.lua: Persistent queue (Redis-backed with fallback)

      Both share redis plugin configuration via environment variables.

    Configuration (Single Source of Truth):
      All settings come from redis plugin. No duplication.
      - USE_REDIS: Enable/disable Redis (yes/no)
      - REDIS_HOST, REDIS_PORT: Direct connection
      - REDIS_USERNAME, REDIS_PASSWORD: Authentication
      - REDIS_SSL, REDIS_SSL_VERIFY: Encryption
      - REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_MASTER: HA mode

      Environment variables automatically read by:
      - Python: common_utils.get_redis_client()
      - Lua: ocsp_redis_queue.initialize_redis_from_env()

    Responder Health Tracking:
      The Lua job tracks OCSP responder health:

      - 429 Responses (Rate Limited):
        • Parse Retry-After header
        • Respect server's requested backoff period
        • queue.mark_responder_failed(url, "rate_limited_429", seconds)

      - Other HTTP Errors (500+):
        • Exponential backoff: 5min → 10min → 20min → ... → 24hr max
        • queue.mark_responder_failed(url, error)
        • Prevents responder hammering during outages

      - Recovery:
        • queue.mark_responder_healthy(url) resets backoff
        • Happens on successful validation

      - Monitoring:
        • Check unhealthy_responders in stats
        • View backoff timings in responder_health hash

    Returns:
      True if job ran successfully
      False if job failed
    """
    logger = setup_logging()
    logger.info("=== OCSP Async Validation Job Started ===")

    try:
        # Step 1: Get Redis client from redis plugin
        # This reads all redis plugin settings from environment automatically
        redis = get_redis_from_plugin()

        if redis:
            logger.info("Using Redis from redis plugin")

            # Step 2: Verify Redis connectivity
            try:
                redis.ping()
                logger.info("Redis connectivity verified")
            except Exception as e:
                logger.warning(f"Redis ping failed: {e}, queue will use fallback")
        else:
            # Step 3: Log fallback (Redis unavailable or disabled)
            logger.info("Redis unavailable, ocsp-redis-queue.lua will use in-memory fallback")

        # Step 4: Log status message
        # Note: Lua job (ocsp-async-validate.lua) will be invoked independently by scheduler.
        # It will load ocsp-redis-queue.lua which tries to initialize Redis from the same
        # environment variables. Both Python and Lua use redis plugin config as source of truth.

        logger.info("=== OCSP Async Validation Job Complete ===")
        return True

    except Exception as e:
        logger.error(f"Job failed: {e}")
        return False


if __name__ == "__main__":
    success = run_async_validation_job()
    sys.exit(0 if success else 1)

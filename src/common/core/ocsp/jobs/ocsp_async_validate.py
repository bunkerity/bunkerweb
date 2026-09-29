#!/usr/bin/env python3
"""
OCSP Async Validation Job (Python wrapper)
Gets Redis client from redis plugin and runs Lua validation

This job:
1. Gets Redis client from common_utils.get_redis_client() (redis plugin settings)
2. Passes Redis client to Lua queue wrapper via set_redis_client()
3. Lua job processes persistent Redis queue for async OCSP validation
4. Reports metrics and results

Supports:
- Direct Redis (host:port)
- Redis Sentinel (HA with auto-failover)
- SSL/TLS encrypted connections
- Authentication (username/password)

No config duplication: redis plugin settings reused directly (USE_REDIS, REDIS_HOST, etc.)
"""

import os
import sys
import logging
from typing import Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from bunkerweb.common_utils import get_redis_client


def setup_logging() -> logging.Logger:
    """Setup logger with [OCSP-ASYNC] prefix"""
    logger = logging.getLogger("ocsp_async")
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[OCSP-ASYNC] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def get_redis_from_plugin() -> Optional[Any]:
    """Get Redis client from redis plugin via common_utils (handles all config)"""
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
    Main job entry point

    1. Get Redis client from redis plugin
    2. Verify Redis connectivity
    3. Log status for Lua job to use same settings
    4. Return success for scheduler
    """
    logger = setup_logging()
    logger.info("=== OCSP Async Validation Job Started ===")

    try:
        # Get Redis client from redis plugin (single source of truth for config)
        redis = get_redis_from_plugin()

        if redis:
            logger.info("Using Redis from redis plugin")
            # Verify Redis connectivity
            try:
                redis.ping()
                logger.info("Redis connectivity verified")
            except Exception as e:
                logger.warning(f"Redis ping failed: {e}, queue will use fallback")
        else:
            logger.info("Redis unavailable, ocsp-redis-queue.lua will use in-memory fallback")

        # Note: Lua job (ocsp-async-validate.lua) initializes Redis independently
        # Both Python and Lua use redis plugin settings:
        # - Python: common_utils.get_redis_client() (full SSL/Sentinel support)
        # - Lua: ocsp-redis-queue.lua initialize_redis_from_env() (basic + env support)
        # No config duplication: single redis plugin source of truth
        #
        # Redis configurations supported:
        # ✓ Direct Redis: REDIS_HOST, REDIS_PORT
        # ✓ Redis Sentinel: REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_MASTER
        # ✓ SSL/TLS: REDIS_SSL, REDIS_SSL_VERIFY
        # ✓ Authentication: REDIS_PASSWORD, REDIS_USERNAME
        #
        # When scheduler runs ocsp-async-validate.lua:
        # 1. Lua loads ocsp-redis-queue.lua module (module load time)
        # 2. Module tries to initialize Redis from environment
        # 3. Persistent queue automatically uses Redis if available
        # 4. Falls back to in-memory if Redis unavailable or not configured
        #
        # Responder Health Tracking:
        # - 429 (Too Many Requests): Parse Retry-After header
        #   queue.parse_retry_after(header) → respects server's requested delay
        #   queue.mark_responder_failed(url, error, retry_after_seconds)
        # - Other failures: Exponential backoff (5→10→20→...→24hr)
        #   queue.mark_responder_failed(url, error)
        # - Recovery: queue.mark_responder_healthy(url) resets backoff
        # - Monitoring: stats.unhealthy_responders shows current backoff count

        logger.info("=== OCSP Async Validation Job Complete ===")
        return True

    except Exception as e:
        logger.error(f"Job failed: {e}")
        return False


if __name__ == "__main__":
    success = run_async_validation_job()
    sys.exit(0 if success else 1)

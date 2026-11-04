from pydantic import field_validator, model_validator
from typing import Literal, Optional

from .action import ActionBase, ActionData


class LimitData(ActionData):
    """Extra fields used by limit tests."""

    rate_limit: Optional[str] = None
    max_requests: Optional[int] = None
    max_connections: Optional[int] = None
    connection_exceed_count: Optional[int] = None
    expect_limited: bool = False
    expect_blocked: bool = False
    test_recovery: bool = False
    recovery_delay: float = 0.0
    rate_exceeded_count: Optional[int] = None
    connection_hold: float = 0.0  # seconds to keep each test connection open (streaming) for connection limiting tests

    @field_validator("rate_limit")
    @classmethod
    def validate_rate_limit(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            # Validate format like "2r/s", "10r/m", etc.
            import re

            if not re.match(r"^\d+r/[smhd]$", v):
                raise ValueError("rate_limit must be in format 'Nr/t' where N is number and t is s|m|h|d")
        return v

    @field_validator("max_requests")
    @classmethod
    def validate_max_requests(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("max_requests must be greater than 0")
        return v

    @field_validator("max_connections")
    @classmethod
    def validate_max_connections(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("max_connections must be greater than 0")
        return v

    @field_validator("recovery_delay")
    @classmethod
    def validate_recovery_delay(cls, v: float) -> float:
        if v < 0:
            raise ValueError("recovery_delay must be non-negative")
        return v

    @field_validator("connection_hold")
    @classmethod
    def validate_connection_hold(cls, v: float) -> float:
        if v < 0:
            raise ValueError("connection_hold must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_limit_fields(self):
        # If testing recovery, ensure recovery_delay is set
        if self.test_recovery and self.recovery_delay <= 0:
            raise ValueError("recovery_delay must be positive when test_recovery is True")

        # If expect_limited is True, should have rate limit info
        if self.expect_limited and not self.rate_limit and not self.max_requests:
            raise ValueError("rate_limit or max_requests must be set when expect_limited is True")

        return self


class LimitBase(ActionBase, LimitData):
    type: Literal["limit"] = "limit"


class Limit(LimitBase):
    Docker: Optional[LimitData] = None
    Linux: Optional[LimitData] = None
    Autoconf: Optional[LimitData] = None
    Kubernetes: Optional[LimitData] = None
    All_in_one: Optional[LimitData] = None


__all__ = ("Limit",)

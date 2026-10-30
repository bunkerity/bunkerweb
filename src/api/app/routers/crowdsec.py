"""CrowdSec investigation and explicit, connection-scoped decision removal."""

from ipaddress import ip_address, ip_network

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from CrowdSec import CrowdSecClient, CrowdSecError  # type: ignore

from ..auth.guard import guard
from ..utils import LOGGER, get_db

router = APIRouter(prefix="/crowdsec", tags=["crowdsec"], dependencies=[Depends(guard)])


class DecisionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str = Field(pattern=r"^(Ip|Range|ip|range)$")
    value: str = Field(min_length=1, max_length=128)
    decision_type: str = Field(min_length=1, max_length=64)

    @field_validator("value")
    @classmethod
    def valid_target(cls, value: str) -> str:
        ip_network(value, strict=False) if "/" in value else ip_address(value)
        return value

    @model_validator(mode="after")
    def scope_matches_target(self):
        if (self.scope.lower() == "range") != ("/" in self.value):
            raise ValueError("The decision scope must match the selected IP or range")
        return self


def call(operation):
    try:
        return operation(CrowdSecClient(get_db(log=False)))
    except CrowdSecError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None


@router.get("")
def connections():
    """List configured connections, preserving per-instance errors and identity."""
    return call(lambda client: client.connections())


@router.get("/{connection_id}/decisions")
def decisions(
    connection_id: str,
    ip: str = "",
    origin: str = Query("", max_length=512),
    scenario: str = Query("", max_length=512),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    if ip:
        try:
            ip = str(ip_address(ip))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid IP address") from None
    return call(lambda client: client.query(connection_id, "decisions", {"ip": ip, "origin": origin, "scenario": scenario, "offset": offset, "limit": limit}))


@router.get("/{connection_id}/alerts/{alert_id}")
def alert(connection_id: str, alert_id: int):
    if alert_id <= 0 or alert_id > 9007199254740991:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
    return call(lambda client: client.query(connection_id, "alerts", {"alert_id": alert_id}))


@router.get("/{connection_id}/allowlists")
def allowlists(connection_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return call(lambda client: client.query(connection_id, "allowlists", {"offset": offset, "limit": limit}))


@router.get("/{connection_id}/allowlists/check")
def allowlist_check(connection_id: str, ip: str):
    try:
        ip = str(ip_address(ip))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IP address") from None
    return call(lambda client: client.query(connection_id, "allowlistcheck", {"ip": ip}))


@router.get("/{connection_id}/ips/{ip}")
def investigate(connection_id: str, ip: str):
    return call(lambda client: client.investigate(connection_id, ip))


@router.delete("/{connection_id}/decisions/{decision_id}")
def remove(connection_id: str, decision_id: int, selection: DecisionSelection, request: Request):
    """Remove the selected upstream decision; confirm scope/value/type in the body.

    Removal affects every bouncer using that CrowdSec engine. Successful deletion
    does not prove cache propagation or bypass another decision or AppSec rule.
    """
    if decision_id <= 0 or decision_id > 9007199254740991:
        raise HTTPException(status_code=400, detail="Invalid decision ID")
    actor = getattr(request.state, "auth_subject", "biscuit")
    try:
        result = call(lambda client: client.query(connection_id, "unban", {**selection.model_dump(), "decision_id": decision_id}))
    except HTTPException as exc:
        LOGGER.warning(
            "CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=error status=%s",
            actor,
            connection_id,
            decision_id,
            selection.value,
            exc.status_code,
        )
        raise
    LOGGER.info(
        "CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=removed propagation=pending", actor, connection_id, decision_id, selection.value
    )
    return result

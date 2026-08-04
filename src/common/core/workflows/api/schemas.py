#!/usr/bin/env python3
"""Request models for the /workflows router.

They live in the plugin rather than in ``app/schemas.py`` because the plugin owns its own
contract — the core API has no reason to know the shape of a rule tree. Only the envelope
is typed here; the definition itself is validated by ``workflow_schema``, which the DB
layer and the compiler share, so there is exactly one place that decides what a rule is.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256, description="Unique workflow name")
    description: str = Field("", max_length=4096)
    definition: Optional[Dict[str, Any]] = Field(None, description="Optional initial definition; an empty workflow is created when omitted")
    service_ids: List[str] = Field(default_factory=list, description="Services to attach the workflow to on creation")


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=4096)


class WorkflowCloneRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256, description="Name of the copy")


class WorkflowDefinitionRequest(BaseModel):
    definition: Dict[str, Any] = Field(..., description="Canonical workflow definition: schema_version + ordered rules")


class WorkflowValidateRequest(BaseModel):
    definition: Dict[str, Any]
    workflow_id: str = Field("", description="Existing workflow the draft would replace, so its own rules are not double-counted")
    service_ids: Optional[List[str]] = Field(None, description="Services to project the aggregate budgets onto (defaults to current attachments)")


class WorkflowAttachmentRequest(BaseModel):
    service_id: str = Field(..., min_length=1, max_length=256)


class WorkflowTestRequestFacts(BaseModel):
    """The synthetic request, in the operator's terms rather than the runtime's.

    GeoIP is asked, never derived from the address: the runtime's own private-range table is
    hand-written Lua that already disagrees with Python's, so deriving it here would invent a
    divergence the parity corpus structurally cannot catch.
    """

    remote_addr: str = Field("", max_length=64)
    uri: str = Field("/", min_length=1, max_length=2048)
    request_method: str = Field("GET", max_length=16)
    geo: str = Field("resolved", description="resolved | local | unavailable")
    country: str = Field("", max_length=8)
    asn: Optional[int] = Field(None, ge=0)
    # The runtime's own counter: what ratelimit.incr returns, INCLUDING this request. Named
    # so the inclusive/exclusive question never has to be asked.
    request_number: int = Field(1, ge=1, le=100000)
    whitelisted: bool = False


class WorkflowTestRequest(BaseModel):
    definition: Optional[Dict[str, Any]] = Field(None, description="Unsaved draft to substitute for this workflow; the stored one is used when omitted")
    service_id: str = Field("", max_length=256, description="Service whose ladder to evaluate; the first attachment when omitted")
    request: WorkflowTestRequestFacts = Field(default_factory=WorkflowTestRequestFacts)

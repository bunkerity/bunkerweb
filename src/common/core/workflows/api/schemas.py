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

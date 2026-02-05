from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


AllowedModel = Literal["kimi-k2p5", "kimi-k2-instruct-0905"]
ContextMode = Literal["full", "code_only"]
CriteriaType = Literal["contains", "regex", "json_valid"]


class StepBase(BaseModel):
    step_order: int = Field(..., ge=1)
    model: AllowedModel
    prompt: str = Field(..., min_length=1)

    criteria_type: Optional[CriteriaType] = None
    criteria_value: Optional[str] = None

    max_retries: int = Field(default=2, ge=0, le=10)
    context_mode: ContextMode = "full"


class StepCreate(StepBase):
    pass


class StepRead(StepBase):
    id: int
    workflow_id: int

    class Config:
        from_attributes = True


class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class WorkflowCreate(WorkflowBase):
    steps: List[StepCreate] = Field(default_factory=list)


class WorkflowUpdate(WorkflowBase):
    steps: List[StepCreate] = Field(default_factory=list)


class WorkflowRead(WorkflowBase):
    id: int
    created_at: datetime
    steps: List[StepRead] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkflowListItem(BaseModel):
    id: int
    name: str
    created_at: datetime
    step_count: int

    class Config:
        from_attributes = True
class RunCreateResponse(BaseModel):
    run_id: int


class RunStepLog(BaseModel):
    id: int
    run_id: int
    step_id: Optional[int] = None
    step_order: int

    status: str
    attempt_no: int

    prompt_used: str
    output: Optional[str] = None
    criteria_result: Optional[str] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


class RunRead(BaseModel):
    id: int
    workflow_id: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    steps: List[RunStepLog] = []

    class Config:
        from_attributes = True


class RunListItem(BaseModel):
    id: int
    workflow_id: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True
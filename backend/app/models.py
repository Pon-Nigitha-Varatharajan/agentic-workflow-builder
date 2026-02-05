from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    steps = relationship(
        "Step",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="Step.step_order",
    )


class Step(Base):
    __tablename__ = "steps"

    id = Column(Integer, primary_key=True, index=True)

    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)

    model = Column(String(100), nullable=False)
    prompt = Column(Text, nullable=False)

    criteria_type = Column(String(50), nullable=True)   # e.g., "contains", "regex", "json_valid"
    criteria_value = Column(Text, nullable=True)        # keyword/pattern or empty for json_valid

    max_retries = Column(Integer, default=2, nullable=False)
    context_mode = Column(String(20), default="full", nullable=False)  # "full" or "code_only"

    workflow = relationship("Workflow", back_populates="steps")
class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)

    status = Column(String(20), nullable=False, default="RUNNING")  # RUNNING/COMPLETED/FAILED
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    workflow = relationship("Workflow")
    run_steps = relationship(
        "RunStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="(RunStep.step_order, RunStep.attempt_no)",
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id = Column(Integer, primary_key=True, index=True)

    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)

    # store step identity + order for easy UI rendering
    step_id = Column(Integer, ForeignKey("steps.id", ondelete="SET NULL"), nullable=True)
    step_order = Column(Integer, nullable=False)

    status = Column(String(20), nullable=False)  # PASSED/FAILED/ERROR
    attempt_no = Column(Integer, nullable=False)

    prompt_used = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    criteria_result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    run = relationship("Run", back_populates="run_steps")
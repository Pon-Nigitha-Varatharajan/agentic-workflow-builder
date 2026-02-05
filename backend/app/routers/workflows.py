from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app import models, schemas

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _ensure_unique_step_orders(steps: List[schemas.StepCreate]) -> None:
    orders = [s.step_order for s in steps]
    if len(orders) != len(set(orders)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate step_order values. Each step must have a unique step_order.",
        )


@router.post("", response_model=schemas.WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: schemas.WorkflowCreate, db: Session = Depends(get_db)):
    _ensure_unique_step_orders(payload.steps)

    wf = models.Workflow(name=payload.name)
    db.add(wf)
    db.flush()  # get wf.id before inserting steps

    for s in payload.steps:
        step = models.Step(
            workflow_id=wf.id,
            step_order=s.step_order,
            model=s.model,
            prompt=s.prompt,
            criteria_type=s.criteria_type,
            criteria_value=s.criteria_value,
            max_retries=s.max_retries,
            context_mode=s.context_mode,
        )
        db.add(step)

    db.commit()
    db.refresh(wf)
    return wf


@router.get("", response_model=List[schemas.WorkflowListItem])
def list_workflows(db: Session = Depends(get_db)):
    # Return lightweight list + step_count
    rows = (
        db.query(
            models.Workflow.id,
            models.Workflow.name,
            models.Workflow.created_at,
            func.count(models.Step.id).label("step_count"),
        )
        .outerjoin(models.Step, models.Step.workflow_id == models.Workflow.id)
        .group_by(models.Workflow.id)
        .order_by(models.Workflow.created_at.desc())
        .all()
    )

    return [
        schemas.WorkflowListItem(
            id=r.id, name=r.name, created_at=r.created_at, step_count=r.step_count
        )
        for r in rows
    ]


@router.get("/{workflow_id}", response_model=schemas.WorkflowRead)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.put("/{workflow_id}", response_model=schemas.WorkflowRead)
def update_workflow(workflow_id: int, payload: schemas.WorkflowUpdate, db: Session = Depends(get_db)):
    _ensure_unique_step_orders(payload.steps)

    wf = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    wf.name = payload.name

    # Replace all steps (simple + reliable for hackathons)
    db.query(models.Step).filter(models.Step.workflow_id == workflow_id).delete()

    for s in payload.steps:
        step = models.Step(
            workflow_id=workflow_id,
            step_order=s.step_order,
            model=s.model,
            prompt=s.prompt,
            criteria_type=s.criteria_type,
            criteria_value=s.criteria_value,
            max_retries=s.max_retries,
            context_mode=s.context_mode,
        )
        db.add(step)

    db.commit()
    db.refresh(wf)
    return wf


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    db.delete(wf)
    db.commit()
    return None
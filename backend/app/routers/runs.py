from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db, SessionLocal
from app import models, schemas
from app.criteria import evaluate
from app.llm_unbound import call_llm, UnboundError
import asyncio
router = APIRouter(prefix="/runs", tags=["runs"])


def _build_criteria(step: models.Step) -> Dict[str, Any]:
    """
    Convert DB fields (criteria_type/value) into criteria dict used by criteria.evaluate()
    """
    if not step.criteria_type:
        return {"type": None}  # means "no criteria"
    if step.criteria_type == "contains":
        return {"type": "contains", "keyword": step.criteria_value or ""}
    if step.criteria_type == "regex":
        return {"type": "regex", "pattern": step.criteria_value or "", "flags": "s"}
    if step.criteria_type == "json_valid":
        return {"type": "json_valid"}
    return {"type": step.criteria_type}  # unknown -> will fail in evaluate()


def _inject_context(prompt: str, context: str) -> str:
    if not context.strip():
        return prompt.strip()
    return (
        "### CONTEXT (output from previous step)\n"
        f"{context.strip()}\n\n"
        "### CURRENT TASK\n"
        f"{prompt.strip()}"
    )


def _context_from_output(output_text: str, context_mode: str) -> str:
    # keep it simple: pass full output forward
    # (you can later re-enable code_only extraction if you want)
    return output_text


async def _execute_workflow_background(run_id: int, workflow_id: int) -> None:
    """
    Background execution:
    - loads workflow steps
    - executes sequentially with criteria+retries
    - writes RunStep logs after each attempt
    - updates Run status to COMPLETED/FAILED
    """
    db: Session = SessionLocal()
    context = ""

    try:
        # Ensure run exists
        run = db.query(models.Run).filter(models.Run.id == run_id).first()
        if not run:
            return

        # Load steps ordered
        steps: List[models.Step] = (
            db.query(models.Step)
            .filter(models.Step.workflow_id == workflow_id)
            .order_by(models.Step.step_order.asc())
            .all()
        )

        if not steps:
            run.status = "FAILED"
            run.ended_at = datetime.utcnow()
            db.add(run)
            db.commit()
            return

        for step in steps:
            final_prompt = _inject_context(step.prompt, context)
            criteria = _build_criteria(step)

            # ----------------------------
            # Retries strategy
            # - User-configured retries (step.max_retries)
            # - plus extra retry "buffer" for flaky network, especially on slower model
            # ----------------------------
            base_retries = int(step.max_retries or 0)

            # The instruct model is often slower / flakier → give it 2 extra attempts
            extra_network_buffer = 2 if step.model == "kimi-k2-instruct-0905" else 1

            total_attempts = (base_retries + extra_network_buffer) + 1  # +1 = first try

            step_passed = False
            last_output: Optional[str] = None
            last_reason: str = ""

            for attempt_no in range(1, total_attempts + 1):
                try:
                    # ----------------------------
                    # Token cap (major ReadError reducer)
                    # ----------------------------
                    max_tokens = 300 if step.model == "kimi-k2p5" else 160

                    output_text, _usage = await call_llm(
                        model=step.model,
                        prompt=final_prompt,
                        max_tokens=max_tokens,
                    )
                    last_output = output_text

                    # Evaluate criteria
                    if not step.criteria_type:
                        crit_res = evaluate(output_text, {})  # no criteria => pass
                    else:
                        crit_res = evaluate(output_text, criteria)

                    last_reason = crit_res.reason

                    run_step = models.RunStep(
                        run_id=run.id,
                        step_id=step.id,
                        step_order=step.step_order,
                        status="PASSED" if crit_res.passed else "FAILED",
                        attempt_no=attempt_no,
                        prompt_used=final_prompt,
                        output=output_text,
                        criteria_result=crit_res.reason,
                        error=None,
                    )
                    db.add(run_step)
                    db.commit()

                    if crit_res.passed:
                        step_passed = True
                        break

                    # If criteria failed (not network), we can retry immediately (no sleep)

                except UnboundError as e:
                    # Network / upstream error from Unbound wrapper
                    run_step = models.RunStep(
                        run_id=run.id,
                        step_id=step.id,
                        step_order=step.step_order,
                        status="ERROR",
                        attempt_no=attempt_no,
                        prompt_used=final_prompt,
                        output=None,
                        criteria_result=None,
                        error=str(e),
                    )
                    db.add(run_step)
                    db.commit()

                    last_reason = f"UnboundError: {str(e)}"

                    # Backoff before retry to reduce flakiness / rate-limit issues
                    # 0.8s, 1.6s, 2.4s, ...
                    await asyncio.sleep(0.8 * attempt_no)
                    continue

            if not step_passed:
                run.status = "FAILED"
                run.ended_at = datetime.utcnow()
                db.add(run)
                db.commit()
                return

            # Step passed → update context for next step
            context = _context_from_output(last_output or "", step.context_mode)

        run.status = "COMPLETED"
        run.ended_at = datetime.utcnow()
        db.add(run)
        db.commit()

    except Exception as e:
        # Mark run failed + store error as a run_step entry (optional but helpful)
        try:
            run = db.query(models.Run).filter(models.Run.id == run_id).first()
            if run:
                run.status = "FAILED"
                run.ended_at = datetime.utcnow()
                db.add(run)

                err_step = models.RunStep(
                    run_id=run_id,
                    step_id=None,
                    step_order=999999,  # puts it at the end
                    status="ERROR",
                    attempt_no=1,
                    prompt_used="(system)",
                    output=None,
                    criteria_result=None,
                    error=str(e),
                )
                db.add(err_step)

                db.commit()
        except Exception:
            pass
    finally:
        db.close()

@router.get("/")
def health():
    return {"message": "Runs router is wired up."}


@router.post(
    "/workflows/{workflow_id}/run",
    response_model=schemas.RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_workflow(workflow_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Milestone 6 change:
    - Create run row
    - Return run_id immediately
    - Execute workflow in background while UI polls GET /runs/{run_id}
    """
    wf = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    steps_exist = (
        db.query(models.Step.id)
        .filter(models.Step.workflow_id == workflow_id)
        .first()
    )
    if not steps_exist:
        raise HTTPException(status_code=400, detail="Workflow has no steps to run")

    run = models.Run(workflow_id=workflow_id, status="RUNNING", started_at=datetime.utcnow())
    db.add(run)
    db.commit()
    db.refresh(run)

    # Fire-and-forget
    background_tasks.add_task(_execute_workflow_background, run.id, workflow_id)

    return schemas.RunCreateResponse(run_id=run.id)


@router.get("/{run_id}", response_model=schemas.RunRead)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run_steps = (
        db.query(models.RunStep)
        .filter(models.RunStep.run_id == run_id)
        .order_by(models.RunStep.step_order.asc(), models.RunStep.attempt_no.asc())
        .all()
    )

    return schemas.RunRead(
        id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        steps=run_steps,
    )


@router.get("/workflows/{workflow_id}/runs", response_model=List[schemas.RunListItem])
def list_workflow_runs(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    runs = (
        db.query(models.Run)
        .filter(models.Run.workflow_id == workflow_id)
        .order_by(models.Run.started_at.desc())
        .all()
    )

    return runs
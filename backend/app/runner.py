from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.llm_unbound import call_llm
from app.criteria import evaluate


ALLOWED_MODELS = {"kimi-k2p5", "kimi-k2-instruct-0905"}


@dataclass
class Step:
    step_id: int
    name: str
    model: str
    prompt: str
    criteria: Dict[str, Any]
    max_retries: int = 2         # total attempts = max_retries + 1
    context_mode: str = "full"   # "full" or "code_only"
    max_tokens: int = 700


def _inject_context(prompt: str, context: str) -> str:
    if not context.strip():
        return prompt.strip()
    return (
        "### CONTEXT (output from previous step)\n"
        f"{context.strip()}\n\n"
        "### CURRENT TASK\n"
        f"{prompt.strip()}"
    )


_CODE_BLOCK_RE = re.compile(r"```(?:\w+)?\s*([\s\S]*?)```", re.MULTILINE)


def _extract_first_code_block(text: str) -> Optional[str]:
    if not text:
        return None
    m = _CODE_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()

    # unclosed fence fallback
    start = text.find("```")
    if start != -1:
        after = text[start + 3 :]
        after = re.sub(r"^\w+\s*\n", "", after)
        return after.strip()

    return None


def _context_from_output(output_text: str, mode: str) -> str:
    if mode == "code_only":
        code = _extract_first_code_block(output_text)
        return f"```python\n{code}\n```" if code else output_text
    return output_text


async def run_demo_workflow_v3() -> Dict[str, Any]:
    """
    Milestone 3 demo runner:
    - sequential execution
    - context passing
    - criteria evaluation + retries
    - stops workflow on permanent fail
    """

    steps: List[Step] = [
        Step(
            step_id=1,
            name="Write add() function",
            model="kimi-k2p5",
            context_mode="code_only",
            max_tokens=250,
            max_retries=1,
            prompt=(
                "Write Python code that defines a function add(a, b) which returns a + b.\n"
                "Return ONLY a single Python code block. No explanations."
            ),
            criteria={
                "type": "regex",
                "pattern": r"```python[\s\S]*```",
                "flags": "s",
            },
        ),
        Step(
            step_id=2,
            name="Write pytest tests",
            model="kimi-k2p5",
            context_mode="code_only",
            max_tokens=900,
            max_retries=3,
            prompt=(
                "Using the CONTEXT code above, write EXACTLY 3 pytest test cases for add(a, b).\n"
                "Rules:\n"
                "1) Return ONLY a single Python code block.\n"
                "2) Do NOT include explanations, analysis, or any text outside the code block.\n"
                "3) Assume add() is already available. Do NOT write placeholder imports.\n"
            ),
            criteria={
                "type": "regex",
                # must contain a python code block
                "pattern": r"```python[\s\S]*```",
                "flags": "s",
            },
        ),
        Step(
            step_id=3,
            name="Generate requirements.txt",
            model="kimi-k2-instruct-0905",
            context_mode="full",
            max_tokens=80,
            max_retries=2,
            prompt=(
                "From the CONTEXT above, output requirements.txt lines ONLY.\n"
                "Rules:\n"
                "1) Output ONLY package names (one per line).\n"
                "2) Do NOT use code fences.\n"
                "3) Do NOT add explanations.\n"
                "If pytest tests exist, include pytest.\n"
            ),
            criteria={
                "type": "contains",
                "keyword": "pytest",
            },
        ),
    ]

    # validate models
    for s in steps:
        if s.model not in ALLOWED_MODELS:
            raise ValueError(f"Unsupported model '{s.model}'. Choose from: {', '.join(sorted(ALLOWED_MODELS))}")

    workflow_status = "COMPLETED"
    context: str = ""
    step_logs: List[Dict[str, Any]] = []

    for step in steps:
        final_prompt = _inject_context(step.prompt, context)

        attempts: List[Dict[str, Any]] = []
        passed = False
        final_output = ""
        final_usage: Dict[str, Any] = {}

        total_attempts = step.max_retries + 1

        for attempt_num in range(1, total_attempts + 1):
            output_text, usage = await call_llm(
                model=step.model,
                prompt=final_prompt,
                max_tokens=step.max_tokens,
            )

            crit = evaluate(output_text, step.criteria)

            attempts.append(
                {
                    "attempt": attempt_num,
                    "passed": crit.passed,
                    "reason": crit.reason,
                    "output": output_text,
                    "usage": usage,
                }
            )

            if crit.passed:
                passed = True
                final_output = output_text
                final_usage = usage
                break

        if not passed:
            workflow_status = "FAILED"
            step_logs.append(
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "model": step.model,
                    "prompt_used": final_prompt,
                    "criteria": step.criteria,
                    "passed": False,
                    "attempts": attempts,
                    "final_output": attempts[-1]["output"] if attempts else "",
                }
            )
            # stop the workflow immediately
            break

        # step passed -> update context for next step
        context = _context_from_output(final_output, step.context_mode)

        step_logs.append(
            {
                "step_id": step.step_id,
                "name": step.name,
                "model": step.model,
                "prompt_used": final_prompt,
                "criteria": step.criteria,
                "passed": True,
                "attempts": attempts,
                "final_output": final_output,
            }
        )

    return {
        "workflow_name": "Demo Workflow (Milestone 3: Criteria + Retries)",
        "workflow_status": workflow_status,
        "steps": step_logs,
    }
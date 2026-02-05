from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class CriteriaResult:
    passed: bool
    reason: str


def evaluate(output_text: str, criteria: Dict[str, Any]) -> CriteriaResult:
    """
    criteria format examples:
      {"type": "contains", "keyword": "pytest"}
      {"type": "regex", "pattern": "```python[\\s\\S]*```"}
      {"type": "json_valid"}

    Returns: CriteriaResult(passed, reason)
    """
    if not criteria or "type" not in criteria:
        return CriteriaResult(True, "no_criteria")

    ctype = criteria.get("type")

    if ctype == "contains":
        keyword = criteria.get("keyword", "")
        if not keyword:
            return CriteriaResult(False, "contains: missing keyword")
        ok = keyword in (output_text or "")
        return CriteriaResult(ok, f"contains: {'found' if ok else 'missing'} '{keyword}'")

    if ctype == "regex":
        pattern = criteria.get("pattern", "")
        flags = criteria.get("flags", "")
        if not pattern:
            return CriteriaResult(False, "regex: missing pattern")

        re_flags = 0
        if "i" in flags:
            re_flags |= re.IGNORECASE
        if "m" in flags:
            re_flags |= re.MULTILINE
        if "s" in flags:
            re_flags |= re.DOTALL

        ok = re.search(pattern, output_text or "", flags=re_flags) is not None
        return CriteriaResult(ok, f"regex: {'matched' if ok else 'no match'}")

    if ctype == "json_valid":
        try:
            json.loads(output_text or "")
            return CriteriaResult(True, "json_valid: parsed")
        except Exception as e:
            return CriteriaResult(False, f"json_valid: parse failed ({type(e).__name__})")

    return CriteriaResult(False, f"unknown criteria type: {ctype}")
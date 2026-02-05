from __future__ import annotations

import asyncio
import random
import httpx
from typing import Any, Dict, Tuple

from app.config import settings


class UnboundError(Exception):
    pass


# Slower model needs longer timeout
MODEL_TIMEOUTS_SECONDS: dict[str, float] = {
    "kimi-k2p5": 60.0,
    "kimi-k2-instruct-0905": 120.0,
}


# HTTP statuses that are usually transient (safe to retry)
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


async def call_llm(model: str, prompt: str, max_tokens: int = 400) -> Tuple[str, Dict[str, Any]]:
    """
    Robust Unbound call with:
    - HTTP/1.1 only
    - retries with backoff (handles ReadError / timeouts / transient 5xx/429)
    - per-model timeout
    - max_tokens to prevent huge outputs
    """

    if not settings.unbound_chat_url:
        raise UnboundError("UNBOUND_CHAT_URL is missing in .env")
    if not settings.unbound_api_key:
        raise UnboundError("UNBOUND_API_KEY is missing in .env")

    url = settings.unbound_chat_url.strip()
    headers = {
        "Authorization": f"Bearer {settings.unbound_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "agentic-workflow-builder/1.0",
        "Connection": "close",  # helps with flaky keep-alive/proxies
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "stream": False,
    }

    # Pick best timeout:
    # - env default used as baseline
    # - model timeout can override upward
    base_total = float(settings.unbound_timeout_seconds)
    model_total = float(MODEL_TIMEOUTS_SECONDS.get(model, base_total))
    total_timeout = max(base_total, model_total)

    timeout = httpx.Timeout(total_timeout, connect=20.0, read=total_timeout)
    limits = httpx.Limits(max_keepalive_connections=0, max_connections=10)

    last_err: Exception | None = None

    # 3 attempts
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=False,            # force HTTP/1.1
                follow_redirects=True,
            ) as client:
                resp = await client.post(url, headers=headers, json=payload)

                # Retry on transient server/rate-limit errors
                if resp.status_code in RETRYABLE_STATUS_CODES:
                    last_err = UnboundError(f"Unbound transient {resp.status_code}: {resp.text[:300]}")
                    raise last_err

                if resp.status_code >= 400:
                    raise UnboundError(f"Unbound error {resp.status_code}: {resp.text}")

                data = resp.json()

            usage: Dict[str, Any] = data.get("usage", {}) if isinstance(data, dict) else {}

            try:
                text = data["choices"][0]["message"]["content"]
            except Exception:
                text = data.get("output") or data.get("text") or data.get("response")

            if not text:
                raise UnboundError(f"Could not parse response. Raw: {data}")

            return text, usage

        except (httpx.ReadError, httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout, UnboundError) as e:
            last_err = e

            # exponential-ish backoff + jitter: ~0.6s, 1.2s, 2.0s
            base_sleep = 0.6 * attempt
            jitter = random.uniform(0.0, 0.25)
            await asyncio.sleep(base_sleep + jitter)
            continue

        except httpx.RequestError as e:
            # other network errors (DNS, etc.)
            raise UnboundError(f"Network error calling Unbound ({type(e).__name__}): {repr(e)}") from e

    raise UnboundError(f"Network ReadError after retries: {repr(last_err)}")
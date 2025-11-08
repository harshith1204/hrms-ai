#!/usr/bin/env python3
"""
HR Profile Creator core logic.

This module exposes helper utilities for generating structured HR job profile JSON
documents using Groq Cloud models. It is designed to be consumed by a FastAPI
service (see `app.py`) but can also be imported directly elsewhere.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from groq import AuthenticationError, BadRequestError, Groq, GroqError, Timeout

load_dotenv()


class HRProfileCreatorError(Exception):
    """Base exception for HR Profile Creator."""


class MissingAPIKeyError(HRProfileCreatorError):
    """Raised when GROQ_API_KEY is not provided."""


DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 2048  # Reduced for faster responses on free tiers
DEFAULT_TIMEOUT = 25  # 25 seconds to stay under 30s free tier limits


@dataclass
class GenerationRequest:
    prompt: str
    schema: Optional[Dict[str, Any]]
    model: str
    temperature: float
    max_tokens: int
    retries: int = 2
    timeout: float = DEFAULT_TIMEOUT


@dataclass
class GenerationResult:
    profile: Dict[str, Any]
    raw: str
    model: str


_BASE_DIR = Path(__file__).resolve().parent
_DEFAULT_SCHEMA_PATH = _BASE_DIR / "schemas" / "core.json"


def _load_default_schema(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise HRProfileCreatorError(
            f"Default schema file not found at '{path}'. Ensure the consolidated schema exists."
        )
    except json.JSONDecodeError as exc:
        raise HRProfileCreatorError(
            f"Default schema at '{path}' contains invalid JSON."
        ) from exc


DEFAULT_SCHEMA = _load_default_schema(_DEFAULT_SCHEMA_PATH)

_client_lock = Lock()
_client: Optional[Groq] = None


def build_system_prompt(schema: Optional[Dict[str, Any]]) -> str:
    """Create the system prompt guiding the LLM output."""
    base_prompt = (
        "You are a senior HR business partner who drafts job profiles for recruiters and hiring managers.\n"
        "Produce only valid JSON—no markdown, code fences, or prose outside the JSON object.\n"
        "Guidelines:\n"
        "- Mirror the schema exactly; keep every key present once and avoid extra fields.\n"
        "- Use concise, inclusive, and professional language suited for job descriptions.\n"
        "- Ground every detail strictly in the user's instructions. Do not infer employers, brands, tools, budgets, or numbers that were not supplied.\n"
        "- If a detail is missing:\n"
        '  * For string fields, set the value to "Not specified".\n'
        "  * For numeric fields, set the value to null.\n"
        "  * For arrays or objects, leave them empty unless the user explicitly lists items.\n"
        "- Align tone and structure with scenario cues (e.g., urgent hiring, graduate roles, leadership positions, multi-location teams).\n"
        "- Respect all quantitative constraints such as budgets, years of experience, headcount, and locations.\n"
        "- When the prompt contains conflicting information, prioritise the latest explicit directive and keep the rest consistent.\n"
        "- Highlight practical next steps (like interview process or onboarding expectations) only when the schema includes relevant fields.\n"
        "- Never expose reasoning or instructions; return the final JSON object only."
    )
    if schema:
        schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
        base_prompt += (
            "\nUse this JSON template and fill every field thoughtfully:\n"
            f"{schema_json}\n"
            "Replace placeholders with content that follows the guidelines above."
        )
    return base_prompt


def strip_code_fences(text: str) -> str:
    """Remove Markdown code fences if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    parts = stripped.split("```")
    if len(parts) < 3:
        return stripped

    # The content is expected to be the middle part. Drop optional language hint.
    inner = parts[1]
    inner_lines = inner.splitlines()
    if inner_lines and inner_lines[0].strip().isalpha():
        inner_lines = inner_lines[1:]
    return "\n".join(inner_lines).strip()


def ensure_api_key() -> str:
    """Read the Groq API key from the environment."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "GROQ_API_KEY environment variable is not set. "
            "Create an API key in Groq Cloud and export it before running the service."
        )
    return api_key


def get_client() -> Groq:
    """Return a Groq client instance, creating one if necessary."""
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is None:
            _client = Groq(api_key=ensure_api_key())
    return _client


def call_groq_api(
    client: Groq, request: GenerationRequest
) -> Tuple[Dict[str, Any], str]:
    """Invoke Groq's chat completion API and parse the JSON response."""
    system_prompt = build_system_prompt(request.schema)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.prompt},
    ]

    last_error: Optional[Exception] = None
    for attempt in range(request.retries + 1):
        try:
            completion = client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format={"type": "json_object"},
                timeout=request.timeout,
            )
        except Timeout as exc:
            raise HRProfileCreatorError(
                f"Request timed out after {request.timeout} seconds. Try with a shorter prompt or lower max_tokens."
            ) from exc
        except AuthenticationError as exc:
            raise MissingAPIKeyError(
                "Groq authentication failed. Confirm that GROQ_API_KEY is present and valid."
            ) from exc
        except BadRequestError as exc:
            if "response_format" in str(exc):
                # Retry without forcing JSON mode; model may not support the flag.
                completion = client.chat.completions.create(
                    model=request.model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    timeout=request.timeout,
                )
            else:
                raise HRProfileCreatorError(
                    f"Groq rejected the request: {exc}"
                ) from exc
        except GroqError as exc:
            raise HRProfileCreatorError(f"Groq API error: {exc}") from exc
        raw_content = completion.choices[0].message.content or ""
        cleaned = strip_code_fences(raw_content)
        try:
            parsed = json.loads(cleaned)
            return parsed, cleaned
        except json.JSONDecodeError as exc:
            last_error = exc
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Reminder: respond with strictly valid JSON that matches the required structure. "
                        "Do not include commentary or code fences."
                    ),
                }
            )
    raise HRProfileCreatorError(
        f"Failed to parse JSON from model response after {request.retries + 1} attempts."
    ) from last_error


def generate_profile(
    prompt: str,
    schema: Optional[Dict[str, Any]] = None,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    retries: int = 2,
    timeout: float = DEFAULT_TIMEOUT,
    client: Optional[Groq] = None,
) -> GenerationResult:
    """Generate an HR profile using the specified instructions and optional schema."""
    groq_client = client or get_client()
    schema_payload = deepcopy(schema if schema is not None else DEFAULT_SCHEMA)
    request = GenerationRequest(
        prompt=prompt,
        schema=schema_payload,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=retries,
        timeout=timeout,
    )
    profile, raw = call_groq_api(groq_client, request)
    return GenerationResult(profile=profile, raw=raw, model=model)

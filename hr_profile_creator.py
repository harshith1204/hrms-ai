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
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from groq import Groq

DEFAULT_MODEL = "llama3-8b-8192"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 2048


class HRProfileCreatorError(Exception):
    """Base exception for HR Profile Creator."""


class MissingAPIKeyError(HRProfileCreatorError):
    """Raised when GROQ_API_KEY is not provided."""


@dataclass
class GenerationRequest:
    prompt: str
    schema: Optional[Dict[str, Any]]
    model: str
    temperature: float
    max_tokens: int
    retries: int = 2


@dataclass
class GenerationResult:
    profile: Dict[str, Any]
    raw: str
    model: str


def build_system_prompt(schema: Optional[Dict[str, Any]]) -> str:
    """Create the system prompt guiding the LLM output."""
    base_prompt = (
        "You are an assistant that generates HR job profile data. "
        "Always respond with strictly valid JSON and nothing else. "
        "Populate each field with professional, realistic, and engaging language suitable "
        "for corporate job postings. Do not omit fields. Avoid commentary outside JSON."
    )
    if schema:
        schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
        base_prompt += (
            " Use exactly the following JSON structure and ensure the response includes every field:\n"
            f"{schema_json}\n"
            "Replace every placeholder with appropriate content inspired by the user's request."
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


@lru_cache(maxsize=1)
def get_client() -> Groq:
    """Return a cached Groq client instance."""
    return Groq(api_key=ensure_api_key())


def call_groq_api(client: Groq, request: GenerationRequest) -> Tuple[Dict[str, Any], str]:
    """Invoke Groq's chat completion API and parse the JSON response."""
    system_prompt = build_system_prompt(request.schema)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.prompt},
    ]

    last_error: Optional[Exception] = None
    for attempt in range(request.retries + 1):
        completion = client.chat.completions.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_format={"type": "json_object"},
        )
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
    client: Optional[Groq] = None,
) -> GenerationResult:
    """Generate an HR profile using the specified instructions and optional schema."""
    groq_client = client or get_client()
    request = GenerationRequest(
        prompt=prompt,
        schema=schema,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=retries,
    )
    profile, raw = call_groq_api(groq_client, request)
    return GenerationResult(profile=profile, raw=raw, model=model)

#!/usr/bin/env python3
"""
HR Profile Creator

A command-line utility that leverages Groq Cloud's LLMs to generate structured HR
profile JSON documents from natural-language prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from groq import Groq


DEFAULT_MODEL = "llama3-8b-8192"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 2048


class HRProfileCreatorError(Exception):
    """Base exception for HR Profile Creator."""


class MissingAPIKeyError(HRProfileCreatorError):
    """Raised when GROQ_API_KEY is not provided."""


def load_prompt(prompt: Optional[str], prompt_file: Optional[Path]) -> str:
    """Return the prompt string, resolving precedence between CLI text and file."""
    if prompt and prompt_file:
        raise HRProfileCreatorError(
            "Please provide either --prompt or --prompt-file, not both."
        )
    if prompt_file:
        try:
            return prompt_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise HRProfileCreatorError(f"Prompt file not found: {prompt_file}") from exc
    if prompt:
        return prompt.strip()
    raise HRProfileCreatorError("A prompt is required. Supply --prompt or --prompt-file.")


def load_schema(schema_path: Optional[Path]) -> Optional[str]:
    """Read a schema file if provided."""
    if not schema_path:
        return None
    try:
        raw = schema_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise HRProfileCreatorError(f"Schema file not found: {schema_path}") from exc
    # Validate that the schema is valid JSON; we only need the raw text afterwards.
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HRProfileCreatorError(
            f"Schema file does not contain valid JSON: {schema_path}"
        ) from exc
    if not isinstance(parsed, dict):
        raise HRProfileCreatorError("Schema JSON must be an object at the top level.")
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def build_system_prompt(schema: Optional[str]) -> str:
    """Create the system prompt guiding the LLM output."""
    base_prompt = (
        "You are an assistant that generates HR job profile data. "
        "Always respond with strictly valid JSON and nothing else. "
        "Populate each field with professional, realistic, and engaging language suitable "
        "for corporate job postings. Do not omit fields. Avoid commentary outside JSON."
    )
    if schema:
        base_prompt += (
            " Use exactly the following JSON structure and ensure the response includes every field:\n"
            f"{schema}\n"
            "Replace every placeholder with appropriate content inspired by the user's request."
        )
    return base_prompt


def strip_code_fences(text: str) -> str:
    """Remove Markdown code fences if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Handle optional language specifier
        end = stripped.rfind("```")
        if end == 0:
            return stripped
        inner = stripped.split("```", 2)[1]
        # Remove optional leading language identifier
        inner_lines = inner.splitlines()
        if inner_lines and inner_lines[0].strip() == "":
            inner_lines = inner_lines[1:]
        elif inner_lines and inner_lines[0].strip().isalpha():
            inner_lines = inner_lines[1:]
        return "\n".join(inner_lines)
    return stripped


def ensure_api_key() -> str:
    """Read the Groq API key from the environment."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "GROQ_API_KEY environment variable is not set. "
            "Create an API key in Groq Cloud and export it before running the script."
        )
    return api_key


@dataclass
class GenerationRequest:
    prompt: str
    schema: Optional[str]
    model: str
    temperature: float
    max_tokens: int
    retries: int = 2


def call_groq_api(
    client: Groq, request: GenerationRequest
) -> Tuple[Dict[str, Any], str, Any]:
    """Invoke Groq's chat completion API and parse the JSON response."""
    system_prompt = build_system_prompt(request.schema)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.prompt},
    ]

    last_error: Optional[Exception] = None
    completion: Optional[Any] = None
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
            return parsed, cleaned, completion
        except json.JSONDecodeError as exc:
            last_error = exc
            # Reinforce the instruction for valid JSON in subsequent attempts.
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Reminder: respond with strictly valid JSON that matches the required structure. "
                        "Do not include commentary or code fences."
                    ),
                }
            )
    assert completion is not None  # for mypy; completion should be set once loop entered.
    raise HRProfileCreatorError(
        f"Failed to parse JSON from model response after {request.retries + 1} attempts."
    ) from last_error


def write_output(
    parsed: Dict[str, Any],
    raw: str,
    output_path: Optional[Path],
    pretty: bool,
) -> None:
    """Print and optionally persist the generated profile."""
    if pretty:
        output_text = json.dumps(parsed, ensure_ascii=False, indent=2)
    else:
        output_text = raw

    if output_path:
        output_path.write_text(output_text, encoding="utf-8")
    print(output_text)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate HR profile JSON structures using Groq Cloud models."
    )
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument(
        "-p",
        "--prompt",
        type=str,
        help="Natural-language instructions describing the desired HR profile.",
    )
    prompt_group.add_argument(
        "--prompt-file",
        type=Path,
        help="Path to a file containing the prompt.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        help="Optional path to a JSON schema or template dict representing the desired output structure.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Groq model to use (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"Sampling temperature (default: {DEFAULT_TEMPERATURE}).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Maximum tokens to generate (default: {DEFAULT_MAX_TOKENS}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path to save the generated JSON.",
    )
    parser.add_argument(
        "--no-pretty",
        action="store_true",
        help="Disable pretty-printing of JSON in stdout/output files.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Number of retry attempts if the model response is not valid JSON.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Entrypoint for the CLI."""
    try:
        args = parse_args(argv)
        prompt = load_prompt(args.prompt, args.prompt_file)
        schema = load_schema(args.schema)
        api_key = ensure_api_key()
        client = Groq(api_key=api_key)
        generation_request = GenerationRequest(
            prompt=prompt,
            schema=schema,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            retries=args.retries,
        )
        parsed, raw_json, completion = call_groq_api(client, generation_request)
        write_output(
            parsed=parsed,
            raw=raw_json,
            output_path=args.output,
            pretty=not args.no_pretty,
        )
        return 0
    except MissingAPIKeyError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except HRProfileCreatorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

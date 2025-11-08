from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from hr_profile_creator import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    HRProfileCreatorError,
    MissingAPIKeyError,
    generate_profile,
)


app = FastAPI(
    title="HR Profile Generator",
    version="1.0.0",
    description="Generate structured HR job profile JSON payloads using Groq Cloud models.",
)


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        description="Natural-language instructions describing the desired HR profile.",
    )
    schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional JSON template dict that defines the required output structure.",
    )
    model: Optional[str] = Field(
        default=DEFAULT_MODEL,
        description="Groq model identifier to use for generation.",
    )
    temperature: Optional[float] = Field(
        default=DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="Sampling temperature to control creativity.",
    )
    max_tokens: Optional[int] = Field(
        default=DEFAULT_MAX_TOKENS,
        ge=1,
        le=4096,
        description="Maximum number of tokens to generate.",
    )
    retries: Optional[int] = Field(
        default=2,
        ge=0,
        le=5,
        description="Retry count if the model returns non-JSON output.",
    )


class GenerateResponse(BaseModel):
    profile: Dict[str, Any]
    raw: str
    model: str


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """Simple health probe for uptime monitoring."""
    return {"status": "ok"}


@app.post(
    "/profiles/generate",
    response_model=GenerateResponse,
    tags=["Profiles"],
    summary="Generate an HR profile from a prompt",
)
async def create_profile(payload: GenerateRequest) -> GenerateResponse:
    try:
        result = generate_profile(
            prompt=payload.prompt,
            schema=payload.schema,
            model=payload.model or DEFAULT_MODEL,
            temperature=payload.temperature
            if payload.temperature is not None
            else DEFAULT_TEMPERATURE,
            max_tokens=payload.max_tokens
            if payload.max_tokens is not None
            else DEFAULT_MAX_TOKENS,
            retries=payload.retries if payload.retries is not None else 2,
        )
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except HRProfileCreatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        raise HTTPException(
            status_code=500, detail="Unexpected error generating profile."
        ) from exc

    return GenerateResponse(profile=result.profile, raw=result.raw, model=result.model)

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from profile_creator import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    HRProfileCreatorError,
    MissingAPIKeyError,
    generate_profile,
)

app = FastAPI(
    title="HR Profile Generator",
    version="1.0.0",
    description="Generate structured HR job profile JSON payloads using Groq Cloud models.",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    timeout: Optional[float] = Field(
        default=DEFAULT_TIMEOUT,
        ge=5.0,
        le=60.0,
        description="Request timeout in seconds (max 30s recommended for free tiers).",
    )


class GenerateResponse(BaseModel):
    profile: Dict[str, Any]
    raw: str
    model: str


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Comprehensive health check including API connectivity."""
    health_status = {
        "status": "ok",
        "service": "HR Profile Generator",
        "version": "1.0.0",
        "groq_api": "unknown",
        "free_tier_optimized": True,
    }

    try:
        # Test API key by checking if we can create a client
        from profile_creator import get_client

        get_client()  # Test client creation to validate API key
        health_status["groq_api"] = "configured"
    except Exception as e:
        health_status["groq_api"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    return health_status


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
            temperature=(
                payload.temperature
                if payload.temperature is not None
                else DEFAULT_TEMPERATURE
            ),
            max_tokens=(
                payload.max_tokens
                if payload.max_tokens is not None
                else DEFAULT_MAX_TOKENS
            ),
            retries=payload.retries if payload.retries is not None else 2,
            timeout=payload.timeout if payload.timeout is not None else DEFAULT_TIMEOUT,
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

"""
LLM abstraction (design doc §3.2, §4):

Provider priority:
    1. Gemini
    2. Groq
    3. Ollama

LiteLLM provides one common interface for all providers.

Structured output:
    - The model is instructed to return JSON.
    - JSON is parsed using json.loads().
    - The result is validated using the supplied Pydantic schema.
    - Invalid output is retried.
    - If one provider fails, the next provider is tried.
    - If all providers fail, LLMGenerationError is raised.

Important:
    Some providers/models do not reliably support LiteLLM's
    response_format={"type": "json_object"} option.

Therefore JSON response_format is enabled only for Gemini.
All providers are still required to return JSON through the prompt,
and Pydantic validation remains mandatory.
"""

import json
import logging
from typing import Type, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from app.config import get_settings


# ============================================================
# Logging
# ============================================================

logger = logging.getLogger("adpilot.llm")


# ============================================================
# Settings
# ============================================================

settings = get_settings()


# ============================================================
# Generic Pydantic Type
# ============================================================

T = TypeVar("T", bound=BaseModel)


# ============================================================
# Custom Exception
# ============================================================

class LLMGenerationError(Exception):
    """
    Raised when all configured LLM providers fail
    to generate valid structured output.
    """

    pass


# ============================================================
# Provider Chain
# ============================================================

def _provider_chain() -> list[dict]:
    """
    Build the provider fallback chain.

    Priority:

        Gemini
           ↓
        Groq
           ↓
        Ollama
    """

    chain = []

    # --------------------------------------------------------
    # Gemini
    # --------------------------------------------------------

    if settings.GEMINI_API_KEY:

        chain.append(
            {
                "name": "gemini",
                "model": settings.GEMINI_MODEL,
                "api_key": settings.GEMINI_API_KEY,
            }
        )

    # --------------------------------------------------------
    # Groq
    # --------------------------------------------------------

    if settings.GROQ_API_KEY:

        chain.append(
            {
                "name": "groq",
                "model": settings.GROQ_MODEL,
                "api_key": settings.GROQ_API_KEY,
            }
        )

    # --------------------------------------------------------
    # Ollama
    # --------------------------------------------------------

    if settings.OLLAMA_BASE_URL:

        chain.append(
            {
                "name": "ollama",
                "model": settings.OLLAMA_MODEL,
                "api_base": settings.OLLAMA_BASE_URL,
            }
        )

    # --------------------------------------------------------
    # No provider
    # --------------------------------------------------------

    if not chain:

        raise LLMGenerationError(
            "No LLM provider configured. "
            "Set GEMINI_API_KEY in .env, or configure "
            "GROQ_API_KEY / OLLAMA_BASE_URL as a fallback."
        )

    return chain


# ============================================================
# Generate Structured Output
# ============================================================

def generate_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    max_retries: int = 2,
) -> T:
    """
    Generate structured JSON from the configured LLM providers.

    Provider order:

        Gemini → Groq → Ollama

    Each provider can make multiple attempts.

    The response is:

        1. Received from the LLM
        2. Parsed as JSON
        3. Validated using the Pydantic schema

    If the provider fails, the next provider is tried.
    """

    last_error: Exception | None = None

    # ========================================================
    # Build Provider Chain
    # ========================================================

    providers = _provider_chain()

    logger.info(
        "LLM provider chain: %s",
        " -> ".join(
            provider["model"]
            for provider in providers
        ),
    )

    # ========================================================
    # Try Providers
    # ========================================================

    for provider in providers:

        provider_name = provider["name"]
        provider_model = provider["model"]

        logger.info(
            "Trying LLM provider: %s (%s)",
            provider_name,
            provider_model,
        )

        # ====================================================
        # Retry Current Provider
        # ====================================================

        for attempt in range(max_retries + 1):

            try:

                # ------------------------------------------------
                # Generate JSON Schema
                # ------------------------------------------------

                schema_json = json.dumps(
                    schema.model_json_schema(),
                    ensure_ascii=False,
                )

                # ------------------------------------------------
                # System Message
                # ------------------------------------------------

                system_content = (
                    system_prompt
                    + "\n\n"
                    + "You MUST respond with ONLY valid JSON."
                    + "\n"
                    + "Do not use markdown."
                    + "\n"
                    + "Do not use ```json."
                    + "\n"
                    + "Do not add explanations."
                    + "\n"
                    + "Do not add text before or after the JSON."
                    + "\n\n"
                    + "The JSON MUST match this Pydantic JSON Schema:"
                    + "\n"
                    + schema_json
                )

                # ------------------------------------------------
                # Messages
                # ------------------------------------------------

                messages = [
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ]

                # ------------------------------------------------
                # Retry Feedback
                # ------------------------------------------------

                if attempt > 0 and last_error is not None:

                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was invalid "
                                "for the required JSON schema.\n\n"
                                f"Validation error:\n{last_error}\n\n"
                                "Return ONLY corrected JSON."
                            ),
                        }
                    )

                # =================================================
                # LiteLLM Request
                # =================================================

                completion_kwargs = {
                    "model": provider_model,
                    "messages": messages,
                    "timeout": settings.LLM_TIMEOUT_SECONDS,
                }

                # -------------------------------------------------
                # Add API Key when available
                # -------------------------------------------------

                if provider.get("api_key"):

                    completion_kwargs["api_key"] = (
                        provider["api_key"]
                    )

                # -------------------------------------------------
                # Add API Base when available
                # -------------------------------------------------

                if provider.get("api_base"):

                    completion_kwargs["api_base"] = (
                        provider["api_base"]
                    )

                # =================================================
                # JSON Mode
                # =================================================
                #
                # Gemini supports LiteLLM JSON mode reliably.
                #
                # Some Groq/Ollama models may reject:
                #
                # response_format={"type": "json_object"}
                #
                # So we only add it for Gemini.
                #
                # Pydantic validation is still performed for
                # every provider.
                # =================================================

                if provider_name == "gemini":

                    completion_kwargs["response_format"] = {
                        "type": "json_object"
                    }

                # =================================================
                # Call LLM
                # =================================================

                response = litellm.completion(
                    **completion_kwargs
                )

                # =================================================
                # Extract Content
                # =================================================

                raw_content = (
                    response["choices"][0]["message"]["content"]
                )

                # ------------------------------------------------
                # Safety Check
                # ------------------------------------------------

                if not raw_content:

                    raise ValueError(
                        "LLM returned empty response"
                    )

                # =================================================
                # Parse JSON
                # =================================================

                raw_content = raw_content.strip()

                # ------------------------------------------------
                # Remove accidental Markdown fences
                # ------------------------------------------------

                if raw_content.startswith("```json"):

                    raw_content = raw_content[
                        len("```json"):
                    ].strip()

                    if raw_content.endswith("```"):

                        raw_content = raw_content[
                            :-3
                        ].strip()

                elif raw_content.startswith("```"):

                    raw_content = raw_content[
                        len("```"):
                    ].strip()

                    if raw_content.endswith("```"):

                        raw_content = raw_content[
                            :-3
                        ].strip()

                # =================================================
                # JSON Decode
                # =================================================

                parsed = json.loads(
                    raw_content
                )

                # =================================================
                # Pydantic Validation
                # =================================================

                validated = schema.model_validate(
                    parsed
                )

                # =================================================
                # Success
                # =================================================

                logger.info(
                    "LLM generation successful: "
                    "provider=%s model=%s attempt=%s",
                    provider_name,
                    provider_model,
                    attempt + 1,
                )

                return validated

            # ====================================================
            # JSON / Pydantic Validation Error
            # ====================================================

            except (
                json.JSONDecodeError,
                ValidationError,
                ValueError,
            ) as e:

                last_error = e

                logger.warning(
                    "LLM output validation failed "
                    "(provider=%s model=%s attempt=%s/%s): %s",
                    provider_name,
                    provider_model,
                    attempt + 1,
                    max_retries + 1,
                    e,
                )

                # -----------------------------------------------
                # Retry same provider
                # -----------------------------------------------

                continue

            # ====================================================
            # Provider / Network / API Error
            # ====================================================

            except Exception as e:

                last_error = e

                logger.warning(
                    "LLM provider failed "
                    "(provider=%s model=%s): %s",
                    provider_name,
                    provider_model,
                    e,
                )

                # -----------------------------------------------
                # Provider is unavailable.
                #
                # Move to next provider instead of wasting
                # retries on the same provider.
                # -----------------------------------------------

                break

    # ============================================================
    # All Providers Failed
    # ============================================================

    raise LLMGenerationError(
        "All LLM providers exhausted. "
        f"Last error: {last_error}"
    )
import os
import logging
from typing import List, Dict, Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

# Attempt to import the official Groq SDK; if unavailable, raise a clear error.
try:
    from groq import Groq
except ImportError as exc:
    raise ImportError(
        "Groq SDK is not installed. Please add 'groq' to backend/requirements.txt and install it."
    ) from exc

logger = logging.getLogger(__name__)

class GroqSettings(BaseModel):
    api_key: str = Field(..., env="GROQ_API_KEY")
    model: str = Field(..., env="GROQ_MODEL")
    timeout_seconds: int = Field(30, description="HTTP request timeout for Groq calls")
    max_history_messages: int = Field(
        20, description="Maximum number of recent messages (user+assistant) to send to the model"
    )

def get_groq_client() -> Groq:
    settings = GroqSettings()
    return Groq(api_key=settings.api_key)

async def generate_response(
    user_id: str, messages: List[Dict[str, str]]
) -> str:
    """Call Groq LLM to generate a response.

    Parameters
    ----------
    user_id: str
        Identifier of the caller – used only for logging.
    messages: List[Dict[str, str]]
        Chat history in OpenAI‑compatible format, e.g. [{"role": "user", "content": "Hello"}, ...]

    Returns
    -------
    str
        The assistant's reply.
    """
    client = get_groq_client()
    settings = GroqSettings()

    # Basic system prompt defining Lexi's personality and safety constraints.
    system_prompt = (
        "You are Lexi, a friendly educational assistant for children (ages 4‑10) and their caregivers. "
        "Provide clear, age‑appropriate explanations about the Dyscover platform, its games, and features. "
        "Never diagnose dyslexia, claim clinical accuracy, or share personal data. "
        "Encourage users to consult qualified professionals when appropriate. "
        "Maintain a supportive tone and avoid political or controversial topics."
    )

    # Insert system prompt as the first message.
    payload = [
        {"role": "system", "content": system_prompt},
        *messages[-settings.max_history_messages :],
    ]

    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=payload,
            temperature=0.7,
            max_tokens=1024,
            timeout=settings.timeout_seconds,
        )
        answer = response.choices[0].message.content
        if not answer:
            raise HTTPException(
                status_code=502,
                detail="Groq returned an empty response. This is unexpected and may indicate a provider issue.",
            )
        return answer.strip()
    except Exception as exc:
        logger.exception("Groq request failed for user %s", user_id)
        # Mask internal errors from the client while preserving useful diagnostics for logs.
        raise HTTPException(
            status_code=502,
            detail="Failed to communicate with the AI service. Please try again later.",
        ) from exc


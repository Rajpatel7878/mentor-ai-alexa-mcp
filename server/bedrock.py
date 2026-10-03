"""
bedrock.py — Amazon Bedrock client wrapper for Mentor AI.

Responsibilities
----------------
- Build a boto3 Bedrock Runtime client from environment variables.
- Invoke a model (Anthropic Claude by default) with a system + user prompt.
- Return a concise, voice-friendly answer string.
- Fall back to an offline canned response when credentials are absent or
  any boto3/botocore error occurs, so the server stays usable without AWS.

Environment variables read
--------------------------
  AWS_REGION        (default: us-east-1)
  BEDROCK_MODEL_ID  (default: anthropic.claude-3-haiku-20240307-v1:0)
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  — standard boto3 credential chain
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID: str = os.getenv(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-haiku-20240307-v1:0",
)

# Maximum tokens for the model reply (kept short for voice output)
MAX_TOKENS: int = 256

# Offline mode is automatic when no credential source is configured.  An
# explicit BEDROCK_OFFLINE override is useful for local development and CI.
# App Runner and other AWS runtimes normally provide credentials through the
# container/web-identity providers rather than AWS_ACCESS_KEY_ID, so checking
# only those two environment variables would incorrectly disable Bedrock.
_OFFLINE_OVERRIDE = os.getenv("BEDROCK_OFFLINE", "auto").strip().lower()


def _is_real_credential(value: Optional[str]) -> bool:
    """Return False for empty values and the placeholders in .env.example."""
    if not value:
        return False
    return not value.strip().upper().startswith("YOUR_")


def _credential_source_configured() -> bool:
    """Detect common boto3 credential sources without making a network call."""
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if _is_real_credential(access_key) and _is_real_credential(secret_key):
        return True

    # These variables are used by profiles, ECS/App Runner task roles, and
    # web-identity roles respectively.
    provider_variables = (
        "AWS_PROFILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_ROLE_ARN",
        "AWS_BEARER_TOKEN_BEDROCK",
    )
    if any(os.getenv(name) for name in provider_variables):
        return True

    # boto3 also reads the default shared credentials/config files.
    aws_dir = Path.home() / ".aws"
    return any(
        (aws_dir / filename).is_file()
        for filename in ("credentials", "config")
    )


def is_offline() -> bool:
    """Return whether Bedrock calls should use the local fallback."""
    if _OFFLINE_OVERRIDE in {"1", "true", "yes", "on"}:
        return True
    if _OFFLINE_OVERRIDE in {"0", "false", "no", "off"}:
        return False
    return not _credential_source_configured()


# ─────────────────────────────────────────────────────────────────────────────
# Lazy client (created once on first real call)
# ─────────────────────────────────────────────────────────────────────────────

_client = None  # boto3 BedrockRuntime client


def _get_client():
    global _client
    if _client is None:
        import boto3  # noqa: PLC0415

        _client = boto3.client(
            "bedrock-runtime",
            region_name=AWS_REGION,
        )
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# Offline fallback answers
# ─────────────────────────────────────────────────────────────────────────────

_OFFLINE_ANSWERS: dict[str, str] = {
    "mentor": (
        "Set one clear goal for this week. Break it into three daily actions. "
        "Reflect each evening for five minutes. Consistency beats intensity every time."
    ),
    "cto": (
        "Start with boring technology that your team already knows. "
        "Defer architectural decisions until you have real load data. "
        "Invest in observability from day one."
    ),
    "pm": (
        "Talk to five customers before writing a single line of spec. "
        "Define success metrics upfront. "
        "Ship the smallest thing that tests your core assumption."
    ),
    "marketing": (
        "Pick one channel and go deep before spreading thin. "
        "Document what works, then double it. "
        "Your message should answer: 'So what?' in under ten seconds."
    ),
    "vc": (
        "Focus on product-market fit first. "
        "Investors want traction, not just ideas. "
        "Know your metrics cold before any meeting."
    ),
    "engineer": (
        "Write the test before the fix. "
        "Make it work, then make it right, then make it fast — in that order. "
        "Readable code is more valuable than clever code."
    ),
    "operations": (
        "Document every manual process as a runbook. "
        "Automate anything you do more than twice. "
        "Run a blameless post-mortem after every incident."
    ),
    "analyst": (
        "Start with the question, not the data. "
        "Validate your numbers against a second source. "
        "A chart that needs a legend is a chart that needs a rethink."
    ),
    "legal": (
        "Always read the full contract before signing. "
        "Pay attention to indemnity and liability clauses. "
        "This is general information, not professional legal advice. "
        "Please consult a qualified attorney for your specific situation."
    ),
    "healthcare": (
        "Maintain a consistent sleep schedule and stay hydrated. "
        "Track symptoms before your appointment so you can describe them clearly. "
        "This is general information, not professional medical advice. "
        "Please consult a qualified healthcare provider for your specific situation."
    ),
}

_DEFAULT_OFFLINE_ANSWER = (
    "I am running in offline mode. "
    "Please configure AWS credentials to get live answers. "
    "Check the README for setup instructions."
)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _offline_answer(persona_name: str, disclaimer: str = "") -> str:
    """Return a canned answer and preserve regulated-domain disclaimers."""
    answer = _OFFLINE_ANSWERS.get(persona_name, _DEFAULT_OFFLINE_ANSWER)
    if disclaimer and disclaimer not in answer:
        answer = f"{answer}\n{disclaimer}"
    return answer


def ask_bedrock(
    question: str,
    system_prompt: str,
    persona_name: str,
    disclaimer: str = "",
) -> str:
    """
    Invoke Amazon Bedrock with *system_prompt* and *question*.

    Returns the model's text reply (with optional *disclaimer* appended).
    Falls back to a canned offline answer on any error.
    """
    if is_offline():
        logger.info("Offline mode - returning canned answer for persona '%s'.", persona_name)
        return _offline_answer(persona_name, disclaimer)

    try:
        client = _get_client()
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": MAX_TOKENS,
                "system": system_prompt,
                "messages": [{"role": "user", "content": question}],
            }
        )
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        answer: str = result["content"][0]["text"].strip()

        if disclaimer and disclaimer not in answer:
            answer = f"{answer}\n{disclaimer}"

        return answer

    except Exception as exc:  # noqa: BLE001
        # Import errors caught here too (botocore not installed, etc.)
        _log_bedrock_error(exc, persona_name)
        return _offline_answer(persona_name, disclaimer)


def _log_bedrock_error(exc: Exception, persona_name: str) -> None:
    """Log a Bedrock error without leaking credentials."""
    exc_type = type(exc).__name__
    if exc_type in ("NoCredentialsError", "PartialCredentialsError"):
        logger.warning("Bedrock credentials missing - falling back to offline mode.")
    elif exc_type == "ClientError":
        logger.warning("Bedrock ClientError for persona '%s': %s", persona_name, exc)
    else:
        logger.error(
            "Unexpected Bedrock error (%s) for persona '%s': %s",
            exc_type,
            persona_name,
            exc,
        )

"""
server.py — Mentor AI MCP Server (Streamable HTTP transport).

Endpoints
---------
  /mcp        — MCP Streamable HTTP transport (auto-mounted by FastMCP)
  /api/ask    — Plain HTTP POST, returns {persona, answer}; rate-limited
  /health     — Plain HTTP GET, returns {status, version, mode}

MCP Tools
---------
  list_personas   — Return all available persona names
  route_question  — Return which persona would handle a question
  ask_mentor      — Full pipeline: route → Bedrock → answer

Security
--------
  - Prompt-injection guard: INJECTION regex blocks malicious inputs in ask_mentor.
    ⚠️  DO NOT MODIFY the INJECTION pattern or its handling without manual review.
  - Per-IP rate limiter on both /api/ask and /mcp (see limiter.py).
  - CORS origin controlled by CORS_ORIGIN env var.

Usage
-----
  python server.py
  # or via uvicorn directly:
  # uvicorn server:app --host 0.0.0.0 --port 8000
"""

# NOTE: Do NOT add 'from __future__ import annotations' here.
# The MCP SDK uses issubclass() on function parameter annotations at decoration
# time. Lazy annotations (PEP 563) turn them into strings and break that check
# on Python 3.10+. Eager evaluation is required.

import logging
import os
import re
import sys
from pathlib import Path

# ── Load .env before any other env reads ──────────────────────────────────────
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

# ── Logging setup ─────────────────────────────────────────────────────────────
# Keep logs usable on Windows consoles that still default to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, OSError, ValueError):
        pass

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("mentor_ai")

# ── Local modules ─────────────────────────────────────────────────────────────
from personas import route, get_persona, all_persona_names  # noqa: E402
from bedrock import ask_bedrock, is_offline  # noqa: E402
from limiter import check_rate_limit, get_client_ip, RateLimitExceeded  # noqa: E402

# ── MCP / Starlette ───────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

VERSION = "1.0.0"

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
CORS_ORIGIN: str = os.getenv("CORS_ORIGIN", "*")
MAX_QUESTION_LENGTH: int = int(os.getenv("MAX_QUESTION_LENGTH", "2000"))

# ⚠️  INJECTION GUARD — DO NOT MODIFY WITHOUT MANUAL REVIEW ⚠️
# This regex detects prompt-injection attempts that try to override the
# system prompt or hijack the model's behaviour.
INJECTION = re.compile(
    r"(ignore\s+(all\s+)?previous|forget\s+(all\s+)?instructions?|"
    r"you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are)|"
    r"disregard\s+(all\s+)?previous|override\s+(system|prompt)|"
    r"system\s*:\s*you)",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# FastMCP application
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="Mentor AI",
    description=(
        "Routes spoken questions to one of ten expert personas and answers "
        "in short, voice-ready sentences using Amazon Bedrock."
    ),
)

# ─────────────────────────────────────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def list_personas() -> dict:
    """Return all available persona names and their titles."""
    from personas import PERSONA_MAP  # local import to avoid circular refs

    return {
        "personas": [
            {"name": p.name, "title": p.title, "description": p.description}
            for p in PERSONA_MAP.values()
        ]
    }


@mcp.tool()
def route_question(question: str) -> dict:
    """
    Return which persona would handle *question* and why.

    Args:
        question: The user's question or topic.

    Returns:
        A dict with keys: persona (name), title, description.
    """
    if not isinstance(question, str) or not question.strip():
        return {"error": "Question must be a non-empty string."}
    if len(question.strip()) > MAX_QUESTION_LENGTH:
        return {
            "error": f"Question must be {MAX_QUESTION_LENGTH} characters or fewer."
        }

    persona = route(question.strip())
    logger.info("route_question: '%s' -> %s", question[:80], persona.name)
    return {
        "persona": persona.name,
        "title": persona.title,
        "description": persona.description,
    }


@mcp.tool()
def ask_mentor(question: str, persona_name: str = "") -> dict:
    """
    Route *question* to the best persona and return an answer from Bedrock.

    ⚠️  Prompt-injection guard is active — inputs matching the INJECTION
    pattern are rejected before any Bedrock call.

    Args:
        question:     The user's question.
        persona_name: Optional override — force a specific persona by name.

    Returns:
        A dict with keys: persona, answer.
    """
    if not isinstance(question, str) or not question.strip():
        return {"error": "Question must be a non-empty string."}

    q = question.strip()
    if len(q) > MAX_QUESTION_LENGTH:
        return {
            "error": f"Question must be {MAX_QUESTION_LENGTH} characters or fewer."
        }
    if persona_name is not None and not isinstance(persona_name, str):
        return {"error": "Persona must be a string when provided."}

    # ── Injection guard (DO NOT MODIFY) ───────────────────────────────────────
    if INJECTION.search(question):
        logger.warning("Injection attempt blocked: '%s'", question[:120])
        raise ValueError(
            "Input rejected: potential prompt-injection detected. "
            "Please ask a genuine question."
        )
    # ─────────────────────────────────────────────────────────────────────────

    if persona_name:
        persona = get_persona(persona_name.strip())
        if persona is None:
            return {
                "error": f"Unknown persona '{persona_name}'. "
                f"Valid names: {', '.join(all_persona_names())}."
            }
    else:
        persona = route(q)

    logger.info("ask_mentor: persona=%s question='%s'", persona.name, q[:80])

    answer = ask_bedrock(
        question=q,
        system_prompt=persona.system_prompt,
        persona_name=persona.name,
        disclaimer=persona.disclaimer,
    )

    return {"persona": persona.name, "answer": answer}


# ─────────────────────────────────────────────────────────────────────────────
# Plain HTTP custom routes  (registered via @mcp.custom_route decorator)
# ─────────────────────────────────────────────────────────────────────────────


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """GET /health — liveness probe."""
    return JSONResponse(
        {
            "status": "ok",
            "version": VERSION,
            "mode": "offline" if is_offline() else "live",
        }
    )


@mcp.custom_route("/api/ask", methods=["POST"])
async def api_ask(request: Request) -> JSONResponse:
    """
    POST /api/ask — REST wrapper around ask_mentor.

    Request body (JSON):
        { "question": "...", "persona": "..." }   (persona is optional)

    Response:
        { "persona": "...", "answer": "..." }
    """
    # ── Rate limit ────────────────────────────────────────────────────────────
    ip = get_client_ip(request)
    try:
        check_rate_limit(ip)
    except RateLimitExceeded as exc:
        logger.warning("Rate limit hit: %s", exc)
        return JSONResponse(
            {"error": "Rate limit exceeded. Please wait before trying again."},
            status_code=429,
        )

    # ── Parse and validate body ───────────────────────────────────────────────
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    if not isinstance(body, dict):
        return JSONResponse(
            {"error": "JSON body must be an object."}, status_code=400
        )

    raw_question = body.get("question")
    if raw_question is None:
        return JSONResponse(
            {"error": "Field 'question' is required."}, status_code=400
        )
    if not isinstance(raw_question, str):
        return JSONResponse(
            {"error": "Field 'question' must be a string."}, status_code=400
        )

    raw_persona = body.get("persona", "")
    if not isinstance(raw_persona, str):
        return JSONResponse(
            {"error": "Field 'persona' must be a string."}, status_code=400
        )

    question = raw_question.strip()
    persona_name = raw_persona.strip()

    if not question:
        return JSONResponse({"error": "Field 'question' is required."}, status_code=400)
    if len(question) > MAX_QUESTION_LENGTH:
        return JSONResponse(
            {
                "error": (
                    f"Field 'question' must be {MAX_QUESTION_LENGTH} "
                    "characters or fewer."
                )
            },
            status_code=413,
        )

    logger.info(
        "POST /api/ask ip=%s persona=%s question='%s'",
        ip,
        persona_name or "auto",
        question[:80],
    )

    # ── Delegate to ask_mentor logic ──────────────────────────────────────────
    try:
        result = ask_mentor(question=question, persona_name=persona_name)
    except ValueError as exc:
        # Injection guard triggered
        return JSONResponse({"error": str(exc)}, status_code=400)

    if "error" in result:
        return JSONResponse(result, status_code=400)

    return JSONResponse(result)


# ─────────────────────────────────────────────────────────────────────────────
# Build the ASGI app
# ─────────────────────────────────────────────────────────────────────────────

# Build the Streamable HTTP ASGI app (auto-mounts /mcp; includes custom routes)
_base_app = mcp.streamable_http_app()


class MCPRateLimitMiddleware:
    """Apply the same per-IP limit to MCP requests as to the REST API."""

    def __init__(self, wrapped_app):
        self.wrapped_app = wrapped_app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").rstrip("/")
        if scope.get("type") == "http" and path == "/mcp":
            request = Request(scope, receive)
            try:
                check_rate_limit(get_client_ip(request))
            except RateLimitExceeded:
                response = JSONResponse(
                    {"error": "Rate limit exceeded. Please wait before trying again."},
                    status_code=429,
                )
                await response(scope, receive, send)
                return

            # Starlette's Mount normally redirects /mcp to /mcp/. Rewrite the
            # canonical documented URL so MCP clients do not need redirect
            # support during session initialization.
            if scope.get("path") == "/mcp":
                scope = dict(scope)
                scope["path"] = "/mcp/"
                scope["raw_path"] = b"/mcp/"
        await self.wrapped_app(scope, receive, send)


# Wrap the MCP transport before CORS so public MCP access cannot bypass the
# request limit applied to the REST endpoint.
_rate_limited_app = MCPRateLimitMiddleware(_base_app)

# Wrap with CORS middleware
app = CORSMiddleware(
    _rate_limited_app,
    allow_origins=[CORS_ORIGIN] if CORS_ORIGIN != "*" else ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Mcp-Session-Id"],
    allow_credentials=False,
)

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting Mentor AI server v%s on %s:%s (mode=%s, model=%s)",
        VERSION,
        HOST,
        PORT,
        "offline" if is_offline() else "live",
        os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
    )
    logger.info("MCP endpoint:  http://%s:%s/mcp", HOST, PORT)
    logger.info("REST API:      http://%s:%s/api/ask", HOST, PORT)
    logger.info("Health:        http://%s:%s/health", HOST, PORT)

    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        log_level=LOG_LEVEL.lower(),
        access_log=True,
    )

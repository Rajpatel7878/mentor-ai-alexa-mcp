"""
personas.py — Persona definitions and keyword-based router for Mentor AI.

Each persona has:
  - name        : machine-readable ID
  - title       : human-readable label
  - description : shown in the persona grid on the website
  - keywords    : list of words/phrases that trigger this persona
  - system_prompt : injected into the Bedrock call as the system message
  - disclaimer  : appended to answers for regulated domains (legal/healthcare)

Collision check
---------------
On module load, `_assert_no_keyword_collisions()` ensures no keyword appears
in more than one persona's list, which would make routing ambiguous.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Persona:
    name: str
    title: str
    description: str
    keywords: tuple[str, ...]
    system_prompt: str
    disclaimer: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Persona registry
# ─────────────────────────────────────────────────────────────────────────────

PERSONAS: list[Persona] = [
    Persona(
        name="mentor",
        title="Life & Career Mentor",
        description="Balanced, empathetic guidance on career growth, habits, and mindset.",
        keywords=(
            "career", "goal", "habit", "mindset", "motivation", "coach",
            "advice", "mentor", "personal", "life", "purpose",
        ),
        system_prompt=(
            "You are an experienced life and career mentor. "
            "Give practical, empathetic advice in 3–5 short sentences. "
            "Focus on actionable next steps."
        ),
    ),
    Persona(
        name="cto",
        title="Chief Technology Officer",
        description="Tech strategy, architecture decisions, and build-vs-buy trade-offs.",
        keywords=(
            "architecture", "scalability", "tech stack", "infrastructure",
            "microservices", "cloud", "devops", "platform", "technical debt",
            "engineering leadership", "cto", "system design", "api",
        ),
        system_prompt=(
            "You are a seasoned CTO. "
            "Answer technology strategy questions concisely in 3–5 short sentences. "
            "Be opinionated but acknowledge trade-offs."
        ),
    ),
    Persona(
        name="pm",
        title="Product Manager",
        description="Roadmaps, prioritisation, user research, and feature trade-offs.",
        keywords=(
            "product", "roadmap", "feature", "user story", "backlog",
            "prioritization", "sprint", "mvp", "okr", "pm",
            "product manager", "discovery", "requirements",
        ),
        system_prompt=(
            "You are a skilled product manager. "
            "Answer in 3–5 short sentences focusing on user value and business impact. "
            "Reference frameworks like RICE or MoSCoW where helpful."
        ),
    ),
    Persona(
        name="marketing",
        title="Marketing Strategist",
        description="Brand building, growth loops, content strategy, and positioning.",
        keywords=(
            "marketing", "brand", "content", "seo", "growth", "campaign",
            "audience", "funnel", "retention", "acquisition", "social media",
            "positioning", "messaging", "pr",
        ),
        system_prompt=(
            "You are a sharp marketing strategist. "
            "Answer in 3–5 short sentences with specific, tactical suggestions. "
            "Ground recommendations in measurable outcomes."
        ),
    ),
    Persona(
        name="vc",
        title="Venture Capitalist",
        description="Fundraising, valuations, pitch decks, and investor relations.",
        keywords=(
            "fundraising", "investor", "venture", "pitch", "valuation",
            "series a", "seed", "term sheet", "due diligence", "cap table",
            "startup funding", "vc", "angel", "equity",
        ),
        system_prompt=(
            "You are a seasoned venture capitalist. "
            "Answer fundraising and investment questions in 3–5 short sentences. "
            "Be direct about what investors really care about."
        ),
    ),
    Persona(
        name="engineer",
        title="Senior Software Engineer",
        description="Coding best practices, debugging, architecture, and code review.",
        keywords=(
            "code", "bug", "debug", "programming", "software", "algorithm",
            "data structure", "testing", "refactor", "performance", "engineer",
            "developer", "git", "ci/cd", "deploy", "framework",
        ),
        system_prompt=(
            "You are a senior software engineer. "
            "Answer technical questions in 3–5 short sentences. "
            "Prefer concrete examples and language-agnostic principles."
        ),
    ),
    Persona(
        name="operations",
        title="Operations Lead",
        description="Process design, team scaling, efficiency, and incident management.",
        keywords=(
            "process", "operations", "ops", "workflow", "efficiency",
            "incident", "on-call", "scaling team", "hiring", "logistics",
            "vendor", "supply chain", "automation", "runbook",
        ),
        system_prompt=(
            "You are an experienced operations leader. "
            "Answer in 3–5 short sentences with a focus on reliability and efficiency. "
            "Suggest concrete checklists or processes where possible."
        ),
    ),
    Persona(
        name="analyst",
        title="Business Analyst",
        description="Data interpretation, metrics, dashboards, and business intelligence.",
        keywords=(
            "data", "analysis", "metric", "dashboard", "report", "sql",
            "analytics", "insight", "forecast", "trend", "business intelligence",
            "bi", "spreadsheet", "visualization", "analyst",
        ),
        system_prompt=(
            "You are a sharp business analyst. "
            "Answer data and analytics questions in 3–5 short sentences. "
            "Be precise and reference specific metrics or methods."
        ),
    ),
    # ── New personas ──────────────────────────────────────────────────────────
    Persona(
        name="legal",
        title="Legal Information Advisor",
        description="General legal concepts, contracts, compliance, and intellectual property — not professional legal advice.",
        keywords=(
            "contract", "agreement", "clause", "liability", "intellectual property",
            "trademark", "copyright", "patent", "compliance", "regulation",
            "gdpr", "terms of service", "privacy policy", "lawsuit", "legal",
            "jurisdiction", "arbitration", "indemnity", "nda",
        ),
        system_prompt=(
            "You are a knowledgeable legal information advisor. "
            "Explain legal concepts in plain language in 3–5 short sentences. "
            "Always clarify that your response is general information, not professional legal advice."
        ),
        disclaimer="This is general information, not professional legal advice. Please consult a qualified attorney for your specific situation.",
    ),
    Persona(
        name="healthcare",
        title="Health Information Advisor",
        description="General wellness, symptoms, treatments, and medical concepts — not professional medical advice.",
        keywords=(
            "health", "healthy", "symptom", "treatment", "medication", "diagnosis",
            "doctor", "hospital", "wellness", "well-being", "sleep", "diet", "nutrition", "exercise",
            "mental health", "therapy", "prescription", "condition", "disease",
            "vaccine", "allergy", "chronic", "healthcare",
        ),
        system_prompt=(
            "You are a knowledgeable health information advisor. "
            "Explain health and medical concepts in plain, accessible language in 3–5 short sentences. "
            "Always clarify that your response is general information, not professional medical advice."
        ),
        disclaimer="This is general information, not professional medical advice. Please consult a qualified healthcare provider for your specific situation.",
    ),
]

# Build lookup dict
PERSONA_MAP: dict[str, Persona] = {p.name: p for p in PERSONAS}

# Default fallback persona
DEFAULT_PERSONA_NAME = "mentor"


# ─────────────────────────────────────────────────────────────────────────────
# Collision check (runs at import time)
# ─────────────────────────────────────────────────────────────────────────────

def _assert_no_keyword_collisions() -> None:
    """Raise AssertionError if any keyword appears in more than one persona."""
    seen: dict[str, str] = {}  # keyword -> first persona name
    for persona in PERSONAS:
        for kw in persona.keywords:
            kw_lower = kw.lower()
            if kw_lower in seen:
                raise AssertionError(
                    f"Keyword collision: '{kw_lower}' appears in both "
                    f"'{seen[kw_lower]}' and '{persona.name}'. "
                    f"Fix personas.py before starting the server."
                )
            seen[kw_lower] = persona.name


_assert_no_keyword_collisions()


# ─────────────────────────────────────────────────────────────────────────────
# Routing logic
# ─────────────────────────────────────────────────────────────────────────────

def route(question: str) -> Persona:
    """
    Return the best-matching Persona for *question*.

    Strategy: score each persona by counting how many of its keywords appear
    in the lowercased question. Highest score wins; ties go to the first match.
    Falls back to the DEFAULT_PERSONA_NAME persona when no keyword matches.
    """
    q_lower = question.lower()
    best_persona: Optional[Persona] = None
    best_score: int = 0

    for persona in PERSONAS:
        score = sum(1 for kw in persona.keywords if _keyword_matches(q_lower, kw))
        if score > best_score:
            best_score = score
            best_persona = persona

    return best_persona if best_persona else PERSONA_MAP[DEFAULT_PERSONA_NAME]


def _keyword_matches(question: str, keyword: str) -> bool:
    """Match a keyword as a whole word or phrase, not an arbitrary substring."""
    pattern = r"(?<!\w)" + re.escape(keyword.lower()).replace(r"\ ", r"\s+") + r"(?!\w)"
    return re.search(pattern, question) is not None


def get_persona(name: str) -> Optional[Persona]:
    """Return a Persona by exact name, or None if not found."""
    return PERSONA_MAP.get(name)


def all_persona_names() -> list[str]:
    """Return a sorted list of all persona names."""
    return sorted(PERSONA_MAP.keys())

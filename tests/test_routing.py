"""
test_routing.py — Tests for the persona keyword router and collision check.

Run: pytest tests/test_routing.py -v
"""

import sys
import os

# Allow importing server modules without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import pytest
from personas import route, get_persona, all_persona_names, PERSONAS, PERSONA_MAP


# ─────────────────────────────────────────────────────────────────────────────
# Collision check (already runs at import; test confirms no assertion raised)
# ─────────────────────────────────────────────────────────────────────────────

def test_no_keyword_collisions():
    """Persona keyword lists must have no overlapping keywords."""
    seen: dict[str, str] = {}
    for persona in PERSONAS:
        for kw in persona.keywords:
            kw_lower = kw.lower()
            assert kw_lower not in seen, (
                f"Keyword '{kw_lower}' is duplicated in '{seen[kw_lower]}' "
                f"and '{persona.name}'."
            )
            seen[kw_lower] = persona.name


# ─────────────────────────────────────────────────────────────────────────────
# Ten personas are registered
# ─────────────────────────────────────────────────────────────────────────────

def test_all_ten_personas_present():
    names = all_persona_names()
    expected = {
        "mentor", "cto", "pm", "marketing", "vc",
        "engineer", "operations", "analyst", "legal", "healthcare",
    }
    assert expected == set(names), f"Unexpected personas: {set(names) ^ expected}"


# ─────────────────────────────────────────────────────────────────────────────
# Routing — happy path
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("question,expected_persona", [
    ("How do I raise a Series A?",                   "vc"),
    ("What is the best tech stack for a startup?",   "cto"),
    ("How do I prioritise my product backlog?",      "pm"),
    ("How do I grow my brand on social media?",      "marketing"),
    ("What is the best algorithm for sorting?",      "engineer"),
    ("How should I write a runbook for incidents?",  "operations"),
    ("What KPIs should I track in my dashboard?",    "analyst"),
    ("What should I know before signing an NDA?",    "legal"),
    ("What does a healthy sleep routine look like?", "healthcare"),
    ("How do I set career goals and find purpose?",  "mentor"),
    ("What is the capital of France?",              "mentor"),
    ("How do I approach a difficult problem?",     "mentor"),
    ("Tell me about my biography.",                 "mentor"),
])
def test_route_question(question, expected_persona):
    persona = route(question)
    assert persona.name == expected_persona, (
        f"Expected '{expected_persona}', got '{persona.name}' for: '{question}'"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routing — fallback to default persona
# ─────────────────────────────────────────────────────────────────────────────

def test_route_unknown_question_falls_back_to_mentor():
    """A question with no keyword matches should fall back to 'mentor'."""
    persona = route("xyzzy frobnicator blurble quux")
    assert persona.name == "mentor"


# ─────────────────────────────────────────────────────────────────────────────
# get_persona — by name
# ─────────────────────────────────────────────────────────────────────────────

def test_get_persona_valid():
    for name in all_persona_names():
        p = get_persona(name)
        assert p is not None
        assert p.name == name


def test_get_persona_invalid():
    assert get_persona("unicorn") is None


# ─────────────────────────────────────────────────────────────────────────────
# New personas — legal and healthcare have disclaimers
# ─────────────────────────────────────────────────────────────────────────────

def test_legal_persona_has_disclaimer():
    legal = get_persona("legal")
    assert legal is not None
    assert "not professional" in legal.disclaimer.lower()


def test_healthcare_persona_has_disclaimer():
    hc = get_persona("healthcare")
    assert hc is not None
    assert "not professional" in hc.disclaimer.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Every persona has required fields
# ─────────────────────────────────────────────────────────────────────────────

def test_all_personas_have_required_fields():
    for persona in PERSONAS:
        assert persona.name,         f"Persona missing 'name'"
        assert persona.title,        f"Persona '{persona.name}' missing 'title'"
        assert persona.description,  f"Persona '{persona.name}' missing 'description'"
        assert persona.keywords,     f"Persona '{persona.name}' has no keywords"
        assert persona.system_prompt, f"Persona '{persona.name}' missing system_prompt"

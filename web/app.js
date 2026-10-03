/**
 * app.js — Mentor AI demo website logic
 *
 * Features
 * ─────────
 * - Calls POST /api/ask on the local (or configurable) server.
 * - Uses Web Speech API (SpeechRecognition) for mic input where available.
 * - Uses Web Speech API (speechSynthesis) to read answers aloud.
 * - Clicking a persona card pre-fills the question box with a sample question
 *   and forces that persona in the API call.
 * - API base URL is user-configurable in the UI (for pointing at App Runner).
 */

/* ── Persona data (mirrors server/personas.py) ───────────────────────── */
const PERSONAS = [
  { name: "mentor",     title: "Life & Career Mentor",       emoji: "🧑‍🏫", sample: "How do I set better career goals?" },
  { name: "cto",        title: "Chief Technology Officer",    emoji: "🏗️",  sample: "What tech stack should a startup use in 2025?" },
  { name: "pm",         title: "Product Manager",             emoji: "📋",  sample: "How do I prioritise my product backlog?" },
  { name: "marketing",  title: "Marketing Strategist",        emoji: "📣",  sample: "How do I build brand awareness with a small budget?" },
  { name: "vc",         title: "Venture Capitalist",          emoji: "💼",  sample: "How do I raise a Series A?" },
  { name: "engineer",   title: "Senior Software Engineer",    emoji: "👩‍💻",  sample: "What's the best way to reduce technical debt?" },
  { name: "operations", title: "Operations Lead",             emoji: "⚙️",  sample: "How do I write a good incident runbook?" },
  { name: "analyst",    title: "Business Analyst",            emoji: "📊",  sample: "How do I choose the right KPIs for my dashboard?" },
  { name: "legal",      title: "Legal Information Advisor",   emoji: "⚖️",  sample: "What should I know before signing an NDA?" },
  { name: "healthcare", title: "Health Information Advisor",  emoji: "🏥",  sample: "What does a healthy sleep routine look like?" },
];

/* ── DOM refs ─────────────────────────────────────────────────────────── */
const questionInput  = document.getElementById("question-input");
const micBtn         = document.getElementById("mic-btn");
const askBtn         = document.getElementById("ask-btn");
const resultBox      = document.getElementById("result-box");
const resultPersona  = document.getElementById("result-persona");
const resultAnswer   = document.getElementById("result-answer");
const statusLine     = document.getElementById("status-line");
const errorBox       = document.getElementById("error-box");
const personaGrid    = document.getElementById("persona-grid");
const apiBaseInput   = document.getElementById("api-base-input");

/* ── State ────────────────────────────────────────────────────────────── */
let forcedPersona = "";   // set when user clicks a persona card
let recognition   = null;
let isListening   = false;

/* ── Build persona grid ───────────────────────────────────────────────── */
function buildPersonaGrid() {
  PERSONAS.forEach((p) => {
    const card = document.createElement("div");
    card.className = "persona-card";
    card.setAttribute("data-persona", p.name);
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", `Ask the ${p.title}`);
    card.innerHTML = `
      <div class="persona-emoji">${p.emoji}</div>
      <div class="persona-name">${p.name}</div>
      <div class="persona-title">${p.title}</div>
    `;
    card.addEventListener("click", () => selectPersona(p));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") selectPersona(p);
    });
    personaGrid.appendChild(card);
  });
}

function selectPersona(p) {
  forcedPersona = p.name;
  questionInput.value = p.sample;
  questionInput.focus();
  // Highlight selected card
  document.querySelectorAll(".persona-card").forEach((c) => {
    c.style.borderColor = c.dataset.persona === p.name ? "var(--primary)" : "";
    c.style.boxShadow   = c.dataset.persona === p.name
      ? "0 0 0 3px color-mix(in srgb, var(--primary) 20%, transparent)" : "";
  });
  document.getElementById("demo").scrollIntoView({ behavior: "smooth" });
}

/* ── Speech Recognition ───────────────────────────────────────────────── */
function initSpeechRecognition() {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    micBtn.disabled = true;
    micBtn.title = "Speech recognition not supported in this browser.";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = "en-US";

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    questionInput.value = transcript;
    forcedPersona = ""; // reset forced persona on new voice input
  };

  recognition.onend = () => {
    isListening = false;
    micBtn.classList.remove("listening");
    micBtn.textContent = "🎤";
    micBtn.setAttribute("aria-label", "Start voice input");
    questionInput.placeholder = "e.g. How do I raise a Series A?";
  };

  recognition.onerror = (event) => {
    console.warn("SpeechRecognition error:", event.error);
    isListening = false;
    micBtn.classList.remove("listening");
    micBtn.textContent = "🎤";
    questionInput.placeholder = "e.g. How do I raise a Series A?";
  };

  micBtn.addEventListener("click", () => {
    if (isListening) {
      recognition.stop();
    } else {
      isListening = true;
      micBtn.classList.add("listening");
      micBtn.textContent = "⏹";
      micBtn.setAttribute("aria-label", "Stop voice input");
      questionInput.placeholder = "Listening…";
      recognition.start();
    }
  });
}

/* ── Text-to-speech ───────────────────────────────────────────────────── */
function speak(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
}

/* ── API call ─────────────────────────────────────────────────────────── */
async function askMentor() {
  const question = questionInput.value.trim();
  if (!question) {
    questionInput.focus();
    return;
  }

  const apiBase = (apiBaseInput.value || "http://localhost:8000").replace(/\/$/, "");

  // UI — loading state
  hideResults();
  askBtn.disabled = true;
  askBtn.innerHTML = '<span class="spinner"></span> Asking…';

  try {
    const body = { question };
    if (forcedPersona) body.persona = forcedPersona;

    const res = await fetch(`${apiBase}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();

    if (!res.ok || data.error) {
      showError(data.error || `Server returned ${res.status}`);
      return;
    }

    showResult(data.persona, data.answer);
    speak(data.answer);
  } catch (err) {
    showError(
      `Could not reach the server at ${apiBase}. ` +
      "Make sure it is running: python server/server.py"
    );
    console.error(err);
  } finally {
    askBtn.disabled = false;
    askBtn.innerHTML = "Ask →";
  }
}

/* ── UI helpers ───────────────────────────────────────────────────────── */
function showResult(personaName, answer) {
  const personaObj = PERSONAS.find((p) => p.name === personaName);
  const emoji = personaObj ? personaObj.emoji : "🤖";

  resultPersona.innerHTML = `${emoji} ${personaName.toUpperCase()}`;
  resultAnswer.textContent = answer;
  statusLine.textContent = window.speechSynthesis
    ? "Reading answer aloud…"
    : "Speech synthesis not available in this browser.";

  resultBox.classList.add("visible");
  errorBox.classList.remove("visible");
}

function showError(msg) {
  errorBox.textContent = "⚠ " + msg;
  errorBox.classList.add("visible");
  resultBox.classList.remove("visible");
}

function hideResults() {
  resultBox.classList.remove("visible");
  errorBox.classList.remove("visible");
}

/* ── Event listeners ──────────────────────────────────────────────────── */
askBtn.addEventListener("click", askMentor);

questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    askMentor();
  }
});

// Reset forced persona whenever the user edits the pre-filled question.
// (selectPersona assigns .value programmatically, so it does not trigger this
// input event and the forced persona remains active until the user types.)
questionInput.addEventListener("input", () => {
  forcedPersona = "";
  document.querySelectorAll(".persona-card").forEach((c) => {
    c.style.borderColor = "";
    c.style.boxShadow   = "";
  });
});

/* ── Init ─────────────────────────────────────────────────────────────── */
buildPersonaGrid();
initSpeechRecognition();

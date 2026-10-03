# Mentor AI for Alexa+ 🎙️

> A self-hosted **Model Context Protocol (MCP)** server that routes spoken questions to expert AI personas and answers in short, voice-ready sentences — powered by **Amazon Bedrock**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-mentor--ai--alexa--mcp-blue?logo=github)](https://github.com/Rajpatel7878/mentor-ai-alexa-mcp)

**Repo:** [github.com/Rajpatel7878/mentor-ai-alexa-mcp](https://github.com/Rajpatel7878/mentor-ai-alexa-mcp)

---

## Hackathon Entry

| Field | Value |
|---|---|
| **Event** | Amazon Developer Hackathon |
| **Track** | **Alexa+** |
| **Mini challenge 1** | **AWS Builder** — self-hosted MCP server deployable to AWS (App Runner + ECR + Bedrock) |
| **Mini challenge 2** | **Open Source** — MIT-licensed, public GitHub repo, documented for community reuse |
| **MCP endpoint** | `https://<your-app-runner-url>/mcp` (Streamable HTTP, spec 2025-11-25+) |

### What I built during the hackathon window

> _✏️ Placeholder — complete this subsection yourself before submitting:_
>
> - _Which parts did you build during the official hackathon window (dates)?_
> - _What was built before vs. during the window?_
> - _Any features added in the final days?_
> - _Link a short demo video or screenshots here if you have them._

---

## Hackathon Tracks

| Track | Mini Challenge | How this project qualifies |
|---|---|---|
| **Alexa+** | AWS Builder | Self-hosted MCP server (Streamable HTTP) designed to connect to Alexa+ as a custom skill back-end |
| **Alexa+** | Open Source | Full source on GitHub, MIT license, documented for community reuse |

---

## What It Does

**Mentor AI** listens to your question, picks the best expert from ten personas, and replies in short sentences optimised for speech:

| Persona | Expertise |
|---|---|
| `mentor` | General life/career guidance |
| `cto` | Technology strategy |
| `pm` | Product management |
| `marketing` | Brand & growth |
| `vc` | Venture capital & fundraising |
| `engineer` | Software engineering |
| `operations` | Ops, process & scaling |
| `analyst` | Data & business analysis |
| `legal` | Legal information _(not professional advice)_ |
| `healthcare` | Health information _(not professional advice)_ |

---

## Project Structure

```
mentor-ai-alexa/
├── server/               # MCP server (FastMCP + Starlette)
│   ├── server.py         # Main entry point — tools, /api/ask, /health
│   ├── personas.py       # All 10 persona definitions & keyword router
│   ├── bedrock.py        # Amazon Bedrock client + offline fallback
│   ├── limiter.py        # Per-IP in-process rate limiter
│   ├── requirements.txt  # Pinned Python dependencies
│   └── Dockerfile        # Container build
├── web/                  # Demo website (plain HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── docs/
│   ├── ARCHITECTURE.md   # System diagram (Mermaid)
│   ├── DEPLOY.md         # AWS App Runner step-by-step
│   ├── FRICTION_LOG.md   # Hackathon friction log template
│   └── FEEDBACK.md       # Per-tool product feedback template
├── tests/                # pytest suite
│   ├── test_routing.py
│   ├── test_injection.py
│   └── test_api.py
├── .env.example          # Environment variable template
├── .gitignore
├── LICENSE               # MIT
└── README.md
```

---

## Quick Start

### 1. Clone & configure

```bash
# Clone or download this repository, then enter its directory.
cd mentor-ai-alexa
cp .env.example .env
# Edit .env — add AWS credentials or configure an AWS role for live mode.
# Leave credentials blank for offline mode.
```

### 2. Install dependencies

Run this from the project root:

```bash
pip install -r server/requirements.txt
```

### 3. Run the server

```bash
python server/server.py
# → MCP endpoint:   http://localhost:8000/mcp
# → REST API:       http://localhost:8000/api/ask
# → Health check:   http://localhost:8000/health
```

### 4. Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

### 5. Open the website

Open `web/index.html` in your browser. The demo box calls `http://localhost:8000/api/ask` by default.

---

## API Reference

### `POST /api/ask`

```json
// Request
{ "question": "How do I raise a Series A?" }

// Response
{
  "persona": "vc",
  "answer": "Focus on product-market fit first. Investors want traction, not just ideas. Prepare a clear pitch deck. Know your metrics cold."
}
```

### `GET /health`

```json
{ "status": "ok", "version": "1.0.0" }
```

### MCP Tools (via `/mcp`)

| Tool | Description |
|---|---|
| `list_personas` | Returns all available persona names |
| `route_question` | Returns which persona would handle a question |
| `ask_mentor` | Full pipeline — routes + calls Bedrock + returns answer |

---

## Run Tests

```bash
cd server
pip install pytest httpx
pytest ../tests/ -v
```

---

## Docker

```bash
cd server
docker build -t mentor-ai .
docker run -p 8000:8000 --env-file ../.env mentor-ai
```

---

## Deploy to AWS

See [docs/DEPLOY.md](docs/DEPLOY.md) for a complete step-by-step guide using **AWS App Runner** (ECR push → App Runner service → public HTTPS URL).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | _(blank unless using keys)_ | AWS credential; an IAM role/profile also works |
| `AWS_SECRET_ACCESS_KEY` | _(blank unless using keys)_ | AWS credential; an IAM role/profile also works |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` | Model to invoke |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |
| `CORS_ORIGIN` | `*` | Allowed CORS origin; restrict this in production |
| `RATE_LIMIT_REQUESTS` | `10` | Max requests per window per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window |
| `TRUST_PROXY_HEADERS` | `false` | Trust sanitized `X-Forwarded-For` headers |
| `MAX_QUESTION_LENGTH` | `2000` | Maximum question size in characters |
| `BEDROCK_OFFLINE` | `auto` | Force `true` for offline mode, or auto-detect credentials |
| `LOG_LEVEL` | `INFO` | Python log level |

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full Mermaid diagram.

```
Alexa+ ──► MCP Server (/mcp) ──► Persona Router ──► Amazon Bedrock
                │
                └──► REST API (/api/ask) ──► Web Demo
```

---

## Security Notes

- **Prompt-injection guard**: `ask_mentor` rejects inputs matching a `INJECTION` regex pattern before any Bedrock call.
- **Rate limiting**: 10 req/60 s per IP on both REST and MCP endpoints (in-process; stateless across restarts).
- **No secrets in code**: credentials use environment variables or the runtime's IAM role.
- **Production hardening**: restrict CORS and add authentication/API gateway controls before exposing a public Bedrock-backed service.

---

## License

[MIT](LICENSE) — free to use, fork, and build upon.

# GitHub Setup — Mentor AI for Alexa+

> **Repo:** `mentor-ai-alexa-mcp`
> Replace `YOUR_USERNAME` with your GitHub username everywhere below
> (your username appears to be `Rajpatel7878` — swap it in as needed).
>
> ⚠️ Create the remote repository **empty** — do **not** initialize it with a
> README, .gitignore, or license on GitHub, otherwise the first push will be
> rejected as non-fast-forward.

---

## Step 1 — Create the empty remote repository

**Option A — GitHub website:**

1. Go to <https://github.com/new>
2. Repository name: `mentor-ai-alexa-mcp`
3. Select **Private** (recommended — see Step 4) or **Public**
4. **Leave unchecked:** `Add a README file`, `Add .gitignore`, `Choose a license`
5. Click **Create repository**

**Option B — GitHub CLI (`gh`):**

```bash
gh repo create YOUR_USERNAME/mentor-ai-alexa-mcp --private --description "Mentor AI for Alexa+ — self-hosted MCP server with 10 expert personas on Amazon Bedrock"
```

---

## Step 2 — Connect your local repo to the remote

Run from the project root (after the initial local commit exists):

```bash
git remote add origin https://github.com/YOUR_USERNAME/mentor-ai-alexa-mcp.git
git branch -M main
git remote -v          # verify: origin points to your repo
```

---

## Step 3 — Push the first commit

```bash
git push -u origin main
```

If GitHub asks for credentials, use one of:

- **GitHub CLI:** `gh auth login` (easiest), or
- **HTTPS with a Personal Access Token:** create a fine-grated PAT at
  <https://github.com/settings/tokens> with `repo` scope, then use it as the
  password when git prompts. **Never commit the token** — store it in a
  credential helper, not in `.env` or any tracked file.

---

## Step 4 — Add Amazon reviewers as collaborators (private repo)

1. Open your repo on GitHub: `https://github.com/YOUR_USERNAME/mentor-ai-alexa-mcp`
2. Click **Settings** (top tab, not your account settings)
3. In the left sidebar, click **Collaborators** (under "Access")
4. Click **Add people**
5. Type the reviewer's GitHub username or email (provided by the hackathon
   rules / Amazon organizers) and select it
6. Click **Add collaborator** to send the invitation
7. The reviewer must **accept** the invitation before they can see the repo
8. Leave access at **Read** unless the hackathon rules say otherwise

> Prefer teams? **Settings → Teams → New team**, add members, then
> **Settings → Collaborators → Add teams**.

---

## Step 5 — Verify everything landed correctly

```bash
git status            # clean, on branch main
git log --oneline     # should show your initial commit
git ls-files | head   # tracked files visible on the remote after push
```

Also confirm on GitHub that `.env` is **absent** from the file list — only
`.env.example` should be there.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `remote contains work that you do not have` | The repo was created **with** a README — delete the remote repo and recreate it empty, or run `git pull --rebase origin main` first |
| `rejected: non-fast-forward` | Same cause as above — the remote must be empty on first push |
| Push asks for a password and rejects it | GitHub no longer accepts account passwords over HTTPS — use a PAT or `gh auth login` |
| Forgot the remote URL | `git remote -v` then `git remote set-url origin https://github.com/YOUR_USERNAME/mentor-ai-alexa-mcp.git` |

---

_Last updated: 2026-10-03_

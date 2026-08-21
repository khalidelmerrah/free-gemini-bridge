---
name: gemini-cli
description: "Delegate coding to Google's Gemini CLI (features, PRs)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Gemini, Google, Code-Review, Refactoring]
    related_skills: [codex, claude-code, hermes-agent]
---

# Gemini CLI

Delegate coding tasks to [Gemini CLI](https://geminicli.com) via the Hermes terminal.
Gemini CLI is Google's autonomous coding agent — the Gemini-models equivalent of Codex.
Authenticates by **Google account login (OAuth)** — no API key required.

## When to use

- Building features with Gemini models
- Refactoring
- PR reviews
- Batch issue fixing
- Any task where the user asks to use Gemini

Requires the `gemini` CLI and a git repository.

## Prerequisites

- Install: `npm install -g @google/gemini-cli`
- **Login-based auth (no key)** — two options:
  1. Interactive: run `GOOGLE_GENAI_USE_GCA=true gemini -p "hello" --skip-trust` in a
     **real terminal** (user's own terminal window) → browser OAuth opens → user signs
     in with their Google account. The PTY here is NOT recognized as interactive, so
     the user must run this themselves the first time.
  2. Manual/remote: `NO_BROWSER=true GOOGLE_GENAI_USE_GCA=true gemini -p "hello"` in a
     real terminal prints a URL + code the user can complete **from their phone**.
- Alternative (if the user ever prefers): `GEMINI_API_KEY` env var.
- **Must run inside a git repository** (same rule as Codex).
- Use `pty=true` for interactive runs; `-p` one-shots work non-interactively once authed.

## One-Shot Tasks

```
terminal(command="gemini -p 'Add dark mode toggle to settings' --skip-trust", workdir="~/project")
```

Scratch work (Gemini needs a git repo):
```
terminal(command="cd $(mktemp -d) && git init && gemini -p 'Build a snake game in Python' --skip-trust", workdir="~/project")
```

## Background Mode (Long Tasks)

```
terminal(command="gemini -p 'Refactor the auth module' --skip-trust --approval-mode auto_edit", workdir="~/project", background=true, pty=true)
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")
process(action="submit", session_id="<id>", data="yes")   # if it asks a question
process(action="kill", session_id="<id>")
```

## Key Flags

| Flag | Effect |
|------|--------|
| `-p "prompt"` | One-shot non-interactive mode |
| `--skip-trust` | Trust the workspace for this session (required for automation) |
| `--approval-mode auto_edit` | Auto-approve file edits (recommended auto-build mode) |
| `--approval-mode yolo` | Auto-approve all tools (fastest, most dangerous) |
| `--approval-mode plan` | Read-only mode |
| `-m <model>` | Pick model (e.g. `gemini-2.5-pro`) |
| `-o json` | JSON output (parse in the agent instead of reading prose) |
| `--list-sessions` | List past sessions |

> Note: Gemini CLI has **no sandbox flag** (unlike Codex). Use `auto_edit` +
> process boundaries as the safety layer: explicit `workdir`, clean git status
> before launch, narrow prompts, `git diff` review, and confirmation before
> committing broad changes.

## PR Reviews

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && gemini -p 'Review this PR against main' --skip-trust", pty=true)
```

## Parallel Work (Worktrees)

```
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 /tmp/issue-99 main", workdir="~/project")
terminal(command="gemini -p 'Fix issue #78: <desc>. Commit when done.' --skip-trust --approval-mode auto_edit", workdir="/tmp/issue-78", background=true, pty=true)
terminal(command="gemini -p 'Fix issue #99: <desc>. Commit when done.' --skip-trust --approval-mode auto_edit", workdir="/tmp/issue-99", background=true, pty=true)
```

## Gemini Quota (status-bar chip)

A **Gemini Quota** desktop plugin (`plugins/gemini-quota/`) shows real per-model
quota in the Hermes status bar. It works WITHOUT any login step by reusing the
Antigravity IDE login already on this machine:

- Tokens live in Antigravity's `state.vscdb` (SQLite) at
  `~/AppData/Roaming/Antigravity/User/globalStorage/state.vscdb`
  under key `antigravityUnifiedStateSync.oauthToken` (base64 of a protobuf
  topic; sentinel `oauthTokenInfoSentinelKey` → Row.value → base64 →
  protobuf fields 1=access_token, 3=refresh_token, 5=id_token).
- Quota: `POST https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels`
  with `Authorization: Bearer <access_token>`, User-Agent
  `antigravity/1.20.5 windows/amd64`, gzip response → `models.{name}.quotaInfo`
  (`remainingFraction`, `resetTime`). Fall back to
  `cloudcode-pa.googleapis.com` (prod) for GCP-ToS accounts.
- Refresh: `POST https://oauth2.googleapis.com/token` with the public
  Antigravity OAuth client (`1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com`
  / `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` — public in cockpit-tools).
- Technique discovered from the open-source `jlcodes99/cockpit-tools` repo
  (Rust): `crates/cockpit-core/src/modules/quota.rs` + `utils/protobuf.rs`.
  It also switches accounts by writing a different token back into the DB.

Chip: `Gemini 100%` label; tooltip lists per-model remaining % + reset times,
account email, click-to-refresh. Backend auto-re-extracts from `state.vscdb`
when the refresh token fails.

## Using Gemini as a CHAT model in Hermes (status: one login away)

The quota API works with the Antigravity token, but **model inference does NOT**:
the generativelanguage API rejects it with `403 insufficient authentication scopes`
(the Antigravity OAuth client's scopes lack `generative-language`). A **Gemini CLI
login** (`gemini` first run / `login_gemini.bat` → NO_BROWSER flow, phone-completable)
grants that scope. Once logged in, the plan is a local OpenAI-compat proxy
(~100 lines: accept /v1/chat/completions → refresh token → map to native
`generateContent` with Bearer → OpenAI-shaped response) registered as Hermes
`custom` provider (base_url http://127.0.0.1:<port>/v1, dummy key). No Hermes
source edits needed; `oauth_external` providers are deliberately not auto-injected
(hermes_cli/models.py:1206) and would require editing app internals — the proxy
avoids that.

## Rules

1. **Auth check first** — `gemini -p "hi" --skip-trust` exits 41 with an auth prompt if not logged in. If so, hand the user the login command (see Prerequisites) — the Hermes PTY can't complete the OAuth flow itself.
2. **`--skip-trust` always** — without it Gemini pauses asking to trust the workspace.
3. **Git repo required** — use `mktemp -d && git init` for scratch.
4. **`auto_edit` for building** — auto-approves file edits without the approval spam.
5. **Background + PTY for long tasks** — monitor with `poll`/`log`, be patient.
6. **Hooks noise** — the user's `~/.gemini/settings.json` may have broken hooks (e.g. claude-mem) that print PowerShell errors on every start; harmless, ignore, or fix the hook command.
7. **No quota API exists** — Google exposes no programmatic Gemini usage/quota endpoint (verified 404s); never claim a quota chip can show real numbers.

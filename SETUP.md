# Setup: agent-driven development

Everything below runs from the repo root. Needs `gh` (logged in), `uv`, and Claude Code.

## How it works

| Workflow | Trigger | What it does |
|---|---|---|
| `agent-dev` | You add label `agent` to one of your issues | Claude implements it on `agent/issue-N-*`, opens a PR as your bot |
| `agent-review` → `review` | Any push to an `agent/` PR | Separate read-only Claude reviews it, ends with `VERDICT: LGTM` or `VERDICT: CHANGES_REQUESTED` |
| `agent-review` → `fix` | Verdict was CHANGES_REQUESTED | Implementation agent fixes and pushes (re-triggers review). After 3 rounds → `needs-human` |
| `agent-mention` | You comment `@claude ...` on an issue/PR | Claude follows your instruction |
| `ci` | Every PR + push to main | ruff, format check, pytest, mock smoke game |
| `tournament` | Manual (Actions tab) | Runs dev or full tournament, uploads results, leaderboard in summary |
| `release` | Push a `v*` tag | Tests, build, GitHub release |

Agents can't merge: reviews are comments, `main` is protected, and only you approve.

## 1. Create the repo and push the starter

```bash
cd bartertown
git init -b main
git add .
git commit -m "Starter: spec, agent workflows, CI"
gh repo create bartertown --public --source . --push
```

Then edit `.github/CODEOWNERS` (replace `YOUR_GITHUB_USERNAME`) and fill the `REPLACE_ME`
model IDs in `config/tournament.yaml`; commit and push.

## 2. Claude auth for the agents (uses your Max plan)

```bash
claude setup-token                       # prints a long-lived OAuth token
gh secret set CLAUDE_CODE_OAUTH_TOKEN    # paste it
```

## 3. Bot identity (GitHub App)

PRs must be pushed with an App token, not `GITHUB_TOKEN`, or CI and the reviewer won't fire.

1. GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**
   - Name: e.g. `paperclip-agent-<you>`; Homepage: your repo URL; **uncheck Webhook**
   - Repository permissions: **Contents: Read & write**, **Pull requests: Read & write**,
     **Issues: Read & write** (Metadata: read is automatic)
   - Where can it be installed: Only on this account
2. Create it → note the **App ID** → **Generate a private key** (downloads a `.pem`)
3. **Install App** → only the `bartertown` repo
4. Store it:
   ```bash
   gh variable set AGENT_APP_ID --body "<app id>"
   gh secret set AGENT_APP_PRIVATE_KEY < ~/Downloads/<your-app>.private-key.pem
   rm ~/Downloads/<your-app>.private-key.pem
   ```
   The App has no Workflows permission, so agents physically can't change `.github/workflows`.

## 4. Protect main

Settings → Rules → Rulesets → New branch ruleset → target `main`, no bypass except you:
- Require a pull request: **1 approval**, **Require review from Code Owners**, dismiss stale approvals
- Require status checks: **`checks`** (from `ci`)
- Block force pushes, restrict deletions

## 5. Tournament keys (kept away from coding agents)

Settings → Environments → New environment `tournament` → add secrets:
`ANTHROPIC_API_KEY` (Console key linked to your Max API credits), `OPENAI_API_KEY`,
`GEMINI_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY`. Optionally add yourself as a
required reviewer so every paid run needs a click.

## 6. Seed the backlog and start

```bash
bash scripts/seed_issues.sh
gh issue edit <first-issue-number> --add-label agent
```

Loop: agent opens PR → reviewer comments → (auto-fix) → CI green → **you review and merge** →
label the next issue. Label one at a time; issues build on each other.

After the "Tournament runner, CLI, and smoke mode" issue merges:
```bash
gh variable set SMOKE_REQUIRED --body true
```
Then run Actions → tournament → `config/dev.yaml` first, `config/tournament.yaml` when happy.

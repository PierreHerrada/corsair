# Agent Prompts — Corsair

All prompts sent to the Claude Code CLI subprocess during each stage of task execution.

## Invocation

The Claude Code CLI is invoked as an asyncio subprocess:

```python
process = await asyncio.create_subprocess_exec(
    "claude", "--print", "--dangerously-skip-permissions",
    prompt,
    cwd=repo_local_path,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    env={**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key}
)
```

## Stage Prompts

### Plan Stage

**Purpose:** Analyze the task and produce a detailed implementation plan.

**Template:**
```
You are a senior software engineer.
Analyze the following ticket and write a detailed, step-by-step implementation plan.
Save it as PLAN.md at the root of the repository.

Title: {title}
Description: {description}
Acceptance criteria: {acceptance}
```

**Variables:**
| Variable | Source | Description |
|---|---|---|
| `{title}` | `task.title` | Task title from Slack/Jira |
| `{description}` | `task.description` | Detailed task description |
| `{acceptance}` | `task.acceptance` | Acceptance criteria |

**Expected Output:** A `PLAN.md` file at the repo root with numbered steps.

**Task Status After:**
- Success: `planned`
- Failure: `failed`

---

### Work Stage

**Purpose:** Implement the plan by writing code, tests, and committing changes.

**Template:**
```
You are a senior software engineer.
Implement the plan in PLAN.md exactly.
Write clean, well-tested code.
Commit your changes with descriptive commit messages.
Do not open a PR yet.
```

**Variables:** None — reads PLAN.md from the repo.

**Expected Output:** Code changes committed to a feature branch.

**Task Status After:**
- Success: `working` → stays `working` (until Review starts)
- Failure: `failed`

---

### Review Stage

**Purpose:** Review all changes, fix issues, and open a GitHub PR.

**Template:**
```
You are a senior software engineer reviewing your own work.
Review all changes since the base branch.
Fix any issues found.
Then open a Pull Request on GitHub with:
- Title: {jira_key} — {title}
- Body: summary of changes, link to Jira ticket ({jira_url}), test results
- Base branch: main
```

**Variables:**
| Variable | Source | Description |
|---|---|---|
| `{jira_key}` | `task.jira_key` | Jira issue key (e.g., SWE-123) |
| `{title}` | `task.title` | Task title |
| `{jira_url}` | `task.jira_url` | Full URL to Jira issue |

**Expected Output:** A GitHub PR with descriptive title, body, and passing tests.

**Task Status After:**
- Success: `reviewing` → `done` (after PR is created)
- Failure: `failed`

---

## Cost Calculation

After each stage completes, token usage is parsed from Claude Code CLI stderr and cost is calculated:

```python
INPUT_PRICE_PER_M  = 3.00   # USD per million tokens (claude-sonnet-4)
OUTPUT_PRICE_PER_M = 15.00

cost = (tokens_in  / 1_000_000 * INPUT_PRICE_PER_M) + \
       (tokens_out / 1_000_000 * OUTPUT_PRICE_PER_M)
```

The cost is saved to the `agent_runs` record.

## Slack Notifications

After each stage, the bot posts an update to the original Slack thread:

| Event | Message |
|---|---|
| Ticket created | `✅ Ticket created: *{jira_key}* — {title}\n{jira_url}` |
| Plan complete | `📋 Plan ready. Review it in the board and trigger Work when ready.` |
| Work complete | `⚙️ Code written and committed. Trigger Review when ready.` |
| PR opened | `🚀 PR ready: {pr_url}` |
| Stage failed | `❌ {stage} failed. Check the dashboard for logs.` |

from __future__ import annotations

from typing import Optional


def build_plan_prompt(
    title: str,
    description: str,
    acceptance: str,
    task_repo: Optional[str] = None,
) -> str:
    repo_hint = ""
    if task_repo:
        from app.agent.workspace import repo_to_subfolder

        subfolder = repo_to_subfolder(task_repo)
        repo_hint = f"\nPrimary repo is in `{subfolder}/` subfolder."

    return f"""You are a senior software engineer.
Analyze the following ticket and write a detailed, step-by-step implementation plan.
Save it as PLAN.md at the root of the repository.

Title: {title}
Description: {description}
Acceptance criteria: {acceptance}{repo_hint}"""


def build_work_prompt(
    task_repo: Optional[str] = None,
    title: str = "",
    description: str = "",
) -> str:
    repo_hint = ""
    if task_repo:
        from app.agent.workspace import repo_to_subfolder

        subfolder = repo_to_subfolder(task_repo)
        repo_hint = f"\nPrimary repo is in `{subfolder}/` subfolder."

    ticket_context = ""
    if title:
        ticket_context += f"\nTitle: {title}"
    if description:
        ticket_context += f"\nDescription: {description}"

    return f"""You are a senior software engineer.
Implement the plan in PLAN.md exactly.
Write clean, well-tested code.

Git workflow (follow these steps exactly):
1. Create a new branch from the current branch. The branch name MUST start with `corsair/` followed by `feat/` or `fix/` and a short kebab-case description (e.g. `corsair/feat/add-user-auth`, `corsair/fix/null-pointer-crash`).
2. Commit your changes with descriptive commit messages.
3. Push the branch to the remote: `git push -u origin <branch-name>`.
4. Open a Pull Request on GitHub with a clear title and summary of changes. Base branch: main.
5. Write the PR URL to a file called PR_URL.txt at the workspace root (just the URL, nothing else).{repo_hint}{ticket_context}"""


def build_review_prompt(jira_key: str, title: str, jira_url: str) -> str:
    return f"""You are a senior software engineer reviewing your own work.
Review all changes since the base branch.
Fix any issues found.
Make sure all changes are committed and the branch is pushed to the remote (`git push`).
Then open a Pull Request on GitHub with:
- Title: {jira_key} — {title}
- Body: summary of changes, link to Jira ticket ({jira_url}), test results
- Base branch: main

After creating the PR, write the PR URL to a file called PR_URL.txt at the workspace root.
The file should contain only the PR URL, nothing else."""


def build_investigate_prompt(
    title: str,
    description: str,
    datadog_context: str = "",
) -> str:
    context_block = ""
    if datadog_context:
        context_block = f"\nPre-fetched Datadog data:\n{datadog_context}\n"

    return f"""You are a senior SRE / incident investigator.
Investigate the following Datadog alert or incident and produce a structured summary.

Title: {title}
Description: {description}
{context_block}
Your investigation should include:
1. **Timeline** — What happened and when, in chronological order
2. **Root cause** — What triggered the incident and why
3. **Affected services** — Which services/monitors were impacted
4. **Resolution** — What was done (or needs to be done) to resolve it

You have access to Datadog API credentials via environment variables:
- DD_API_KEY, DD_APP_KEY, DD_SITE (default: datadoghq.com)

You can write and run Python scripts to fetch additional data from Datadog APIs:
- Logs: POST https://api.{{DD_SITE}}/api/v2/logs/events/search
- Traces: POST https://api.{{DD_SITE}}/api/v2/spans/events/search
- Incidents: GET https://api.{{DD_SITE}}/api/v2/incidents
- Monitors: GET https://api.{{DD_SITE}}/api/v1/monitor
- Events: POST https://api.{{DD_SITE}}/api/v2/events/search

Include headers: DD-API-KEY and DD-APPLICATION-KEY.

A helper script `datadog_helper.py` is available in the workspace root.

Write your final investigation summary to INVESTIGATION.md at the workspace root."""

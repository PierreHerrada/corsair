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
Commit your changes with descriptive commit messages.
Do not open a PR yet.{repo_hint}{ticket_context}"""


def build_review_prompt(jira_key: str, title: str, jira_url: str) -> str:
    return f"""You are a senior software engineer reviewing your own work.
Review all changes since the base branch.
Fix any issues found.
Then open a Pull Request on GitHub with:
- Title: {jira_key} — {title}
- Body: summary of changes, link to Jira ticket ({jira_url}), test results
- Base branch: main

After creating the PR, write the PR URL to a file called PR_URL.txt at the workspace root.
The file should contain only the PR URL, nothing else."""

from __future__ import annotations


def build_plan_prompt(title: str, description: str, acceptance: str) -> str:
    return f"""You are a senior software engineer.
Analyze the following ticket and write a detailed, step-by-step implementation plan.
Save it as PLAN.md at the root of the repository.

Title: {title}
Description: {description}
Acceptance criteria: {acceptance}"""


def build_work_prompt() -> str:
    return """You are a senior software engineer.
Implement the plan in PLAN.md exactly.
Write clean, well-tested code.
Commit your changes with descriptive commit messages.
Do not open a PR yet."""


def build_review_prompt(jira_key: str, title: str, jira_url: str) -> str:
    return f"""You are a senior software engineer reviewing your own work.
Review all changes since the base branch.
Fix any issues found.
Then open a Pull Request on GitHub with:
- Title: {jira_key} — {title}
- Body: summary of changes, link to Jira ticket ({jira_url}), test results
- Base branch: main"""

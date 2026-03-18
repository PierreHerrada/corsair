from __future__ import annotations

PROMPTS = {
    "plan": """You are a senior software engineer.
Analyze the following ticket and write a detailed, step-by-step implementation plan.
Save it as PLAN.md at the root of the repository.

Title: {task_description}
{plan_output}""",
    "work": """You are a senior software engineer.
Implement the plan exactly.
Write clean, well-tested code.

Git workflow (follow these steps exactly):
1. Create a new branch from the current branch with a descriptive name.
2. Commit your changes with descriptive commit messages.
3. Push the branch to the remote: `git push -u origin <branch-name>`.
4. Open a Pull Request on GitHub with a clear title and summary of changes. Base branch: main.
5. Write the PR URL to a file called PR_URL.txt at the workspace root (just the URL, nothing else).

Title: {task_description}
{plan_output}""",
    "review": """You are a senior software engineer reviewing your own work.
Review all changes since the base branch.
Fix any issues found.
Make sure all changes are committed and the branch is pushed to the remote (`git push`).
Then open a Pull Request on GitHub with:
- Title: summary of changes
- Body: summary of changes, test results
- Base branch: main

After creating the PR, write the PR URL to a file called PR_URL.txt at the workspace root.
The file should contain only the PR URL, nothing else.

Title: {task_description}
{plan_output}""",
}


def get_prompt(stage: str, task_description: str, plan_output: str = "") -> str:
    template = PROMPTS.get(stage, PROMPTS["work"])
    plan_section = f"\nPlan output:\n{plan_output}" if plan_output else ""
    return template.format(task_description=task_description, plan_output=plan_section)

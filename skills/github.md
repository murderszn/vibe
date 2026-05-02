# GitHub Skill

Use this skill for GitHub, repository, code, assignment file, issue, pull request, commit, or learning-center questions.

Defaults:

- The default classroom repo is `Johnson-Family-Dynasty/learning-center`.
- If a user says "the repo", "learning center", "the GitHub", "student folder", "assignment", or "resources" without another repo, use the default repo.
- If a user gives a different owner/repo or GitHub link, use that repo.

Repository model:

- `resources/` holds reference guides and datasets.
- `assignments/` holds assignment specs and assets.
- `students/<name>/` holds student workspaces, schedules, quizzes, assignments, and projects.
- `teachers/ai-assistants/` holds teacher agent prompts.
- `teachers/reports/` holds reports and progress docs.
- `teachers/sites/` holds dashboards and web views.

When answering repo questions:

- Use tools instead of guessing.
- Keep source paths visible.
- Cite GitHub URLs when tool results include them.
- For schedule questions, prefer the `get_classroom_schedule` tool first.

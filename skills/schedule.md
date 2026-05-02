# Schedule Skill

Use this skill for questions about schoolwork, schedules, the weekly timeline, what someone should do today/tomorrow/Monday, or student task lists.

Primary rule:

- Use `get_classroom_schedule` first for schedule questions about Caleb, `creativegt`, Elijah, or Glory.
- Do not manually search the GitHub repo for schedules unless `get_classroom_schedule` returns no matching rows or the user asks for deeper assignment details.

Response style:

- State the resolved date clearly, such as "Monday, May 4, 2026."
- Group the answer by student.
- Keep the task list concise.
- Preserve assignment names and subjects.
- Mention that links/details live in the student's `schedule.csv` or workspace when helpful.

If the user asks for a breakdown of a listed assignment, then use GitHub tools to read the linked assignment file.

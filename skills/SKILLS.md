# Vibe Skills Index

Vibe can load trusted local skill files from this folder. Skills are behavioral instructions, not executable code. Tool access is still controlled by the Python tool schemas passed to Claude.

Available skills:

- `classroom.md` — JFD family/classroom identity, roles, and repo model.
- `tutor.md` — student tutoring style and age-aware coaching.
- `teacher-assistant.md` — parent/teacher planning, rubrics, assignments, and classroom materials.
- `family-helper.md` — productivity, routines, planning, and friendly family-buddy mode.
- `schedule.md` — schedule and schoolwork lookup rules.
- `github.md` — learning-center GitHub behavior.
- `web-live.md` — live web, URL, weather, and source-citation behavior.

Only load skills from the allowlist in `prompting.py`.

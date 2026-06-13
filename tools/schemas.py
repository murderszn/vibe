from config import (
    SERVER_TIMEZONE,
    OPENCRUSH_GITHUB_OWNER,
    OPENCRUSH_GITHUB_REPO,
)

_GITHUB_DEFAULT_NOTE = (
    f" Defaults to {OPENCRUSH_GITHUB_OWNER}/{OPENCRUSH_GITHUB_REPO} when owner/repo are omitted."
    if OPENCRUSH_GITHUB_OWNER and OPENCRUSH_GITHUB_REPO
    else ""
)

TOOLS = [
    {
        "name": "get_current_time",
        "description": (
            f"Get the current date and time. Defaults to the server timezone ({SERVER_TIMEZONE}). "
            "Use when a user asks what time or day it is."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": f"Optional IANA timezone, e.g. America/New_York. Defaults to {SERVER_TIMEZONE}.",
                }
            },
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use for news, facts, documentation, "
            "or anything that may have changed since training."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_webpage",
        "description": (
            "Fetch and read the text content of a specific URL. "
            "Use when a user pastes a link they want you to read or summarize."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to fetch"}
            },
            "required": ["url"],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Get current weather and a short forecast for any city or location. "
            "Always use this when a user asks about weather, temperature, or forecast."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or city+state/country, e.g. 'Chicago, IL'",
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "github",
        "description": (
            f"Access GitHub repositories.{_GITHUB_DEFAULT_NOTE} "
            "Can summarize a repo, list files, read files, search code, list commits, "
            "and look up issues or pull requests."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "repo_summary",
                        "list_files",
                        "get_file",
                        "search_code",
                        "search_repos",
                        "get_issue",
                        "list_issues",
                        "get_pull_request",
                        "list_pull_requests",
                        "list_commits",
                    ],
                    "description": "The operation to perform",
                },
                "owner": {"type": "string", "description": "Repository owner (GitHub username or org)."},
                "repo": {"type": "string", "description": "Repository name."},
                "path": {"type": "string", "description": "File or directory path in the repo."},
                "query": {"type": "string", "description": "Search string. For search_code, scoped to owner/repo unless query already includes 'repo:'."},
                "issue_number": {"type": "integer", "description": "Issue number (for get_issue)"},
                "pull_number": {"type": "integer", "description": "Pull request number (for get_pull_request)"},
                "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Issue or PR state. Defaults to open."},
                "branch": {"type": "string", "description": "Branch, tag, or commit SHA for list_files."},
            },
            "required": ["action"],
        },
    },
]

import base64
from urllib.parse import quote

import requests

from config import (
    GITHUB_HEADERS,
    HTTP_TIMEOUT,
    LEARNING_CENTER_OWNER,
    LEARNING_CENTER_REPO,
    MAX_GITHUB_RESULTS,
    MAX_GITHUB_TREE,
)
from tools.common import truncate


def github_target(owner=None, repo=None) -> tuple[str, str]:
    return (owner or LEARNING_CENTER_OWNER), (repo or LEARNING_CENTER_REPO)


def _github_error(resp: requests.Response) -> str:
    try:
        message = resp.json().get("message", "")
    except ValueError:
        message = resp.text[:200]

    extra = ""
    if resp.status_code in {401, 403}:
        extra = " If the repo is private or code search is blocked, set GITHUB_TOKEN with repo access."
    elif resp.status_code == 404:
        extra = " Check the owner/repo/path and confirm GITHUB_TOKEN can access the repo."
    return f"GitHub API {resp.status_code}: {message}.{extra}"


def github_get(endpoint: str, params=None, headers=None):
    url = f"https://api.github.com{endpoint}"
    resp = requests.get(
        url,
        headers=headers or GITHUB_HEADERS,
        params=params,
        timeout=HTTP_TIMEOUT,
    )
    if not resp.ok:
        raise RuntimeError(_github_error(resp))
    return resp.json()


def decode_github_file(data: dict) -> str:
    if data.get("size", 0) > 1_000_000:
        return "File is too large to read safely through Discord."
    if data.get("encoding") == "base64":
        raw = base64.b64decode(data.get("content", ""))
        return raw.decode("utf-8", errors="replace")
    return data.get("content", "")


def _format_directory_listing(data: list, owner: str, repo: str, path: str) -> str:
    items = sorted(data, key=lambda item: (item.get("type") != "dir", item.get("name", "").lower()))
    lines = []
    for item in items[:MAX_GITHUB_TREE]:
        item_type = "dir " if item.get("type") == "dir" else "file"
        lines.append(f"{item_type}  {item.get('path', item.get('name', ''))}")

    more = ""
    if len(items) > MAX_GITHUB_TREE:
        more = f"\n...and {len(items) - MAX_GITHUB_TREE} more items."

    return (
        f"Repository: {owner}/{repo}\n"
        f"Path: /{path.strip('/') if path else ''}\n\n"
        + "\n".join(lines)
        + more
    )


def _github_repo_summary(owner: str, repo: str) -> str:
    repo_data = github_get(f"/repos/{owner}/{repo}")
    topics = ", ".join(repo_data.get("topics") or []) or "none"

    readme_preview = "README unavailable."
    try:
        readme = github_get(f"/repos/{owner}/{repo}/readme")
        readme_preview = truncate(decode_github_file(readme).strip(), 1200)
    except Exception as exc:
        readme_preview = f"README unavailable: {exc}"

    return truncate(
        f"Repository: {repo_data.get('full_name')}\n"
        f"URL: {repo_data.get('html_url')}\n"
        f"Description: {repo_data.get('description') or 'none'}\n"
        f"Default branch: {repo_data.get('default_branch')}\n"
        f"Visibility/private: {'private' if repo_data.get('private') else 'public'}\n"
        f"Open issues count: {repo_data.get('open_issues_count')}\n"
        f"Updated: {repo_data.get('updated_at')}\n"
        f"Topics: {topics}\n\n"
        f"README preview:\n{readme_preview}"
    )


def tool_github(
    action: str,
    owner=None,
    repo=None,
    path=None,
    query=None,
    issue_number=None,
    pull_number=None,
    state=None,
    branch=None,
) -> str:
    owner, repo = github_target(owner, repo)
    state = state if state in {"open", "closed", "all"} else "open"

    if action == "repo_summary":
        return _github_repo_summary(owner, repo)

    if action == "get_file":
        clean_path = (path or "").strip("/")
        encoded_path = quote(clean_path, safe="/")
        endpoint = f"/repos/{owner}/{repo}/contents"
        if encoded_path:
            endpoint += f"/{encoded_path}"
        data = github_get(endpoint)
        if isinstance(data, list):
            return _format_directory_listing(data, owner, repo, clean_path)
        if data.get("type") != "file":
            return f"Repository: {owner}/{repo}\nPath is not a readable file: {clean_path or '/'}"
        content = decode_github_file(data)
        return truncate(
            f"Repository: {owner}/{repo}\n"
            f"Path: {data.get('path')}\n"
            f"URL: {data.get('html_url')}\n\n"
            f"{content}"
        )

    if action == "list_files":
        repo_data = github_get(f"/repos/{owner}/{repo}")
        ref = branch or repo_data.get("default_branch") or "main"
        tree = github_get(
            f"/repos/{owner}/{repo}/git/trees/{quote(ref, safe='')}",
            params={"recursive": "1"},
        )
        rows = tree.get("tree", [])
        q = (query or "").lower().strip()
        if q:
            rows = [item for item in rows if q in item.get("path", "").lower()]

        lines = []
        for item in rows[:MAX_GITHUB_TREE]:
            item_type = "dir " if item.get("type") == "tree" else "file"
            size = f" ({item.get('size')} bytes)" if item.get("type") == "blob" and item.get("size") is not None else ""
            lines.append(f"{item_type}  {item.get('path')}{size}")

        if not lines:
            return f"No files matched in {owner}/{repo}."
        more = ""
        if len(rows) > MAX_GITHUB_TREE:
            more = f"\n...and {len(rows) - MAX_GITHUB_TREE} more items."
        truncated = "\nGitHub marked this tree as truncated; results may be incomplete." if tree.get("truncated") else ""
        return truncate(
            f"Repository: {owner}/{repo}\n"
            f"Ref: {ref}\n"
            f"Filter: {query or 'none'}\n\n"
            + "\n".join(lines)
            + more
            + truncated
        )

    if action == "search_repos":
        if not query:
            return "search_repos requires a query."
        data = github_get(
            "/search/repositories",
            params={"q": query, "sort": "stars", "per_page": 5},
        )
        items = data.get("items", [])
        parts = []
        for item in items:
            parts.append(f"{item['full_name']} ⭐{item['stargazers_count']}\n{item.get('description') or ''}\n{item['html_url']}")
        return truncate("\n\n".join(parts)) if parts else "No results."

    if action == "search_code":
        if not query:
            return "search_code requires a query."
        scoped_query = query if "repo:" in query else f"{query} repo:{owner}/{repo}"
        headers = {**GITHUB_HEADERS, "Accept": "application/vnd.github.text-match+json"}
        try:
            data = github_get(
                "/search/code",
                params={"q": scoped_query, "per_page": MAX_GITHUB_RESULTS},
                headers=headers,
            )
        except RuntimeError as exc:
            path_matches = tool_github("list_files", owner=owner, repo=repo, query=query)
            return truncate(f"Code search unavailable: {exc}\n\nPath-match fallback:\n{path_matches}")

        items = data.get("items", [])
        parts = []
        for item in items:
            fragments = []
            for match in item.get("text_matches", [])[:2]:
                fragment = " ".join(match.get("fragment", "").split())
                if fragment:
                    fragments.append(truncate(fragment, 250))
            snippet = "\n".join(f"Match: {fragment}" for fragment in fragments)
            if snippet:
                snippet = "\n" + snippet
            parts.append(f"{item['repository']['full_name']}: {item['path']}\n{item['html_url']}{snippet}")
        return truncate("\n\n".join(parts)) if parts else "No results."

    if action == "get_issue":
        if not issue_number:
            return "get_issue requires issue_number."
        issue = github_get(f"/repos/{owner}/{repo}/issues/{issue_number}")
        labels = ", ".join(label["name"] for label in issue.get("labels", [])) or "none"
        body = truncate(issue.get("body") or "", 1800)
        return (
            f"Repository: {owner}/{repo}\n"
            f"Issue: #{issue['number']} {issue['title']}\n"
            f"State: {issue['state']}\n"
            f"Labels: {labels}\n"
            f"URL: {issue.get('html_url')}\n\n"
            f"{body}"
        )

    if action == "list_issues":
        issues = github_get(
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": MAX_GITHUB_RESULTS},
        )
        issues = [issue for issue in issues if "pull_request" not in issue]
        lines = [f"#{i['number']}: {i['title']}\n{i['html_url']}" for i in issues]
        return f"Repository: {owner}/{repo}\nIssues ({state}):\n\n" + "\n\n".join(lines) if lines else f"No {state} issues."

    if action == "get_pull_request":
        if not pull_number:
            return "get_pull_request requires pull_number."
        pr = github_get(f"/repos/{owner}/{repo}/pulls/{pull_number}")
        body = truncate(pr.get("body") or "", 1800)
        return (
            f"Repository: {owner}/{repo}\n"
            f"PR: #{pr['number']} {pr['title']}\n"
            f"State: {pr['state']} | Draft: {pr.get('draft')}\n"
            f"Branch: {pr['head']['ref']} -> {pr['base']['ref']}\n"
            f"URL: {pr.get('html_url')}\n\n"
            f"{body}"
        )

    if action == "list_pull_requests":
        pulls = github_get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": MAX_GITHUB_RESULTS},
        )
        lines = [f"#{pr['number']}: {pr['title']}\n{pr['html_url']}" for pr in pulls]
        return f"Repository: {owner}/{repo}\nPull requests ({state}):\n\n" + "\n\n".join(lines) if lines else f"No {state} pull requests."

    if action == "list_commits":
        params = {"per_page": MAX_GITHUB_RESULTS}
        if branch:
            params["sha"] = branch
        commits = github_get(f"/repos/{owner}/{repo}/commits", params=params)
        lines = []
        for commit in commits:
            detail = commit.get("commit", {})
            author = detail.get("author", {}) or {}
            sha = commit.get("sha", "")[:7]
            message = (detail.get("message") or "").splitlines()[0]
            lines.append(f"{sha} {author.get('date', '')} {author.get('name', '')}: {message}\n{commit.get('html_url')}")
        return f"Repository: {owner}/{repo}\nRecent commits:\n\n" + "\n\n".join(lines) if lines else "No commits found."

    return f"Unknown GitHub action: {action}"

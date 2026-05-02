from config import MAX_TOOL_RESULT


def truncate(text: str, limit: int = MAX_TOOL_RESULT) -> str:
    if len(text) > limit:
        return text[:limit].rstrip() + "\n[truncated]"
    return text

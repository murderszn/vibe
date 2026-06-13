import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

# ── Runtime config ────────────────────────────────────────────────────────────
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
MAX_HISTORY = 10
COOLDOWN_SECONDS = 5           # AI chat per-user cooldown (seconds)
MAX_RESPONSE_LEN = 1900
MAX_TOOL_RESULT = 3000
MAX_SEARCH_RESULTS = 5
MAX_GITHUB_RESULTS = 10
MAX_GITHUB_TREE = 150
MAX_TOOL_ROUNDS = 3
MAX_TOOL_ROUNDS_FRESH_FACTS = 4
MAX_TOOL_ROUNDS_REPO = 3
MAX_TOOL_ROUNDS_SCHEDULE = 2
TOOL_CALL_TIMEOUT_SECONDS = 8
HTTP_TIMEOUT = 12
VIBE_PERSONA_MODE = os.getenv("VIBE_PERSONA_MODE", "balanced")
VIBE_SARCASM_LEVEL = max(0, min(3, int(os.getenv("VIBE_SARCASM_LEVEL", "1"))))
VIBE_SARCASM_BLOCKLIST_CONTEXTS = tuple(
    context.strip().lower()
    for context in os.getenv(
        "VIBE_SARCASM_BLOCKLIST_CONTEXTS",
        "safety-sensitive,sensitive topics,frustrated,confused,upset,grief,mental health,self-harm,medical,legal,crisis",
    ).split(",")
    if context.strip()
)

# ── Server identity ───────────────────────────────────────────────────────────
SERVER_NAME = os.getenv("SERVER_NAME", "OpenCrush")
SERVER_TIMEZONE = os.getenv("SERVER_TIMEZONE", "America/Chicago")

# ── Channel names (bot resolves by name at runtime) ───────────────────────────
LOG_CHANNEL_NAME = os.getenv("LOG_CHANNEL_NAME", "mod-log")
WELCOME_CHANNEL_NAME = os.getenv("WELCOME_CHANNEL_NAME", "welcome")
LEVEL_UP_CHANNEL_NAME = os.getenv("LEVEL_UP_CHANNEL_NAME", "")  # empty = same channel as message

# ── Leveling ──────────────────────────────────────────────────────────────────
XP_PER_MESSAGE_MIN = int(os.getenv("XP_PER_MESSAGE_MIN", "15"))
XP_PER_MESSAGE_MAX = int(os.getenv("XP_PER_MESSAGE_MAX", "25"))
XP_COOLDOWN_SECONDS = int(os.getenv("XP_COOLDOWN_SECONDS", "60"))

# Role rewards: list of (min_level, role_name). Set role names in env or edit here.
LEVEL_ROLE_REWARDS: list[tuple[int, str]] = [
    (5,  os.getenv("ROLE_LEVEL_5",  "Active Member")),
    (10, os.getenv("ROLE_LEVEL_10", "Regular")),
    (20, os.getenv("ROLE_LEVEL_20", "OC Insider")),
    (50, os.getenv("ROLE_LEVEL_50", "OC Legend")),
]

# ── Automod ───────────────────────────────────────────────────────────────────
AUTOMOD_SPAM_THRESHOLD = int(os.getenv("AUTOMOD_SPAM_THRESHOLD", "5"))   # messages in window
AUTOMOD_SPAM_WINDOW = int(os.getenv("AUTOMOD_SPAM_WINDOW", "5"))          # seconds
AUTOMOD_BLOCK_INVITES = os.getenv("AUTOMOD_BLOCK_INVITES", "true").lower() == "true"
AUTOMOD_BANNED_WORDS: list[str] = [
    w.strip() for w in os.getenv("AUTOMOD_BANNED_WORDS", "").split(",") if w.strip()
]

# ── GitHub (optional — used by AI tool) ──────────────────────────────────────
OPENCRUSH_GITHUB_OWNER = os.getenv("OPENCRUSH_GITHUB_OWNER", "")
OPENCRUSH_GITHUB_REPO = os.getenv("OPENCRUSH_GITHUB_REPO", "")

REQUEST_HEADERS = {
    "User-Agent": "OpenCrush-VibeBot/2.0 (+https://opencrush.app)",
}

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    **REQUEST_HEADERS,
    **({"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}),
}


def server_timezone():
    try:
        return ZoneInfo(SERVER_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return datetime.now().astimezone().tzinfo


def now_in_server_timezone() -> datetime:
    return datetime.now(server_timezone())


def format_current_time_context(now=None) -> str:
    now = now or now_in_server_timezone()
    timezone_name = getattr(now.tzinfo, "key", None) or now.tzname() or SERVER_TIMEZONE
    return (
        "Current server time:\n"
        f"- Local date: {now.strftime('%A, %B')} {now.day}, {now.year}\n"
        f"- Local time: {now.strftime('%I:%M %p').lstrip('0')} {now.tzname() or ''}\n"
        f"- Timezone: {timezone_name}\n"
        f"- ISO timestamp: {now.isoformat()}"
    )

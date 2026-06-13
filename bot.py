"""
Vibe — OpenCrush Discord Manager
Mee6-style moderation, leveling, welcome, automod, and AI chat.
"""

import asyncio
import concurrent.futures
import json
import os
import random
import re
import time
import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import anthropic
import discord
from discord.ext import commands

from config import (
    AUTOMOD_BANNED_WORDS,
    AUTOMOD_BLOCK_INVITES,
    AUTOMOD_SPAM_THRESHOLD,
    AUTOMOD_SPAM_WINDOW,
    BOT_PREFIX,
    COOLDOWN_SECONDS,
    LEVEL_ROLE_REWARDS,
    LEVEL_UP_CHANNEL_NAME,
    LOG_CHANNEL_NAME,
    MAX_HISTORY,
    MAX_RESPONSE_LEN,
    MAX_SUMMARY_LENGTH,
    MAX_TOOL_ROUNDS,
    SERVER_NAME,
    WELCOME_CHANNEL_NAME,
    XP_COOLDOWN_SECONDS,
    XP_PER_MESSAGE_MAX,
    XP_PER_MESSAGE_MIN,
)
from prompting import build_system_prompt
from tools.github_tools import tool_github
from tools.schemas import TOOLS
from tools.time_tools import tool_get_current_time
from tools.web_tools import tool_fetch_webpage, tool_get_weather, tool_web_search

# ── Brand ──────────────────────────────────────────────────────────────────────
OC_PINK = 0xD94686

# ── Data persistence ───────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

XP_FILE = DATA_DIR / "xp.json"
WARNINGS_FILE = DATA_DIR / "warnings.json"
CMDS_FILE = DATA_DIR / "custom_commands.json"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2))


xp_data: dict[str, int] = _load_json(XP_FILE, {})
warnings_data: dict[str, list] = _load_json(WARNINGS_FILE, {})
custom_commands: dict[str, str] = _load_json(CMDS_FILE, {})

# ── In-memory state ────────────────────────────────────────────────────────────
conversation_histories: dict[int, list] = defaultdict(list)
ai_cooldown: dict[int, float] = defaultdict(float)
xp_cooldown: dict[int, float] = defaultdict(float)
spam_tracker: dict[int, list] = defaultdict(list)
TOOL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=6)

# ── Bot setup ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)
ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ─────────────────────────────────────────────────────────────────────────────
# LEVELING
# ─────────────────────────────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """XP required to complete level N (Mee6 formula)."""
    return 5 * (level ** 2) + 50 * level + 100


def level_from_xp(total_xp: int) -> tuple[int, int, int]:
    """Return (level, xp_into_current_level, xp_needed_for_next_level)."""
    level = 0
    remaining = total_xp
    while remaining >= xp_for_level(level):
        remaining -= xp_for_level(level)
        level += 1
    return level, remaining, xp_for_level(level)


async def grant_xp(message: discord.Message) -> None:
    uid = str(message.author.id)
    now = time.time()
    if now - xp_cooldown[message.author.id] < XP_COOLDOWN_SECONDS:
        return
    xp_cooldown[message.author.id] = now

    earned = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
    old_total = xp_data.get(uid, 0)
    new_total = old_total + earned
    xp_data[uid] = new_total
    _save_json(XP_FILE, xp_data)

    old_level, _, _ = level_from_xp(old_total)
    new_level, _, _ = level_from_xp(new_total)
    if new_level > old_level:
        await _announce_level_up(message, new_level)
        if message.guild:
            await _apply_role_rewards(message.author, new_level)


async def _announce_level_up(message: discord.Message, level: int) -> None:
    target_ch = message.channel
    if LEVEL_UP_CHANNEL_NAME and message.guild:
        ch = discord.utils.get(message.guild.text_channels, name=LEVEL_UP_CHANNEL_NAME)
        if ch:
            target_ch = ch
    embed = discord.Embed(
        description=f"🎉 {message.author.mention} just reached **Level {level}**!",
        color=OC_PINK,
    )
    try:
        await target_ch.send(embed=embed)
    except discord.Forbidden:
        pass


async def _apply_role_rewards(member: discord.Member, level: int) -> None:
    for reward_level, role_name in LEVEL_ROLE_REWARDS:
        if level >= reward_level:
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Level {reward_level} reward")
                except discord.Forbidden:
                    pass


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMOD
# ─────────────────────────────────────────────────────────────────────────────

_INVITE_RE = re.compile(r"(discord\.gg|discord\.com/invite)/\S+", re.IGNORECASE)


async def check_automod(message: discord.Message) -> bool:
    """Returns True if the message was deleted (caller should stop processing)."""
    if not message.guild:
        return False
    if message.author.guild_permissions.manage_messages:
        return False

    content = message.content

    if AUTOMOD_BANNED_WORDS and any(w in content.lower() for w in AUTOMOD_BANNED_WORDS):
        try:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} — that word isn't allowed here.", delete_after=5
            )
        except discord.Forbidden:
            pass
        return True

    if AUTOMOD_BLOCK_INVITES and _INVITE_RE.search(content):
        try:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} — external invite links aren't allowed here.", delete_after=5
            )
        except discord.Forbidden:
            pass
        return True

    uid = message.author.id
    now = time.time()
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < AUTOMOD_SPAM_WINDOW]
    spam_tracker[uid].append(now)
    if len(spam_tracker[uid]) >= AUTOMOD_SPAM_THRESHOLD:
        spam_tracker[uid] = []
        try:
            await message.delete()
            until = discord.utils.utcnow() + timedelta(minutes=1)
            await message.author.timeout(until, reason="Automod: spam")
            await message.channel.send(
                f"{message.author.mention} — slow down. Muted for 1 minute for spamming.",
                delete_after=10,
            )
            await _log_action(
                message.guild,
                _mod_embed(
                    "Automod: Spam Timeout",
                    user=str(message.author),
                    channel=f"#{message.channel.name}",
                    duration="1m",
                ),
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _mod_embed(title: str, color: int = OC_PINK, **fields) -> discord.Embed:
    e = discord.Embed(title=title, color=color, timestamp=discord.utils.utcnow())
    for name, value in fields.items():
        e.add_field(name=name.replace("_", " ").title(), value=str(value), inline=True)
    return e


async def _log_action(guild: discord.Guild, embed: discord.Embed) -> None:
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.Forbidden:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# AI CHAT
# ─────────────────────────────────────────────────────────────────────────────

def _preprocess_mentions(content: str, guild: discord.Guild) -> str:
    def replace(match):
        user_id = int(match.group(1))
        member = guild.get_member(user_id)
        return f"@{member.display_name} (id: {user_id})" if member else match.group(0)
    return re.sub(r"<@!?(\d+)>", replace, content)


async def _dispatch_tool(name: str, inputs: dict) -> str:
    loop = asyncio.get_running_loop()
    try:
        if name == "web_search":
            return await loop.run_in_executor(TOOL_EXECUTOR, tool_web_search, inputs["query"])
        if name == "fetch_webpage":
            return await loop.run_in_executor(TOOL_EXECUTOR, tool_fetch_webpage, inputs["url"])
        if name == "get_weather":
            return await loop.run_in_executor(TOOL_EXECUTOR, tool_get_weather, inputs["location"])
        if name == "get_current_time":
            return await loop.run_in_executor(
                TOOL_EXECUTOR, lambda: tool_get_current_time(inputs.get("timezone"))
            )
        if name == "github":
            return await loop.run_in_executor(TOOL_EXECUTOR, lambda: tool_github(**inputs))
        return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Tool error ({name}): {exc}"


async def _send_long(reply_to: discord.Message, text: str) -> None:
    if len(text) > MAX_RESPONSE_LEN:
        text = text[: MAX_RESPONSE_LEN - 22].rstrip() + "\n\n[Reply truncated.]"
    await reply_to.reply(text)


async def handle_ai_chat(message: discord.Message) -> None:
    now = time.time()
    if now - ai_cooldown[message.author.id] < COOLDOWN_SECONDS:
        await message.reply(f"One sec — one question every {COOLDOWN_SECONDS}s, please.")
        return
    ai_cooldown[message.author.id] = now

    clean = re.sub(rf"<@!?{bot.user.id}>", "", message.content).strip()
    if not clean:
        clean = "Hey Vibe, what's up?"
    if message.guild:
        clean = _preprocess_mentions(clean, message.guild)

    roles = [r.name for r in getattr(message.author, "roles", []) if r.name != "@everyone"]
    channel_name = getattr(message.channel, "name", "dm")
    user_ctx = (
        f"[User: {message.author.display_name} (id: {message.author.id}), "
        f"Roles: {', '.join(roles) or 'none'}, Channel: #{channel_name}]\n\n"
    )
    full_content = user_ctx + clean

    history = conversation_histories[message.channel.id]
    history.append({"role": "user", "content": full_content})

    system = build_system_prompt()

    async with message.channel.typing():
        try:
            msgs = list(history)
            tool_rounds = 0
            while True:
                response = ai.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    system=system,
                    tools=TOOLS,
                    messages=msgs,
                )
                if response.stop_reason == "tool_use":
                    blocks = [b for b in response.content if b.type == "tool_use"]
                    tool_rounds += 1
                    if tool_rounds > MAX_TOOL_ROUNDS:
                        text = "Hit the tool-use limit. Try a more focused question."
                        history.append({"role": "assistant", "content": text})
                        await _send_long(message, text)
                        break
                    msgs.append({"role": "assistant", "content": response.content})
                    results = await asyncio.gather(*(_dispatch_tool(b.name, b.input) for b in blocks))
                    msgs.append({
                        "role": "user",
                        "content": [
                            {"type": "tool_result", "tool_use_id": b.id, "content": r}
                            for b, r in zip(blocks, results)
                        ],
                    })
                    continue
                text = next((b.text for b in response.content if hasattr(b, "text")), None)
                if text:
                    history.append({"role": "assistant", "content": text})
                    await _send_long(message, text)
                break
        except Exception as exc:
            await message.reply(f"Something went sideways: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[Vibe] {bot.user} online — {SERVER_NAME} Discord manager ready.")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=f"the {SERVER_NAME} server")
    )


@bot.event
async def on_member_join(member: discord.Member):
    ch = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not ch:
        return
    embed = discord.Embed(
        title=f"Welcome to {member.guild.name}!",
        description=(
            f"Hey {member.mention}, glad you're here! 👋\n\n"
            "**OpenCrush** is the dating app where every profile shows its live engagement metrics — "
            "views, click-through rate, message rate, and an OC Score updated every week. "
            "Open by design.\n\n"
            "📌 Check **#rules** to get started.\n"
            "💬 Introduce yourself in **#introductions**!"
        ),
        color=OC_PINK,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Member #{member.guild.member_count}")
    try:
        await ch.send(embed=embed)
    except discord.Forbidden:
        pass


@bot.event
async def on_member_remove(member: discord.Member):
    ch = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not ch:
        return
    try:
        await ch.send(f"**{member.display_name}** has left the server.")
    except discord.Forbidden:
        pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    deleted = await check_automod(message)
    if deleted:
        return

    is_command = message.content.startswith(BOT_PREFIX)

    if not is_command and message.guild:
        await grant_xp(message)

    # Custom command — exact trigger match, checked before AI
    if not is_command and message.guild:
        trigger = message.content.strip().lower()
        if trigger in custom_commands:
            await message.channel.send(custom_commands[trigger])
            return

    # AI chat on @mention (not a bot command)
    if bot.user in message.mentions and not is_command:
        await handle_ai_chat(message)
        return

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use that command.", delete_after=8)
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(f"I'm missing permissions: {', '.join(error.missing_permissions)}", delete_after=8)
    elif isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
        await ctx.send("Couldn't find that member.", delete_after=8)
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad argument — {error}", delete_after=8)
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Slow down — try again in {error.retry_after:.1f}s.", delete_after=8)
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You can't use that command here.", delete_after=8)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        raise error


# ─────────────────────────────────────────────────────────────────────────────
# MODERATION COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True)
@commands.guild_only()
async def cmd_kick(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Kick a member.  !kick @user [reason]"""
    if member == ctx.author:
        return await ctx.send("You can't kick yourself.", delete_after=5)
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        return await ctx.send("You can't kick someone with an equal or higher role.", delete_after=5)
    await member.kick(reason=f"{ctx.author}: {reason}")
    e = _mod_embed("Member Kicked", user=str(member), moderator=str(ctx.author), reason=reason)
    await ctx.send(embed=e)
    await _log_action(ctx.guild, e)


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True)
@commands.guild_only()
async def cmd_ban(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Ban a member.  !ban @user [reason]"""
    if member == ctx.author:
        return await ctx.send("You can't ban yourself.", delete_after=5)
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        return await ctx.send("You can't ban someone with an equal or higher role.", delete_after=5)
    await member.ban(reason=f"{ctx.author}: {reason}", delete_message_days=1)
    e = _mod_embed("Member Banned", user=str(member), moderator=str(ctx.author), reason=reason)
    await ctx.send(embed=e)
    await _log_action(ctx.guild, e)


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True)
@commands.guild_only()
async def cmd_unban(ctx: commands.Context, *, user: str):
    """Unban by username or user ID.  !unban Username#0000"""
    bans = [entry async for entry in ctx.guild.bans()]
    target = next(
        (e.user for e in bans if str(e.user) == user or str(e.user.id) == user),
        None,
    )
    if not target:
        return await ctx.send(f"No ban found for `{user}`.", delete_after=8)
    await ctx.guild.unban(target, reason=f"Unbanned by {ctx.author}")
    e = _mod_embed("Member Unbanned", user=str(target), moderator=str(ctx.author))
    await ctx.send(embed=e)
    await _log_action(ctx.guild, e)


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
@commands.guild_only()
async def cmd_mute(
    ctx: commands.Context,
    member: discord.Member,
    duration: int = 10,
    *,
    reason: str = "No reason provided",
):
    """Timeout a member.  !mute @user [minutes] [reason]  (default: 10 min, max: 28 days)"""
    if member == ctx.author:
        return await ctx.send("You can't mute yourself.", delete_after=5)
    duration = max(1, min(duration, 40320))
    until = discord.utils.utcnow() + timedelta(minutes=duration)
    await member.timeout(until, reason=f"{ctx.author}: {reason}")
    e = _mod_embed("Member Muted", user=str(member), moderator=str(ctx.author), duration=f"{duration}m", reason=reason)
    await ctx.send(embed=e)
    await _log_action(ctx.guild, e)


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
@commands.guild_only()
async def cmd_unmute(ctx: commands.Context, member: discord.Member):
    """Remove a timeout.  !unmute @user"""
    await member.timeout(None, reason=f"Unmuted by {ctx.author}")
    e = _mod_embed("Member Unmuted", user=str(member), moderator=str(ctx.author))
    await ctx.send(embed=e)
    await _log_action(ctx.guild, e)


@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_warn(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Warn a member.  !warn @user [reason]"""
    uid = str(member.id)
    record = {
        "reason": reason,
        "moderator": str(ctx.author),
        "ts": discord.utils.utcnow().isoformat(),
    }
    warnings_data.setdefault(uid, []).append(record)
    _save_json(WARNINGS_FILE, warnings_data)
    count = len(warnings_data[uid])
    e = _mod_embed(f"Warning #{count} Issued", user=str(member), moderator=str(ctx.author), reason=reason)
    await ctx.send(embed=e)
    try:
        await member.send(f"⚠️ You received a warning in **{ctx.guild.name}**: {reason}")
    except discord.Forbidden:
        pass
    await _log_action(ctx.guild, e)


@bot.command(name="warnings")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_warnings(ctx: commands.Context, member: discord.Member):
    """List a member's warnings.  !warnings @user"""
    uid = str(member.id)
    records = warnings_data.get(uid, [])
    if not records:
        return await ctx.send(f"{member.display_name} has no warnings.")
    embed = discord.Embed(title=f"Warnings — {member.display_name}", color=OC_PINK)
    for i, r in enumerate(records, 1):
        embed.add_field(name=f"#{i} by {r['moderator']}", value=r["reason"], inline=False)
    await ctx.send(embed=embed)


@bot.command(name="clearwarnings")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_clearwarnings(ctx: commands.Context, member: discord.Member):
    """Clear all warnings for a member.  !clearwarnings @user"""
    uid = str(member.id)
    warnings_data[uid] = []
    _save_json(WARNINGS_FILE, warnings_data)
    await ctx.send(f"Cleared all warnings for **{member.display_name}**.")


@bot.command(name="purge", aliases=["clear"])
@commands.has_permissions(manage_messages=True)
@commands.bot_has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_purge(ctx: commands.Context, amount: int, member: discord.Member = None):
    """Delete messages.  !purge [count] [@user optional]  (max 100)"""
    await ctx.message.delete()
    amount = max(1, min(amount, 100))
    check = (lambda m: m.author == member) if member else None
    deleted = await ctx.channel.purge(limit=amount, check=check)
    await ctx.send(f"Deleted {len(deleted)} message(s).", delete_after=5)
    await _log_action(
        ctx.guild,
        _mod_embed("Messages Purged", channel=f"#{ctx.channel.name}", count=len(deleted), moderator=str(ctx.author)),
    )


@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True)
@commands.guild_only()
async def cmd_slowmode(ctx: commands.Context, seconds: int = 0):
    """Set channel slowmode.  !slowmode [seconds]  (0 = off)"""
    seconds = max(0, min(seconds, 21600))
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send("Slowmode disabled." if seconds == 0 else f"Slowmode set to {seconds}s.")


@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True)
@commands.guild_only()
async def cmd_lock(ctx: commands.Context, *, reason: str = "Locked by moderator"):
    """Prevent @everyone from sending messages.  !lock [reason]"""
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)
    await ctx.send(f"🔒 **Channel locked.** {reason}")


@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True)
@commands.guild_only()
async def cmd_unlock(ctx: commands.Context):
    """Re-open a locked channel.  !unlock"""
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 **Channel unlocked.**")


# ─────────────────────────────────────────────────────────────────────────────
# LEVELING COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.command(name="rank")
async def cmd_rank(ctx: commands.Context, member: discord.Member = None):
    """Show your rank or another member's.  !rank [@user]"""
    member = member or ctx.author
    uid = str(member.id)
    total_xp = xp_data.get(uid, 0)
    level, xp_in, xp_needed = level_from_xp(total_xp)

    sorted_ids = sorted(xp_data, key=lambda k: xp_data[k], reverse=True)
    rank_pos = next((i + 1 for i, k in enumerate(sorted_ids) if k == uid), len(sorted_ids) + 1)

    embed = discord.Embed(title=f"{member.display_name}'s Rank", color=OC_PINK)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp_in:,} / {xp_needed:,}", inline=True)
    embed.add_field(name="Total XP", value=f"{total_xp:,}", inline=True)
    embed.add_field(name="Server Rank", value=f"#{rank_pos}", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="leaderboard", aliases=["lb"])
async def cmd_leaderboard(ctx: commands.Context):
    """Top 10 members by XP.  !leaderboard"""
    sorted_xp = sorted(xp_data.items(), key=lambda x: x[1], reverse=True)[:10]
    if not sorted_xp:
        return await ctx.send("No XP data yet — start chatting to earn XP!")
    embed = discord.Embed(title=f"🏆 {SERVER_NAME} Leaderboard", color=OC_PINK)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, (uid, total) in enumerate(sorted_xp, 1):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"User …{uid[-4:]}"
        level, _, _ = level_from_xp(total)
        lines.append(f"{medals.get(i, f'**{i}.**')} {name} — Level {level} ({total:,} XP)")
    embed.description = "\n".join(lines)
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# INFO COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.command(name="serverinfo")
@commands.guild_only()
async def cmd_serverinfo(ctx: commands.Context):
    """Show server stats.  !serverinfo"""
    g = ctx.guild
    embed = discord.Embed(title=g.name, color=OC_PINK, timestamp=discord.utils.utcnow())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="Members", value=f"{g.member_count:,}", inline=True)
    embed.add_field(name="Channels", value=f"{len(g.text_channels)} text · {len(g.voice_channels)} voice", inline=True)
    embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
    embed.add_field(name="Owner", value=str(g.owner), inline=True)
    embed.add_field(name="Created", value=g.created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="Verification", value=str(g.verification_level).replace("_", " ").title(), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="userinfo")
@commands.guild_only()
async def cmd_userinfo(ctx: commands.Context, member: discord.Member = None):
    """Show member info.  !userinfo [@user]"""
    member = member or ctx.author
    uid = str(member.id)
    total_xp = xp_data.get(uid, 0)
    level, _, _ = level_from_xp(total_xp)
    warn_count = len(warnings_data.get(uid, []))

    embed = discord.Embed(title=str(member), color=member.color or OC_PINK, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "?", inline=True)
    embed.add_field(name="Registered", value=member.created_at.strftime("%b %d, %Y"), inline=True)
    embed.add_field(name="Level", value=f"{level} ({total_xp:,} XP)", inline=True)
    embed.add_field(name="Warnings", value=str(warn_count), inline=True)
    roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
    embed.add_field(name="Roles", value=" ".join(roles[:8]) or "None", inline=False)
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# COMMUNITY COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.command(name="poll")
@commands.guild_only()
async def cmd_poll(ctx: commands.Context, *, question: str):
    """Create a quick poll.  !poll [question]"""
    embed = discord.Embed(title="📊 Poll", description=question, color=OC_PINK)
    embed.set_footer(text=f"Asked by {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.command(name="announce")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_announce(ctx: commands.Context, channel: discord.TextChannel, *, text: str):
    """Send an announcement embed.  !announce #channel [text]"""
    embed = discord.Embed(description=text, color=OC_PINK, timestamp=discord.utils.utcnow())
    embed.set_footer(text=SERVER_NAME)
    await channel.send(embed=embed)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.command(name="say")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_say(ctx: commands.Context, *, text: str):
    """Make Vibe say something.  !say [text]"""
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(text)


@bot.command(name="ping")
async def cmd_ping(ctx: commands.Context):
    """Check bot latency.  !ping"""
    await ctx.send(f"Pong! **{round(bot.latency * 1000)}ms**")


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@bot.command(name="addcmd")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_addcmd(ctx: commands.Context, trigger: str, *, response: str):
    """Add a custom auto-response.  !addcmd <trigger> <response>"""
    key = trigger.lower().strip()
    custom_commands[key] = response
    _save_json(CMDS_FILE, custom_commands)
    await ctx.send(f"Custom command `{key}` saved.")


@bot.command(name="delcmd")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def cmd_delcmd(ctx: commands.Context, trigger: str):
    """Delete a custom command.  !delcmd <trigger>"""
    key = trigger.lower().strip()
    if key in custom_commands:
        del custom_commands[key]
        _save_json(CMDS_FILE, custom_commands)
        await ctx.send(f"Custom command `{key}` removed.")
    else:
        await ctx.send(f"No command found for `{key}`.", delete_after=8)


@bot.command(name="cmds")
@commands.guild_only()
async def cmd_cmds(ctx: commands.Context):
    """List all custom commands.  !cmds"""
    if not custom_commands:
        return await ctx.send("No custom commands set up yet.")
    embed = discord.Embed(title="Custom Commands", color=OC_PINK)
    embed.description = "\n".join(
        f"`{t}` → {r[:80]}{'…' if len(r) > 80 else ''}"
        for t, r in list(custom_commands.items())[:25]
    )
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# HELP + RESET
# ─────────────────────────────────────────────────────────────────────────────

@bot.command(name="help")
async def cmd_help(ctx: commands.Context):
    """Show all commands.  !help"""
    embed = discord.Embed(
        title=f"Vibe — {SERVER_NAME} Manager",
        description=f"Prefix: `{BOT_PREFIX}` · @mention Vibe to chat with AI",
        color=OC_PINK,
    )
    embed.add_field(name="🔨 Moderation", value=(
        "`kick` `ban` `unban`\n"
        "`mute [min]` `unmute`\n"
        "`warn` `warnings` `clearwarnings`\n"
        "`purge [n]` `slowmode [s]` `lock` `unlock`"
    ), inline=False)
    embed.add_field(name="⭐ Leveling", value="`rank [@user]` `leaderboard`", inline=False)
    embed.add_field(name="ℹ️ Info", value="`serverinfo` `userinfo [@user]` `ping`", inline=False)
    embed.add_field(name="📢 Community", value="`poll [question]` `announce #ch [text]` `say [text]`", inline=False)
    embed.add_field(name="⚙️ Custom Commands", value="`addcmd <trigger> <response>` `delcmd <trigger>` `cmds`", inline=False)
    embed.add_field(name="🤖 AI Chat", value="@mention Vibe with any question", inline=False)
    embed.add_field(name="🔄 Misc", value="`reset` — clear AI chat history in this channel", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="reset")
async def cmd_reset(ctx: commands.Context):
    """Clear AI chat history for this channel.  !reset"""
    conversation_histories[ctx.channel.id] = []
    await ctx.reply("Conversation history cleared. Fresh start!")


# ─────────────────────────────────────────────────────────────────────────────
# BOOT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("DISCORD_TOKEN not found in environment.")

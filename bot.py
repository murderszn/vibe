import discord
import anthropic
import os
import re
import json
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

client = discord.Client(intents=intents)

ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are Vibe, a cool cat admin of a Discord server focused on homeschooling and middle school education.

You are running inside a Discord server. Users interact with you by @mentioning you. You have full admin rights over the server and can use your tools to manage it — when someone asks you to take an action, use your tools to actually do it, don't just say you will.

You speak with a laid-back, cool cat persona but are highly educational, encouraging, and great at explaining complex middle school subjects in a fun, easy-to-understand way.

Keep responses concise and to the point. A few sentences is usually enough unless the topic genuinely needs more depth.

When you mention a website, tool, or resource by name, always include a clickable HTML hyperlink like: <a href="https://example.com">Example</a>. Never just name a site without linking it.

Use emojis sparingly — only when they genuinely add to the vibe. Avoid overusing cat emojis specifically.

Exercise admin powers responsibly. Confirm destructive actions (kick, ban, delete channel) in your reply so the requesting user knows what was done."""

TOOLS = [
    {
        "name": "kick_member",
        "description": "Kick a member from the server",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Discord user ID"},
                "reason": {"type": "string", "description": "Reason for the kick"}
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "ban_member",
        "description": "Ban a member from the server",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Discord user ID"},
                "reason": {"type": "string", "description": "Reason for the ban"},
                "delete_message_days": {"type": "integer", "description": "Days of messages to delete (0-7)", "default": 0}
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "unban_member",
        "description": "Unban a previously banned member",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Discord user ID to unban"}
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "timeout_member",
        "description": "Temporarily mute/timeout a member",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Discord user ID"},
                "duration_minutes": {"type": "integer", "description": "Timeout duration in minutes"},
                "reason": {"type": "string", "description": "Reason for the timeout"}
            },
            "required": ["user_id", "duration_minutes"]
        }
    },
    {
        "name": "purge_messages",
        "description": "Delete recent messages from the current channel",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of messages to delete (max 100)"}
            },
            "required": ["count"]
        }
    },
    {
        "name": "create_channel",
        "description": "Create a new text or voice channel",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Channel name"},
                "type": {"type": "string", "enum": ["text", "voice"], "description": "Channel type"}
            },
            "required": ["name", "type"]
        }
    },
    {
        "name": "delete_channel",
        "description": "Delete a channel by name",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_name": {"type": "string", "description": "Name of the channel to delete"}
            },
            "required": ["channel_name"]
        }
    },
    {
        "name": "rename_channel",
        "description": "Rename an existing channel",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_name": {"type": "string", "description": "Current channel name"},
                "new_name": {"type": "string", "description": "New channel name"}
            },
            "required": ["channel_name", "new_name"]
        }
    },
    {
        "name": "set_slowmode",
        "description": "Set slowmode delay on the current channel (0 to disable)",
        "input_schema": {
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "description": "Slowmode delay in seconds"}
            },
            "required": ["seconds"]
        }
    },
    {
        "name": "create_role",
        "description": "Create a new role in the server",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Role name"},
                "color": {"type": "string", "description": "Hex color like #ff5733 (optional)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "assign_role",
        "description": "Assign a role to a member",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Discord user ID"},
                "role_name": {"type": "string", "description": "Role name to assign"}
            },
            "required": ["user_id", "role_name"]
        }
    },
    {
        "name": "remove_role",
        "description": "Remove a role from a member",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Discord user ID"},
                "role_name": {"type": "string", "description": "Role name to remove"}
            },
            "required": ["user_id", "role_name"]
        }
    },
    {
        "name": "get_server_info",
        "description": "Get information about the current server: name, member count, channels, and roles",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_member_info",
        "description": "Get information about a specific member: name, roles, join date",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Discord user ID"}
            },
            "required": ["user_id"]
        }
    }
]


async def execute_tool(tool_name, tool_input, message):
    guild = message.guild
    try:
        if tool_name == "kick_member":
            member = guild.get_member(int(tool_input["user_id"]))
            if not member:
                return "Member not found."
            await member.kick(reason=tool_input.get("reason", "No reason provided"))
            return f"Kicked {member.display_name}."

        elif tool_name == "ban_member":
            member = guild.get_member(int(tool_input["user_id"]))
            if not member:
                return "Member not found."
            await member.ban(
                reason=tool_input.get("reason", "No reason provided"),
                delete_message_days=tool_input.get("delete_message_days", 0)
            )
            return f"Banned {member.display_name}."

        elif tool_name == "unban_member":
            user = await client.fetch_user(int(tool_input["user_id"]))
            await guild.unban(user)
            return f"Unbanned {user.name}."

        elif tool_name == "timeout_member":
            member = guild.get_member(int(tool_input["user_id"]))
            if not member:
                return "Member not found."
            await member.timeout(
                timedelta(minutes=tool_input["duration_minutes"]),
                reason=tool_input.get("reason", "No reason provided")
            )
            return f"Timed out {member.display_name} for {tool_input['duration_minutes']} minutes."

        elif tool_name == "purge_messages":
            count = min(tool_input["count"], 100)
            deleted = await message.channel.purge(limit=count)
            return f"Deleted {len(deleted)} messages."

        elif tool_name == "create_channel":
            if tool_input["type"] == "voice":
                channel = await guild.create_voice_channel(tool_input["name"])
            else:
                channel = await guild.create_text_channel(tool_input["name"])
            return f"Created {tool_input['type']} channel #{channel.name}."

        elif tool_name == "delete_channel":
            channel = discord.utils.get(guild.channels, name=tool_input["channel_name"])
            if not channel:
                return f"Channel '{tool_input['channel_name']}' not found."
            await channel.delete()
            return f"Deleted channel #{tool_input['channel_name']}."

        elif tool_name == "rename_channel":
            channel = discord.utils.get(guild.channels, name=tool_input["channel_name"])
            if not channel:
                return f"Channel '{tool_input['channel_name']}' not found."
            old_name = channel.name
            await channel.edit(name=tool_input["new_name"])
            return f"Renamed #{old_name} to #{tool_input['new_name']}."

        elif tool_name == "set_slowmode":
            await message.channel.edit(slowmode_delay=tool_input["seconds"])
            if tool_input["seconds"] == 0:
                return "Slowmode disabled."
            return f"Slowmode set to {tool_input['seconds']} seconds."

        elif tool_name == "create_role":
            color_str = tool_input.get("color", "#000000").lstrip("#")
            color = discord.Color(int(color_str, 16)) if color_str else discord.Color.default()
            role = await guild.create_role(name=tool_input["name"], color=color)
            return f"Created role '{role.name}'."

        elif tool_name == "assign_role":
            member = guild.get_member(int(tool_input["user_id"]))
            if not member:
                return "Member not found."
            role = discord.utils.get(guild.roles, name=tool_input["role_name"])
            if not role:
                return f"Role '{tool_input['role_name']}' not found."
            await member.add_roles(role)
            return f"Assigned '{role.name}' to {member.display_name}."

        elif tool_name == "remove_role":
            member = guild.get_member(int(tool_input["user_id"]))
            if not member:
                return "Member not found."
            role = discord.utils.get(guild.roles, name=tool_input["role_name"])
            if not role:
                return f"Role '{tool_input['role_name']}' not found."
            await member.remove_roles(role)
            return f"Removed '{role.name}' from {member.display_name}."

        elif tool_name == "get_server_info":
            return json.dumps({
                "name": guild.name,
                "member_count": guild.member_count,
                "channels": [{"name": c.name, "type": str(c.type)} for c in guild.channels],
                "roles": [r.name for r in guild.roles]
            })

        elif tool_name == "get_member_info":
            member = guild.get_member(int(tool_input["user_id"]))
            if not member:
                return "Member not found."
            return json.dumps({
                "name": member.display_name,
                "id": str(member.id),
                "roles": [r.name for r in member.roles],
                "joined_at": str(member.joined_at)
            })

        else:
            return f"Unknown tool: {tool_name}"

    except discord.Forbidden:
        return "I don't have permission to do that."
    except Exception as e:
        return f"Error: {e}"


def preprocess_mentions(content, guild):
    """Replace <@user_id> with @DisplayName (id: user_id) so Claude knows who is referenced."""
    def replace(match):
        user_id = int(match.group(1))
        member = guild.get_member(user_id)
        return f"@{member.display_name} (id: {user_id})" if member else match.group(0)
    return re.sub(r'<@!?(\d+)>', replace, content)


@client.event
async def on_ready():
    print(f'Cool cat {client.user} has logged in and is ready to vibe!')


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if not client.user.mentioned_in(message):
        return

    clean_content = message.content.replace(f'<@{client.user.id}>', '').strip()
    if not clean_content:
        clean_content = "Hey Vibe, what's up?"

    if message.guild:
        clean_content = preprocess_mentions(clean_content, message.guild)

    async with message.channel.typing():
        try:
            messages = [{"role": "user", "content": clean_content}]

            while True:
                response = ai.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages
                )

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            result = await execute_tool(block.name, block.input, message)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result
                            })
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

                else:
                    text = next((b.text for b in response.content if hasattr(b, "text")), None)
                    if text:
                        await message.reply(text)
                    break

        except Exception as e:
            await message.reply(f"Hit a snag: {e}")


if __name__ == "__main__":
    discord_token = os.getenv("DISCORD_TOKEN")
    if discord_token:
        client.run(discord_token)
    else:
        print("Hold up! I couldn't find the DISCORD_TOKEN in the .env file.")

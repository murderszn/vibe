import discord
import anthropic
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up Discord bot intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Initialize Anthropic client using the key from env, or a fallback
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_KEY")
ai = anthropic.Anthropic(api_key=anthropic_api_key)

# The cool cat personality
SYSTEM_PROMPT = """You are Vibe, a cool cat who is extremely knowledgeable about homeschooling and all the different topics in middle school.
You speak with a laid-back, cool cat persona but are highly educational, encouraging, and great at explaining complex middle school subjects in a fun, easy-to-understand way.

Keep responses concise and to the point — don't over-explain. A few sentences is usually enough unless the topic genuinely needs more depth.

When you mention a website, tool, or resource by name, always include a clickable HTML hyperlink, like: <a href="https://example.com">Example</a>. Never just name a site without linking it.

Use emojis sparingly — only when they genuinely add to the vibe. Avoid overusing cat emojis specifically."""

@client.event
async def on_ready():
    print(f'Cool cat {client.user} has logged in and is ready to vibe!')

@client.event
async def on_message(message):
    # Don't respond to ourselves
    if message.author == client.user:
        return
        
    # Only respond when @mentioned
    if client.user.mentioned_in(message):
        # Remove the bot mention from the prompt so Vibe doesn't read its own ID
        clean_content = message.content.replace(f'<@{client.user.id}>', '').strip()
        
        if not clean_content:
            clean_content = "Hey Vibe, what's up?"
            
        async with message.channel.typing():
            try:
                response = ai.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": clean_content}]
                )
                await message.reply(response.content[0].text)
            except Exception as e:
                await message.reply(f"Meow... hit a little snag: {e}")

if __name__ == "__main__":
    discord_token = os.getenv("DISCORD_TOKEN")
    if discord_token:
        client.run(discord_token)
    else:
        print("Hold up! I couldn't find the DISCORD_TOKEN in the .env file.")
